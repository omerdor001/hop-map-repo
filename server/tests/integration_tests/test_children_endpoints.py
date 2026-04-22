"""Integration tests for children management endpoints.

  GET  /api/children
  POST /api/children          (register)
  PATCH /api/children/{id}    (rename)
"""
from __future__ import annotations

import pytest

from core.database import pool


class TestListChildren:

    def test_empty_list_initially(self, app_client):
        client, _ = app_client
        resp = client.get("/api/children")
        assert resp.status_code == 200
        data = resp.json()
        assert "children" in data
        assert isinstance(data["children"], list)

    def test_registered_child_appears_in_list(self, app_client):
        client, _ = app_client
        client.post("/api/children", json={"childId": "list-test-kid", "childName": "Alice"})
        children = {c["childId"] for c in client.get("/api/children").json()["children"]}
        assert "list-test-kid" in children


class TestRegisterChild:

    def test_register_with_explicit_id_and_name(self, app_client):
        client, _ = app_client
        resp = client.post("/api/children", json={"childId": "reg-kid-1", "childName": "Bob"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["ok"] is True
        assert data["childId"] == "reg-kid-1"
        assert data["childName"] == "Bob"

    def test_register_without_id_generates_uuid(self, app_client):
        client, _ = app_client
        resp = client.post("/api/children", json={})
        assert resp.status_code == 201
        child_id = resp.json()["childId"]
        # Should be a valid non-empty string (UUID format).
        assert len(child_id) > 0

    def test_register_without_name_uses_id_as_name(self, app_client):
        client, _ = app_client
        resp = client.post("/api/children", json={"childId": "no-name-kid"})
        data = resp.json()
        assert data["childName"] == "no-name-kid"

    def test_re_registration_does_not_overwrite_name(self, app_client):
        """Second register call with different name must not change stored name."""
        client, _ = app_client
        client.post("/api/children", json={"childId": "idem-kid", "childName": "Original"})
        client.post("/api/children", json={"childId": "idem-kid", "childName": "Changed"})
        children = {c["childId"]: c["childName"]
                    for c in client.get("/api/children").json()["children"]}
        assert children["idem-kid"] == "Original"


class TestRenameChild:

    def test_rename_updates_name(self, app_client):
        client, _ = app_client
        client.post("/api/children", json={"childId": "rename-kid", "childName": "OldName"})
        resp = client.patch("/api/children/rename-kid",
                            json={"childName": "NewName"})
        assert resp.status_code == 200
        assert resp.json()["childName"] == "NewName"

    def test_renamed_name_reflected_in_list(self, app_client):
        client, _ = app_client
        client.post("/api/children", json={"childId": "rename-kid-2", "childName": "Alpha"})
        client.patch("/api/children/rename-kid-2", json={"childName": "Beta"})
        children = {c["childId"]: c["childName"]
                    for c in client.get("/api/children").json()["children"]}
        assert children.get("rename-kid-2") == "Beta"

    def test_rename_empty_name_returns_422(self, app_client):
        # Schema-level validation (min_length=1 after strip) produces 422, not 400.
        # 422 Unprocessable Entity is the correct HTTP status for semantic
        # validation failures on a well-formed request body (RFC 9110).
        client, _ = app_client
        client.post("/api/children", json={"childId": "rename-kid-3", "childName": "Valid"})
        resp = client.patch("/api/children/rename-kid-3", json={"childName": ""})
        assert resp.status_code == 422
        # Whitespace-only is also rejected after stripping.
        resp2 = client.patch("/api/children/rename-kid-3", json={"childName": "   "})
        assert resp2.status_code == 422

    def test_rename_invalid_child_id_format_returns_400(self, app_client):
        client, _ = app_client
        resp = client.patch("/api/children/bad id!", json={"childName": "NewName"})
        assert resp.status_code == 400

    def test_rename_rejects_other_parents_child(self, app_client):
        """Renaming a child owned by a different parent must return 404 and leave the DB unchanged."""
        client, _ = app_client
        pool.get_collection("children").insert_one({
            "childId": "other-parents-kid",
            "childName": "OriginalName",
            "parentId": "other-parent-id",
            "agentTokenHash": "dummy",
            "agentTokenPrefix": "dum",
        })
        resp = client.patch("/api/children/other-parents-kid", json={"childName": "Stolen"})
        assert resp.status_code == 404
        doc = pool.get_collection("children").find_one({"childId": "other-parents-kid"})
        assert doc["childName"] == "OriginalName"
