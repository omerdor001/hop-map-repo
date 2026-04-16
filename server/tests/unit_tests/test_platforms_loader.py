"""
Unit tests for _load_platforms_db().

All tests are fully in-process — no server, no HTTP.
Temporary Excel files are built with openpyxl and written to pytest's tmp_path.
The module-level globals (_platform_app_map, _browser_processes, _transit_processes)
are reset before each test via an autouse monkeypatch fixture so tests are
independent of each other and of the server's lifespan startup.
"""

import pytest
import openpyxl

import server as _server_module
from server import _load_platforms_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_xlsx(tmp_path, rows: list[tuple[str, str]]) -> str:
    """Write a minimal platforms xlsx to tmp_path and return its path string."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["platform", "process"])
    for platform, process in rows:
        ws.append([platform, process])
    path = tmp_path / "platforms_test.xlsx"
    wb.save(str(path))
    return str(path)


# ---------------------------------------------------------------------------
# Core loading behaviour
# ---------------------------------------------------------------------------

class TestLoadPlatformsDB:
    """Pure unit tests: each test builds its own xlsx, calls the loader,
    and verifies the resulting module-level globals."""

    @pytest.fixture(autouse=True)
    def _reset_platform_globals(self, monkeypatch):
        """Guarantee clean globals before every test in this class.
        monkeypatch restores the original values at teardown even if the test
        fails mid-way, so no manual cleanup is needed in each test.
        """
        monkeypatch.setattr(_server_module, "_platform_app_map",  {})
        monkeypatch.setattr(_server_module, "_browser_processes",  [])
        monkeypatch.setattr(_server_module, "_transit_processes",  [])

    def test_missing_file_leaves_globals_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            _server_module.config_manager.data, "platforms_db_path",
            str(tmp_path / "nonexistent.xlsx"),
        )
        _load_platforms_db()
        assert _server_module._platform_app_map  == {}
        assert _server_module._browser_processes == []
        assert _server_module._transit_processes == []

    def test_platform_rows_loaded_into_map(self, monkeypatch, tmp_path):
        path = _make_xlsx(tmp_path, [
            ("discord",  "discord.exe"),
            ("discord",  "discordptb.exe"),
            ("telegram", "telegram.exe"),
        ])
        monkeypatch.setattr(_server_module.config_manager.data, "platforms_db_path", path)
        _load_platforms_db()

        assert set(_server_module._platform_app_map["discord"]) == {"discord.exe", "discordptb.exe"}
        assert _server_module._platform_app_map["telegram"] == ["telegram.exe"]

    def test_browser_rows_go_to_browser_list_not_platform_map(self, monkeypatch, tmp_path):
        path = _make_xlsx(tmp_path, [
            ("browser", "chrome.exe"),
            ("browser", "firefox.exe"),
        ])
        monkeypatch.setattr(_server_module.config_manager.data, "platforms_db_path", path)
        _load_platforms_db()

        assert "chrome.exe"  in _server_module._browser_processes
        assert "firefox.exe" in _server_module._browser_processes
        assert _server_module._platform_app_map == {}   # not mixed into platform map

    def test_transit_rows_go_to_transit_list_not_platform_map(self, monkeypatch, tmp_path):
        path = _make_xlsx(tmp_path, [
            ("transit", "explorer.exe"),
        ])
        monkeypatch.setattr(_server_module.config_manager.data, "platforms_db_path", path)
        _load_platforms_db()

        assert "explorer.exe" in _server_module._transit_processes
        assert _server_module._platform_app_map == {}

    def test_missing_columns_leaves_all_globals_empty(self, monkeypatch, tmp_path):
        """An xlsx with wrong column headers must not crash and must leave all globals empty."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["name", "exe"])           # wrong column names
        ws.append(["discord", "discord.exe"])
        bad_path = tmp_path / "bad.xlsx"
        wb.save(str(bad_path))

        monkeypatch.setattr(_server_module.config_manager.data, "platforms_db_path", str(bad_path))
        _load_platforms_db()

        assert _server_module._platform_app_map  == {}
        assert _server_module._browser_processes == []
        assert _server_module._transit_processes == []

    def test_blank_rows_are_skipped(self, monkeypatch, tmp_path):
        path = _make_xlsx(tmp_path, [
            ("discord",  "discord.exe"),
            ("",          ""),            # blank row
            ("telegram", "telegram.exe"),
        ])
        monkeypatch.setattr(_server_module.config_manager.data, "platforms_db_path", path)
        _load_platforms_db()

        assert "discord"  in _server_module._platform_app_map
        assert "telegram" in _server_module._platform_app_map
        assert "" not in _server_module._platform_app_map

    def test_whitespace_only_process_is_skipped(self, monkeypatch, tmp_path):
        """A process cell containing only whitespace must be stripped and skipped.
        The function has a second 'if not proc' guard after .strip() for this case.
        """
        path = _make_xlsx(tmp_path, [
            ("discord", "   "),          # whitespace-only → stripped to "" → skipped
            ("discord", "discord.exe"),
        ])
        monkeypatch.setattr(_server_module.config_manager.data, "platforms_db_path", path)
        _load_platforms_db()

        assert _server_module._platform_app_map["discord"] == ["discord.exe"]

    def test_process_names_normalised_to_lowercase(self, monkeypatch, tmp_path):
        path = _make_xlsx(tmp_path, [
            ("Discord", "Discord.EXE"),
        ])
        monkeypatch.setattr(_server_module.config_manager.data, "platforms_db_path", path)
        _load_platforms_db()

        assert "discord"     in _server_module._platform_app_map
        assert "discord.exe" in _server_module._platform_app_map["discord"]

    def test_output_lists_are_sorted(self, monkeypatch, tmp_path):
        """Process lists and platform map values must be sorted for deterministic output."""
        path = _make_xlsx(tmp_path, [
            ("discord", "zapp.exe"),
            ("discord", "aardvark.exe"),
            ("browser", "zzz.exe"),
            ("browser", "aaa.exe"),
        ])
        monkeypatch.setattr(_server_module.config_manager.data, "platforms_db_path", path)
        _load_platforms_db()

        assert _server_module._platform_app_map["discord"] == ["aardvark.exe", "zapp.exe"]
        assert _server_module._browser_processes == ["aaa.exe", "zzz.exe"]


