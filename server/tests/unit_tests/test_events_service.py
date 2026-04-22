"""Pure unit tests for events.service — listener lifecycle, broadcast, and shutdown.

Each test class owns one slice of behaviour.  All tests manipulate module-level
state directly (white-box) and reset it via the `_clean_state` autouse fixture so
no test bleeds into another.

Covered behaviours:
  - register_listener  : queue creation and tracking
  - unregister_listener: normal removal, idempotent double-remove, unknown child_id
  - broadcast          : delivery, per-child isolation, snapshot safety
  - shutdown_all       : sentinel delivery, empty-registry safety, snapshot safety
  - lifecycle          : end-to-end session scenarios

asyncio_mode = auto (pytest.ini) — no @pytest.mark.asyncio needed.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import events.service as svc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset the shared listener registry before and after every test.

    _sse_queues is module-level state; without this fixture tests would leak
    queues into each other and produce non-deterministic failures.
    """
    svc._sse_queues.clear()
    yield
    svc._sse_queues.clear()


# =============================================================================
# register_listener
# =============================================================================


@pytest.mark.unit
class TestRegisterListener:
    """register_listener must create a queue, add it to the registry, and return it."""

    def test_returns_asyncio_queue(self):
        q = svc.register_listener("child-1")
        assert isinstance(q, asyncio.Queue)

    def test_listener_tracked_under_child_id(self):
        q = svc.register_listener("child-1")
        assert q in svc._sse_queues["child-1"]

    def test_first_registration_creates_set_entry(self):
        """The registry value must be a set — required for O(1) discard."""
        svc.register_listener("child-1")
        assert isinstance(svc._sse_queues["child-1"], set)
        assert len(svc._sse_queues["child-1"]) == 1

    def test_each_call_returns_distinct_queue(self):
        """Two registrations for the same child must produce two independent queues."""
        q1 = svc.register_listener("child-1")
        q2 = svc.register_listener("child-1")
        assert q1 is not q2

    def test_multiple_listeners_same_child_all_tracked(self):
        q1 = svc.register_listener("child-1")
        q2 = svc.register_listener("child-1")
        assert {q1, q2} == svc._sse_queues["child-1"]

    def test_different_children_use_separate_sets(self):
        q1 = svc.register_listener("child-a")
        q2 = svc.register_listener("child-b")
        assert q1 not in svc._sse_queues["child-b"]
        assert q2 not in svc._sse_queues["child-a"]


# =============================================================================
# unregister_listener
# =============================================================================


@pytest.mark.unit
class TestUnregisterListener:
    """unregister_listener must remove the queue and be safe under all error conditions."""

    def test_removes_listener_from_set(self):
        q = svc.register_listener("child-1")
        svc.unregister_listener("child-1", q)
        assert q not in svc._sse_queues.get("child-1", set())

    def test_prunes_empty_child_entry(self):
        """child_id key must be deleted once its set is empty — no ghost entries."""
        q = svc.register_listener("child-1")
        svc.unregister_listener("child-1", q)
        assert "child-1" not in svc._sse_queues

    def test_sibling_listener_survives_unregister(self):
        """Only the specified queue is removed; the other listener for the same child remains."""
        q1 = svc.register_listener("child-1")
        q2 = svc.register_listener("child-1")
        svc.unregister_listener("child-1", q1)
        assert q2 in svc._sse_queues["child-1"]

    def test_sibling_child_entry_unaffected(self):
        """Unregistering from one child must not touch another child's set."""
        q_a = svc.register_listener("child-a")
        q_b = svc.register_listener("child-b")
        svc.unregister_listener("child-a", q_a)
        assert q_b in svc._sse_queues["child-b"]

    def test_double_unregister_does_not_raise(self):
        """Calling unregister twice for the same queue must be idempotent.

        Before fix: list.remove() raised ValueError on the second call because
        the element was already gone.  discard() is unconditionally safe.
        """
        q = svc.register_listener("child-1")
        svc.unregister_listener("child-1", q)
        svc.unregister_listener("child-1", q)  # must not raise ValueError

    def test_unknown_child_id_does_not_raise(self):
        """Unregistering a queue for a child_id that was never registered must be a no-op.

        Before fix: _sse_queues[child_id] raised KeyError when child_id was absent.
        dict.get() is unconditionally safe.
        """
        q = asyncio.Queue()
        svc.unregister_listener("ghost-child", q)  # must not raise KeyError

    def test_unregister_after_entry_pruned_does_not_raise(self):
        """After the last listener is removed and the key is deleted, a second call must
        still succeed — child_id is gone from the dict, not just the set."""
        q = svc.register_listener("child-1")
        svc.unregister_listener("child-1", q)
        assert "child-1" not in svc._sse_queues  # key pruned
        svc.unregister_listener("child-1", q)    # must not raise KeyError


