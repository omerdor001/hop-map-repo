import logging
import os

from config import config_manager

log = logging.getLogger(__name__)

_platform_app_map: dict[str, list[str]] = {}
_browser_processes: list[str] = []
_transit_processes: list[str] = []


def load_platforms_db() -> None:
    import openpyxl

    excel_path = config_manager.data.platforms_db_path
    if not excel_path or not os.path.exists(excel_path):
        log.warning("Platforms DB not found at %r — agents will use built-in defaults.", excel_path)
        return

    try:
        workbook = openpyxl.load_workbook(excel_path, read_only=True)
        try:
            worksheet = workbook.active
            platform_col = process_col = None
            for cell in worksheet[1]:
                if cell.value:
                    name = str(cell.value).strip().lower()
                    if name == "platform":
                        platform_col = cell.column - 1
                    elif name == "process":
                        process_col = cell.column - 1

            if platform_col is None or process_col is None:
                log.warning("Platforms DB missing 'platform' or 'process' column — skipping.")
                return

            platforms: dict[str, set[str]] = {}
            browsers: set[str] = set()
            transits: set[str] = set()

            for row in worksheet.iter_rows(min_row=2, values_only=True):
                if not row:
                    continue
                plat = row[platform_col] if platform_col < len(row) else None
                proc = row[process_col] if process_col < len(row) else None
                if not plat or not proc:
                    continue
                plat = str(plat).strip().lower()
                proc = str(proc).strip().lower()
                if not plat or not proc:
                    continue
                if plat == "browser":
                    browsers.add(proc)
                elif plat == "transit":
                    transits.add(proc)
                else:
                    platforms.setdefault(plat, set()).add(proc)
        finally:
            workbook.close()

        global _platform_app_map, _browser_processes, _transit_processes
        _platform_app_map = {k: sorted(v) for k, v in platforms.items()}
        _browser_processes = sorted(browsers)
        _transit_processes = sorted(transits)

        log.info(
            "Loaded %d platforms, %d browsers, %d transit processes from %s",
            len(_platform_app_map), len(_browser_processes), len(_transit_processes), excel_path,
        )
    except Exception as exc:
        log.warning("Failed to load platforms DB: %s — agents will use built-in defaults.", exc)
        _platform_app_map.clear()
        _browser_processes.clear()
        _transit_processes.clear()


def get_platforms() -> dict:
    return {
        "platforms": _platform_app_map,
        "browsers": _browser_processes,
        "transit": _transit_processes,
    }
