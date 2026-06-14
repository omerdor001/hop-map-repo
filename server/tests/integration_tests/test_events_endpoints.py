"""Integration tests for GET/DELETE /api/events/{child_id}.

Uses TestClient + mongomock — no real server or DB needed.
"""
from __future__ import annotations

import pytest

from test_helpers import register_test_child


def _post_hop(client, child_id: str, from_app: str = "roblox.exe", to_app: str = "discord.exe") -> None:
    client.post(f"/agent/hop/{child_id}", json={
        "from": from_app, "to": to_app,
        "detection": "confirmed_hop",
        "clickConfidence": "app_match",
        "timestamp": "2026-01-01T12:00:00Z",
    })


class TestGetEvents:

    def test_returns_200_and_empty_list_for_child_with_no_events(self, app_client):
        client, _ = app_client
        child = "get-events-empty"
        register_test_child(child)
        resp = client.get(f"/api/events/{child}")
        assert resp.status_code == 200
        assert resp.json() == {"childId": child, "events": [], "count": 0}

    def test_returns_stored_events(self, app_client):
        client, _ = app_client
        child = "get-events-child"
        _post_hop(client, child, from_app="roblox.exe", to_app="discord.exe")
        register_test_child(child)
        data = client.get(f"/api/events/{child}").json()
        assert data["count"] == 1
        assert data["events"][0]["from"] == "roblox.exe"

    def test_returns_403_for_unregistered_child(self, app_client):
        """Child not in DB should return 403, not 500."""
        client, _ = app_client
        resp = client.get("/api/events/unregistered-child-xyz")
        assert resp.status_code == 403

    def test_invalid_child_id_returns_400(self, app_client):
        client, _ = app_client
        resp = client.get("/api/events/bad id!")
        assert resp.status_code == 400

    def test_limit_parameter_caps_results(self, app_client):
        client, _ = app_client
        child = "get-events-limit"
        for _ in range(5):
            _post_hop(client, child)
        register_test_child(child)
        data = client.get(f"/api/events/{child}?limit=3").json()
        assert data["count"] == 3

    def test_events_for_different_children_are_isolated(self, app_client):
        client, _ = app_client
        child_a, child_b = "iso-events-a", "iso-events-b"
        _post_hop(client, child_a)
        register_test_child(child_a)
        register_test_child(child_b)
        assert client.get(f"/api/events/{child_b}").json()["count"] == 0


class TestClearEvents:

    def test_returns_deleted_count(self, app_client):
        client, _ = app_client
        child = "clear-events-count"
        _post_hop(client, child)
        _post_hop(client, child)
        register_test_child(child)
        resp = client.delete(f"/api/events/{child}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 2

    def test_events_absent_after_clear(self, app_client):
        client, _ = app_client
        child = "clear-events-absent"
        _post_hop(client, child)
        register_test_child(child)
        client.delete(f"/api/events/{child}")
        assert client.get(f"/api/events/{child}").json()["count"] == 0

    def test_clear_does_not_affect_other_children(self, app_client):
        client, _ = app_client
        child_a, child_b = "clear-iso-a", "clear-iso-b"
        _post_hop(client, child_a)
        _post_hop(client, child_b)
        register_test_child(child_a)
        register_test_child(child_b)
        client.delete(f"/api/events/{child_a}")
        assert client.get(f"/api/events/{child_b}").json()["count"] == 1

    def test_returns_403_for_unregistered_child(self, app_client):
        client, _ = app_client
        resp = client.delete("/api/events/unregistered-child-xyz")
        assert resp.status_code == 403
