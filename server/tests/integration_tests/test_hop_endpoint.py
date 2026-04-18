"""Integration tests for POST /agent/hop/{child_id}.

Uses TestClient + mongomock — no real server or DB needed.
"""
from __future__ import annotations

import pytest


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

    def test_hop_event_persisted_in_db(self, app_client):
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

        events_resp = client.get(f"/api/events/{CHILD_ID}")
        assert events_resp.status_code == 200
        data = events_resp.json()
        assert data["count"] >= 1
        assert any(e["from"] == "robloxplayerbeta.exe" for e in data["events"])

    def test_switch_only_hop_not_persisted(self, app_client):
        """switch_only clickConfidence should NOT persist the event to DB."""
        client, _ = app_client
        child = "switch-only-child"
        body = {
            "from": "robloxplayerbeta.exe",
            "to": "chrome.exe",
            "detection": "confirmed_hop",
            "clickConfidence": "switch_only",
        }
        client.post(f"/agent/hop/{child}", json=body)

        events_resp = client.get(f"/api/events/{child}")
        assert events_resp.json()["count"] == 0

    def test_non_confirmed_hop_not_persisted(self, app_client):
        """Events without detection=confirmed_hop are not stored."""
        client, _ = app_client
        child = "non-confirmed-child"
        body = {
            "from": "robloxplayerbeta.exe",
            "to": "chrome.exe",
            "clickConfidence": "title_match",
        }
        client.post(f"/agent/hop/{child}", json=body)

        events_resp = client.get(f"/api/events/{child}")
        assert events_resp.json()["count"] == 0

    def test_invalid_child_id_returns_400(self, app_client):
        client, _ = app_client
        resp = client.post("/agent/hop/bad id!", json={"from": "a", "to": "b"})
        assert resp.status_code == 400

    def test_empty_body_still_returns_200(self, app_client):
        """Server must not crash on a minimal/empty body — fields are optional."""
        client, _ = app_client
        resp = client.post(f"/agent/hop/{CHILD_ID}", json={})
        assert resp.status_code == 200