# =============================================================================
# broadcast
# =============================================================================


@pytest.mark.unit
class TestBroadcast:
    """broadcast must deliver the payload to all registered queues for the target child only."""

    async def test_delivers_payload_to_single_listener(self):
        q = svc.register_listener("child-1")
        await svc.broadcast("child-1", {"type": "hop"})
        assert q.get_nowait() == {"type": "hop"}

    async def test_delivers_payload_to_all_listeners_for_child(self):
        q1 = svc.register_listener("child-1")
        q2 = svc.register_listener("child-1")
        await svc.broadcast("child-1", {"type": "hop"})
        assert q1.get_nowait() == {"type": "hop"}
        assert q2.get_nowait() == {"type": "hop"}

    async def test_does_not_deliver_to_other_children(self):
        svc.register_listener("child-a")
        q_b = svc.register_listener("child-b")
        await svc.broadcast("child-a", {"type": "hop"})
        assert q_b.empty()

    async def test_unregistered_child_is_no_op(self):
        """Broadcasting to a child with no listeners must not raise."""
        await svc.broadcast("ghost-child", {"type": "hop"})  # must not raise

    async def test_payload_delivered_verbatim(self):
        """The exact dict object must arrive in the queue — no copying or wrapping."""
        payload = {"type": "hop", "from": "roblox.exe", "to": "discord.exe"}
        q = svc.register_listener("child-1")
        await svc.broadcast("child-1", payload)
        assert q.get_nowait() is payload

    async def test_snapshot_tolerates_unregister_during_iteration(self):
        """Unregistering a listener mid-broadcast must not raise RuntimeError, and
        the removed listener must still receive the item that was in-flight.

        Without the list() snapshot, iterating a set while a listener unregisters
        between two await q.put() calls raises:
            RuntimeError: Set changed size during iteration

        The snapshot freezes the iteration target so mutations to the live set are
        irrelevant.  We guarantee the race fires regardless of set iteration order
        by patching both queues symmetrically: whichever is visited first removes
        the other from the live set.  Both queues must still receive because they
        were both captured in the snapshot before iteration began.
        """
        q1 = svc.register_listener("child-1")
        q2 = svc.register_listener("child-1")

        orig1, orig2 = q1.put, q2.put

        async def put_and_remove_sibling(orig, sibling, item):
            await orig(item)
            svc.unregister_listener("child-1", sibling)  # discard — safe even if already gone

        q1.put = lambda item: put_and_remove_sibling(orig1, q2, item)
        q2.put = lambda item: put_and_remove_sibling(orig2, q1, item)

        await svc.broadcast("child-1", {"type": "hop"})  # must not raise RuntimeError

        # Both queues receive — snapshot guarantees delivery to all listeners that
        # were registered at broadcast time, even if they disconnect mid-fanout.
        assert q1.qsize() == 1
        assert q2.qsize() == 1


# =============================================================================
# shutdown_all
# =============================================================================


