"""Unit tests for game-process detection: registry, Epic, Riot, and _is_game().

winreg is already stubbed by conftest.py.  Manifest files are created in
pytest's tmp_path to avoid touching the filesystem of the test machine.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import sys

import pytest

import agent as _agent


class TestLoadFromEpic:

    def test_returns_exe_from_valid_manifest(self, tmp_path):
        manifest = {"LaunchExecutable": "FortniteGame/Binaries/Win64/FortniteLauncher.exe"}
        item_file = tmp_path / "fortnite.item"
        item_file.write_text(json.dumps(manifest), encoding="utf-8")

        with patch.object(_agent, "_EPIC_MANIFESTS_DIR", tmp_path):
            exes = _agent._load_from_epic()

        assert "fortnitelauncher.exe" in exes

    def test_returns_empty_when_directory_missing(self, tmp_path):
        missing = tmp_path / "nonexistent_epic"
        with patch.object(_agent, "_EPIC_MANIFESTS_DIR", missing):
            exes = _agent._load_from_epic()
        assert exes == set()

    def test_skips_malformed_manifest(self, tmp_path):
        bad_file = tmp_path / "bad.item"
        bad_file.write_text("not valid json", encoding="utf-8")
        with patch.object(_agent, "_EPIC_MANIFESTS_DIR", tmp_path):
            exes = _agent._load_from_epic()
        assert exes == set()

    def test_skips_manifest_with_no_launch_executable(self, tmp_path):
        manifest = {"DisplayName": "SomeGame"}  # no LaunchExecutable
        item_file = tmp_path / "some.item"
        item_file.write_text(json.dumps(manifest), encoding="utf-8")
        with patch.object(_agent, "_EPIC_MANIFESTS_DIR", tmp_path):
            exes = _agent._load_from_epic()
        assert exes == set()

    def test_result_is_lowercase(self, tmp_path):
        manifest = {"LaunchExecutable": "Bin/Win64/MyGame.exe"}
        item_file = tmp_path / "mg.item"
        item_file.write_text(json.dumps(manifest), encoding="utf-8")
        with patch.object(_agent, "_EPIC_MANIFESTS_DIR", tmp_path):
            exes = _agent._load_from_epic()
        assert all(e == e.lower() for e in exes)


class TestLoadFromRiot:

    def test_returns_exe_from_valid_settings_file(self, tmp_path):
        product_dir = tmp_path / "live-valorant-win"
        product_dir.mkdir()
        yaml_content = 'exe_name: "VALORANT-Win64-Shipping.exe"\nother: stuff\n'
        (product_dir / "valorant.product_settings.yaml").write_text(yaml_content, encoding="utf-8")

        with patch.object(_agent, "_RIOT_METADATA_DIR", tmp_path):
            exes = _agent._load_from_riot()

        assert "valorant-win64-shipping.exe" in exes

    def test_returns_empty_when_directory_missing(self, tmp_path):
        missing = tmp_path / "nonexistent_riot"
        with patch.object(_agent, "_RIOT_METADATA_DIR", missing):
            exes = _agent._load_from_riot()
        assert exes == set()

    def test_skips_product_dir_without_yaml(self, tmp_path):
        product_dir = tmp_path / "live-league-win"
        product_dir.mkdir()
        # No .yaml file inside.
        with patch.object(_agent, "_RIOT_METADATA_DIR", tmp_path):
            exes = _agent._load_from_riot()
        assert exes == set()

    def test_result_is_lowercase(self, tmp_path):
        product_dir = tmp_path / "live-lol-win"
        product_dir.mkdir()
        yaml_content = 'exe_name: "League_Of_Legends.exe"\n'
        (product_dir / "lol.product_settings.yaml").write_text(yaml_content, encoding="utf-8")
        with patch.object(_agent, "_RIOT_METADATA_DIR", tmp_path):
            exes = _agent._load_from_riot()
        assert all(e == e.lower() for e in exes)


class TestLoadFromRegistry:

    def test_returns_exe_from_registry_key(self):
        """Mock winreg to simulate a game registered via Game Mode."""
        parent_cm = MagicMock()
        parent_cm.__enter__ = MagicMock(return_value=parent_cm)
        parent_cm.__exit__ = MagicMock(return_value=False)

        child_cm = MagicMock()
        child_cm.__enter__ = MagicMock(return_value=child_cm)
        child_cm.__exit__ = MagicMock(return_value=False)

        with patch("winreg.OpenKey", side_effect=[parent_cm, child_cm]), \
             patch("winreg.EnumKey", side_effect=["child-0", OSError("no more")]), \
             patch("winreg.QueryValueEx",
                   return_value=(r"C:\Games\Roblox\RobloxPlayerBeta.exe", 1)):
            exes = _agent._load_from_registry()

        assert "robloxplayerbeta.exe" in exes

    def test_returns_empty_when_registry_key_absent(self):
        with patch("winreg.OpenKey", side_effect=OSError("key not found")):
            exes = _agent._load_from_registry()
        assert exes == set()


class TestIsGame:

    def setup_method(self):
        """Reset cache so each test starts fresh."""
        _agent._game_processes_cache = frozenset()
        _agent._game_cache_updated_at = 0.0

    def test_known_game_returns_true(self):
        with patch.object(_agent, "_load_game_processes",
                          return_value=frozenset({"robloxplayerbeta.exe"})):
            assert _agent._is_game("robloxplayerbeta.exe") is True

    def test_unknown_process_returns_false(self):
        with patch.object(_agent, "_load_game_processes",
                          return_value=frozenset({"robloxplayerbeta.exe"})):
            assert _agent._is_game("discord.exe") is False

    def test_check_is_case_insensitive(self):
        with patch.object(_agent, "_load_game_processes",
                          return_value=frozenset({"robloxplayerbeta.exe"})):
            assert _agent._is_game("RobloxPlayerBeta.EXE") is True

    def test_cache_not_refreshed_within_ttl(self):
        """_load_game_processes should only be called once within the TTL window."""
        loader = MagicMock(return_value=frozenset({"game.exe"}))
        with patch.object(_agent, "_load_game_processes", loader):
            _agent._is_game("game.exe")
            _agent._is_game("game.exe")
        assert loader.call_count == 1

    def test_cache_refreshed_after_ttl_expires(self):
        """After TTL, the loader must be called again."""
        loader = MagicMock(return_value=frozenset({"game.exe"}))
        with patch.object(_agent, "_load_game_processes", loader):
            # Mark cache as very stale so the first call always triggers a reload.
            _agent._game_cache_updated_at = time.monotonic() - (_agent._GAME_CACHE_TTL + 100)
            _agent._is_game("game.exe")  # first refresh

            # Expire the cache again.
            _agent._game_cache_updated_at = time.monotonic() - (_agent._GAME_CACHE_TTL + 100)
            _agent._is_game("game.exe")  # second refresh

        assert loader.call_count == 2
