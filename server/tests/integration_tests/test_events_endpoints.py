"""Integration tests for GET /api/events/{child_id} and DELETE /api/events/{child_id}."""
from __future__ import annotations

import pytest

from test_helpers import register_test_child


CHILD_ID = "inttest-events-child"


def _insert_hop(client, child_id: str = CHILD_ID, **kwargs):
    register_test_child(child_id)
    body = {
        "from": "roblox.exe",
        "to": "discord.exe",
        "fromTitle": "Roblox",
        "toTitle": "Discord",
        "detection": "confirmed_hop",
        "clickConfidence": "app_match",
        **kwargs,
    }
    resp = client.post(f"/agent/hop/{child_id}", json=body)
    assert resp.status_code == 200


class TestGetEvents:

    def test_empty_child_returns_zero_count(self, app_client):
        client, _ = app_client
        register_test_child("nobody-here")
        resp = client.get("/api/events/nobody-here")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["events"] == []

    def test_events_include_inserted_hop(self, app_client):
        client, _ = app_client
        _insert_hop(client)
        resp = client.get(f"/api/events/{CHILD_ID}")
        assert resp.json()["count"] == 1

    def test_multiple_events_returned(self, app_client):
        client, _ = app_client
        _insert_hop(client)
        _insert_hop(client)
        resp = client.get(f"/api/events/{CHILD_ID}")
        assert resp.json()["count"] == 2

    def test_events_response_has_required_fields(self, app_client):
        client, _ = app_client
        _insert_hop(client)
        events = client.get(f"/api/events/{CHILD_ID}").json()["events"]
        event = events[0]
        assert "childId" in event
        assert "from" in event
        assert "to" in event
        assert "timestamp" in event

    def test_events_scoped_to_child(self, app_client):
        """Events for one child must not bleed into another child's results."""
        client, _ = app_client
        _insert_hop(client, child_id="child-a")
        _insert_hop(client, child_id="child-b")
        resp_a = client.get("/api/events/child-a").json()
        resp_b = client.get("/api/events/child-b").json()
        assert resp_a["count"] == 1
        assert resp_b["count"] == 1

    def test_invalid_child_id_returns_400(self, app_client):
        client, _ = app_client
        resp = client.get("/api/events/bad id!")
        assert resp.status_code == 400

    def test_limit_parameter_respected(self, app_client):
        client, _ = app_client
        for _ in range(5):
            _insert_hop(client)
        resp = client.get(f"/api/events/{CHILD_ID}?limit=2")
        assert resp.json()["count"] == 2

    def test_limit_zero_returns_422(self, app_client):
        client, _ = app_client
        resp = client.get(f"/api/events/{CHILD_ID}?limit=0")
        assert resp.status_code == 422

    def test_limit_above_max_returns_422(self, app_client):
        client, _ = app_client
        resp = client.get(f"/api/events/{CHILD_ID}?limit=501")
        assert resp.status_code == 422


class TestDeleteEvents:

    def test_clear_returns_deleted_count(self, app_client):
        client, _ = app_client
        _insert_hop(client)
        _insert_hop(client)
        resp = client.delete(f"/api/events/{CHILD_ID}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 2

    def test_events_empty_after_clear(self, app_client):
        client, _ = app_client
        _insert_hop(client)
        client.delete(f"/api/events/{CHILD_ID}")
        remaining = client.get(f"/api/events/{CHILD_ID}").json()["count"]
        assert remaining == 0

    def test_clear_on_empty_child_returns_zero(self, app_client):
        client, _ = app_client
        register_test_child("no-events-ever")
        resp = client.delete("/api/events/no-events-ever")
        assert resp.json()["deleted"] == 0

    def test_clear_does_not_affect_other_children(self, app_client):
        client, _ = app_client
        _insert_hop(client, child_id="keep-child")
        _insert_hop(client, child_id="clear-child")
        client.delete("/api/events/clear-child")
        kept = client.get("/api/events/keep-child").json()["count"]
        assert kept == 1
