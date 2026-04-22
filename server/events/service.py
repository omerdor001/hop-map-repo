import asyncio

_sse_queues: dict[str, set[asyncio.Queue]] = {}
_SSE_SHUTDOWN = object()


def register_listener(child_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _sse_queues.setdefault(child_id, set()).add(q)
    return q


def unregister_listener(child_id: str, q: asyncio.Queue) -> None:
    listeners = _sse_queues.get(child_id)
    if listeners is None:
        return
    listeners.discard(q)
    if not listeners:
        _sse_queues.pop(child_id, None)


async def broadcast(child_id: str, payload: dict) -> None:
    for q in list(_sse_queues.get(child_id, ())):
        await q.put(payload)


async def shutdown_all() -> None:
    for queues in list(_sse_queues.values()):
        for q in list(queues):
            await q.put(_SSE_SHUTDOWN)
