"""Integration tests for POST /agent/hop/{child_id}.

Uses TestClient + mongomock — no real server or DB needed.
"""
from __future__ import annotations

import pytest

from test_helpers import register_test_child


CHILD_ID = "inttest-hop-child"


class TestHopEndpointIngestion:

    def test_valid_hop_returns_200(self, app_client):
        client, _ = app_client
        body = {
            "from": "robloxplayerbeta.exe",
            "to": "chrome.exe",
            "fromTitle": "Roblox",
            "toTitle": "Google Chrome",
            "detection": "confirmed_hop",
            "timestamp": "2026-01-01T12:00:00Z",
            "clickConfidence": "app_match",
        }
        resp = client.post(f"/agent/hop/{CHILD_ID}", json=body)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_confirmed_hop_persisted_in_db(self, app_client):
        """A confirmed_hop with non-switch_only confidence must be stored."""
        client, _ = app_client
        body = {
            "from": "robloxplayerbeta.exe",
            "to": "discord.exe",
            "fromTitle": "Roblox",
            "toTitle": "Discord",
            "detection": "confirmed_hop",
            "timestamp": "2026-01-01T12:00:00Z",
            "clickConfidence": "app_match",
        }
        client.post(f"/agent/hop/{CHILD_ID}", json=body)

        register_test_child(CHILD_ID)
        resp = client.get(f"/api/events/{CHILD_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert any(e["from"] == "robloxplayerbeta.exe" for e in data["events"])

    def test_switch_only_hop_not_persisted(self, app_client):
        """switch_only clickConfidence must not persist to DB."""
        client, _ = app_client
        child = "switch-only-child"
        client.post(f"/agent/hop/{child}", json={
            "from": "robloxplayerbeta.exe",
            "to": "chrome.exe",
            "detection": "confirmed_hop",
            "clickConfidence": "switch_only",
        })
        register_test_child(child)
        assert client.get(f"/api/events/{child}").json()["count"] == 0

    def test_non_confirmed_hop_not_persisted(self, app_client):
        """Events without detection=confirmed_hop must not be stored."""
        client, _ = app_client
        child = "non-confirmed-child"
        client.post(f"/agent/hop/{child}", json={
            "from": "robloxplayerbeta.exe",
            "to": "chrome.exe",
            "clickConfidence": "title_match",
        })
        register_test_child(child)
        assert client.get(f"/api/events/{child}").json()["count"] == 0

    def test_invalid_child_id_returns_400(self, app_client):
        client, _ = app_client
        resp = client.post("/agent/hop/bad id!", json={"from": "a", "to": "b"})
        assert resp.status_code == 400

    def test_empty_body_still_returns_200(self, app_client):
        """Server must not crash on a minimal/empty body — fields are optional."""
        client, _ = app_client
        resp = client.post(f"/agent/hop/{CHILD_ID}", json={})
        assert resp.status_code == 200