# ---------------------------------------------------------------------------
# Integration with the real Excel file
# ---------------------------------------------------------------------------

class TestLoadPlatformsDBWithRealFile:
    """Load the actual platforms_db.xlsx and verify the produced structure.

    Skipped automatically if the file is not present.
    Uses _load_platforms_db() (the production loader) so this also exercises
    the full code path including file I/O.
    """

    @pytest.fixture(autouse=True)
    def _load(self, monkeypatch, platforms_db_path):
        monkeypatch.setattr(_server_module, "_platform_app_map",  {})
        monkeypatch.setattr(_server_module, "_browser_processes",  [])
        monkeypatch.setattr(_server_module, "_transit_processes",  [])
        monkeypatch.setattr(_server_module.config_manager.data, "platforms_db_path", platforms_db_path)
        # _load_platforms_db() rebinds the module globals; monkeypatch restores at teardown.
        _load_platforms_db()

    def test_at_least_one_platform_loaded(self):
        assert len(_server_module._platform_app_map) >= 1

    def test_browsers_list_non_empty(self):
        assert len(_server_module._browser_processes) >= 1

    def test_transit_list_non_empty(self):
        assert len(_server_module._transit_processes) >= 1

    def test_all_process_names_are_lowercase(self):
        all_procs = (
            list(_server_module._browser_processes)
            + list(_server_module._transit_processes)
            + [p for procs in _server_module._platform_app_map.values() for p in procs]
        )
        for p in all_procs:
            assert p == p.lower(), f"Process name not lowercase: {p!r}"

    def test_no_empty_process_names(self):
        all_procs = (
            list(_server_module._browser_processes)
            + list(_server_module._transit_processes)
            + [p for procs in _server_module._platform_app_map.values() for p in procs]
        )
        assert all(p for p in all_procs), "Empty process name found"

    def test_platform_map_values_are_sorted(self):
        for platform, procs in _server_module._platform_app_map.items():
            assert procs == sorted(procs), f"Processes for {platform!r} are not sorted"