@pytest.mark.unit
class TestShutdownAll:
    """shutdown_all must send _SSE_SHUTDOWN to every queue across all children."""

    async def test_sends_sentinel_to_single_listener(self):
        q = svc.register_listener("child-1")
        await svc.shutdown_all()
        assert q.get_nowait() is svc._SSE_SHUTDOWN

    async def test_sends_sentinel_to_all_listeners_across_children(self):
        q1 = svc.register_listener("child-a")
        q2 = svc.register_listener("child-a")
        q3 = svc.register_listener("child-b")
        await svc.shutdown_all()
        assert q1.get_nowait() is svc._SSE_SHUTDOWN
        assert q2.get_nowait() is svc._SSE_SHUTDOWN
        assert q3.get_nowait() is svc._SSE_SHUTDOWN

    async def test_empty_registry_is_no_op(self):
        """shutdown_all on an empty registry must not raise."""
        await svc.shutdown_all()  # must not raise

    async def test_snapshot_tolerates_unregister_during_shutdown(self):
        """Unregistering a listener while shutdown_all iterates must not raise RuntimeError.

        Same race as TestBroadcast.test_snapshot_tolerates_unregister_during_iteration —
        shutdown_all snapshots both the outer dict values and each inner set.
        Both queues must still receive _SSE_SHUTDOWN because they were captured
        in the snapshot before iteration began.
        """
        q1 = svc.register_listener("child-1")
        q2 = svc.register_listener("child-1")

        orig1, orig2 = q1.put, q2.put

        async def put_and_remove_sibling(orig, sibling, item):
            await orig(item)
            svc.unregister_listener("child-1", sibling)

        q1.put = lambda item: put_and_remove_sibling(orig1, q2, item)
        q2.put = lambda item: put_and_remove_sibling(orig2, q1, item)

        await svc.shutdown_all()  # must not raise RuntimeError

        assert q1.get_nowait() is svc._SSE_SHUTDOWN
        assert q2.get_nowait() is svc._SSE_SHUTDOWN


# =============================================================================
# Lifecycle scenarios
# =============================================================================


@pytest.mark.unit
class TestListenerLifecycle:
    """End-to-end flows that combine register, broadcast, and unregister."""

    async def test_golden_path_connect_receive_disconnect(self):
        """Standard SSE session: connect, receive event, disconnect cleanly."""
        q = svc.register_listener("child-1")
        await svc.broadcast("child-1", {"type": "hop"})
        assert q.get_nowait() == {"type": "hop"}
        svc.unregister_listener("child-1", q)
        assert "child-1" not in svc._sse_queues

    async def test_no_delivery_after_disconnect(self):
        """Events emitted after unregister must not be queued to the removed listener."""
        q = svc.register_listener("child-1")
        svc.unregister_listener("child-1", q)
        await svc.broadcast("child-1", {"type": "hop"})
        assert q.empty()

    async def test_two_children_are_fully_isolated(self):
        """Events for child-a must never appear in child-b's queue and vice versa."""
        q_a = svc.register_listener("child-a")
        q_b = svc.register_listener("child-b")

        await svc.broadcast("child-a", {"for": "a"})
        await svc.broadcast("child-b", {"for": "b"})

        assert q_a.get_nowait() == {"for": "a"}
        assert q_b.get_nowait() == {"for": "b"}
        assert q_a.empty()
        assert q_b.empty()

    async def test_re_register_after_full_cleanup_works(self):
        """A child can reconnect (re-register) after a full disconnect without any state leak."""
        q1 = svc.register_listener("child-1")
        svc.unregister_listener("child-1", q1)
        assert "child-1" not in svc._sse_queues

        q2 = svc.register_listener("child-1")
        await svc.broadcast("child-1", {"type": "reconnect"})
        assert q2.get_nowait() == {"type": "reconnect"}
        assert q1.empty()  # old queue must not receive events from the new session
