"""
Unit tests for platforms.service.load_platforms_db().

All tests are fully in-process — no server, no HTTP.
Temporary Excel files are built with openpyxl and written to pytest's tmp_path.
The module-level globals are reset before each test via monkeypatch.
"""

import sys
from pathlib import Path

import pytest
import openpyxl

_SERVER_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

import platforms.service as platforms_svc
from platforms.service import load_platforms_db
from config import config_manager


def _make_xlsx(tmp_path, rows: list[tuple[str, str]]) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["platform", "process"])
    for platform, process in rows:
        ws.append([platform, process])
    path = tmp_path / "platforms_test.xlsx"
    wb.save(str(path))
    return str(path)


class TestLoadPlatformsDB:

    @pytest.fixture(autouse=True)
    def _reset_platform_globals(self, monkeypatch):
        monkeypatch.setattr(platforms_svc, "_platform_app_map", {})
        monkeypatch.setattr(platforms_svc, "_browser_processes", [])
        monkeypatch.setattr(platforms_svc, "_transit_processes", [])

    def test_missing_file_leaves_globals_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(config_manager.data, "platforms_db_path", str(tmp_path / "nonexistent.xlsx"))
        load_platforms_db()
        assert platforms_svc._platform_app_map == {}
        assert platforms_svc._browser_processes == []
        assert platforms_svc._transit_processes == []

    def test_platform_rows_loaded_into_map(self, monkeypatch, tmp_path):
        path = _make_xlsx(tmp_path, [
            ("discord",  "discord.exe"),
            ("discord",  "discordptb.exe"),
            ("telegram", "telegram.exe"),
        ])
        monkeypatch.setattr(config_manager.data, "platforms_db_path", path)
        load_platforms_db()
        assert set(platforms_svc._platform_app_map["discord"]) == {"discord.exe", "discordptb.exe"}
        assert platforms_svc._platform_app_map["telegram"] == ["telegram.exe"]

    def test_browser_rows_go_to_browser_list_not_platform_map(self, monkeypatch, tmp_path):
        path = _make_xlsx(tmp_path, [("browser", "chrome.exe"), ("browser", "firefox.exe")])
        monkeypatch.setattr(config_manager.data, "platforms_db_path", path)
        load_platforms_db()
        assert "chrome.exe" in platforms_svc._browser_processes
        assert "firefox.exe" in platforms_svc._browser_processes
        assert platforms_svc._platform_app_map == {}

    def test_transit_rows_go_to_transit_list_not_platform_map(self, monkeypatch, tmp_path):
        path = _make_xlsx(tmp_path, [("transit", "explorer.exe")])
        monkeypatch.setattr(config_manager.data, "platforms_db_path", path)
        load_platforms_db()
        assert "explorer.exe" in platforms_svc._transit_processes
        assert platforms_svc._platform_app_map == {}

    def test_missing_columns_leaves_all_globals_empty(self, monkeypatch, tmp_path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["name", "exe"])
        ws.append(["discord", "discord.exe"])
        bad_path = tmp_path / "bad.xlsx"
        wb.save(str(bad_path))
        monkeypatch.setattr(config_manager.data, "platforms_db_path", str(bad_path))
        load_platforms_db()
        assert platforms_svc._platform_app_map == {}
        assert platforms_svc._browser_processes == []
        assert platforms_svc._transit_processes == []

    def test_blank_rows_are_skipped(self, monkeypatch, tmp_path):
        path = _make_xlsx(tmp_path, [("discord", "discord.exe"), ("", ""), ("telegram", "telegram.exe")])
        monkeypatch.setattr(config_manager.data, "platforms_db_path", path)
        load_platforms_db()
        assert "discord" in platforms_svc._platform_app_map
        assert "telegram" in platforms_svc._platform_app_map
        assert "" not in platforms_svc._platform_app_map

    def test_whitespace_only_process_is_skipped(self, monkeypatch, tmp_path):
        path = _make_xlsx(tmp_path, [("discord", "   "), ("discord", "discord.exe")])
        monkeypatch.setattr(config_manager.data, "platforms_db_path", path)
        load_platforms_db()
        assert platforms_svc._platform_app_map["discord"] == ["discord.exe"]

    def test_process_names_normalised_to_lowercase(self, monkeypatch, tmp_path):
        path = _make_xlsx(tmp_path, [("Discord", "Discord.EXE")])
        monkeypatch.setattr(config_manager.data, "platforms_db_path", path)
        load_platforms_db()
        assert "discord" in platforms_svc._platform_app_map
        assert "discord.exe" in platforms_svc._platform_app_map["discord"]

    def test_output_lists_are_sorted(self, monkeypatch, tmp_path):
        path = _make_xlsx(tmp_path, [
            ("discord", "zapp.exe"), ("discord", "aardvark.exe"),
            ("browser", "zzz.exe"),  ("browser", "aaa.exe"),
        ])
        monkeypatch.setattr(config_manager.data, "platforms_db_path", path)
        load_platforms_db()
        assert platforms_svc._platform_app_map["discord"] == ["aardvark.exe", "zapp.exe"]
        assert platforms_svc._browser_processes == ["aaa.exe", "zzz.exe"]


class TestLoadPlatformsDBWithRealFile:
    """Load the actual platforms_db.xlsx and verify the produced structure.
    Skipped automatically if the file is not present.
    """

    @pytest.fixture(autouse=True)
    def _load(self, monkeypatch, platforms_db_path):
        monkeypatch.setattr(platforms_svc, "_platform_app_map", {})
        monkeypatch.setattr(platforms_svc, "_browser_processes", [])
        monkeypatch.setattr(platforms_svc, "_transit_processes", [])
        monkeypatch.setattr(config_manager.data, "platforms_db_path", platforms_db_path)
        load_platforms_db()

    def test_at_least_one_platform_loaded(self):
        assert len(platforms_svc._platform_app_map) >= 1

    def test_browsers_list_non_empty(self):
        assert len(platforms_svc._browser_processes) >= 1

    def test_transit_list_non_empty(self):
        assert len(platforms_svc._transit_processes) >= 1

    def test_all_process_names_are_lowercase(self):
        all_procs = (
            list(platforms_svc._browser_processes)
            + list(platforms_svc._transit_processes)
            + [p for procs in platforms_svc._platform_app_map.values() for p in procs]
        )
        for p in all_procs:
            assert p == p.lower(), f"Process name not lowercase: {p!r}"

    def test_no_empty_process_names(self):
        all_procs = (
            list(platforms_svc._browser_processes)
            + list(platforms_svc._transit_processes)
            + [p for procs in platforms_svc._platform_app_map.values() for p in procs]
        )
        assert all(p for p in all_procs), "Empty process name found"

    def test_platform_map_values_are_sorted(self):
        for platform, procs in platforms_svc._platform_app_map.items():
            assert procs == sorted(procs), f"Processes for {platform!r} are not sorted"
