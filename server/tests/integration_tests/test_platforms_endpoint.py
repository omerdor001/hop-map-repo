"""Integration tests for GET /api/platforms."""
from __future__ import annotations

import pytest


class TestPlatformsEndpoint:

    def test_returns_200(self, app_client):
        client, _ = app_client
        resp = client.get("/api/platforms")
        assert resp.status_code == 200

    def test_response_has_required_keys(self, app_client):
        client, _ = app_client
        data = client.get("/api/platforms").json()
        assert "platforms" in data
        assert "browsers" in data
        assert "transit" in data

    def test_platforms_is_dict(self, app_client):
        client, _ = app_client
        data = client.get("/api/platforms").json()
        assert isinstance(data["platforms"], dict)

    def test_browsers_is_list(self, app_client):
        client, _ = app_client
        data = client.get("/api/platforms").json()
        assert isinstance(data["browsers"], list)

    def test_transit_is_list(self, app_client):
        client, _ = app_client
        data = client.get("/api/platforms").json()
        assert isinstance(data["transit"], list)

    def test_liveness_endpoint_returns_200(self, app_client):
        """Smoke-test /health/live while we have a client."""
        client, _ = app_client
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"
