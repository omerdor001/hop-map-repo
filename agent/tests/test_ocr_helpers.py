"""Unit tests for the OCR helpers in agent.py.

Covers:
  * ``_grab_window`` — wraps ``mss.grab`` and respects ``_hwnd_rect`` returning
    ``None`` for minimised windows.
  * ``_ocr_frame``   — converts a raw mss frame to grayscale and forwards it
    to Tesseract with the expected ``--oem 1 --psm 11`` configuration.

These are pure unit tests: every collaborator (``_hwnd_rect``, ``mss``, ``PIL``,
``pytesseract``) is mocked.  No real screenshot is captured and no Tesseract
binary is invoked.
"""
from __future__ import annotations

from unittest.mock import ANY, MagicMock, patch

import pytest

import agent as _agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_frame(width: int = 800, height: int = 600, bgra: bytes = b"\x00" * 16) -> MagicMock:
    """Return a stand-in for an ``mss.ScreenShot`` exposing only ``size`` and ``bgra``."""
    raw = MagicMock(name="ScreenShot")
    raw.size = (width, height)
    raw.bgra = bgra
    return raw


# ---------------------------------------------------------------------------
# _grab_window
# ---------------------------------------------------------------------------


class TestGrabWindow:

    def test_returns_none_when_window_minimised(self):
        """When ``_hwnd_rect`` returns ``None`` (minimised window) we must not
        call ``sct.grab`` and must propagate ``None`` to the caller."""
        sct = MagicMock(name="mss")
        with patch.object(_agent, "_hwnd_rect", return_value=None) as mock_rect:
            result = _agent._grab_window(hwnd=1234, sct=sct)

        assert result is None
        mock_rect.assert_called_once_with(1234)
        sct.grab.assert_not_called()

    def test_passes_correct_region_to_mss_grab(self):
        """The ``(left, top, w, h)`` tuple from ``_hwnd_rect`` must be forwarded
        to ``sct.grab`` as the standard mss region dict."""
        sct = MagicMock(name="mss")
        sct.grab.return_value = "fake-frame"

        with patch.object(_agent, "_hwnd_rect", return_value=(100, 200, 800, 600)):
            result = _agent._grab_window(hwnd=1, sct=sct)

        sct.grab.assert_called_once_with(
            {"left": 100, "top": 200, "width": 800, "height": 600}
        )
        assert result == "fake-frame"


# ---------------------------------------------------------------------------
# _ocr_frame
# ---------------------------------------------------------------------------


class TestOcrFrame:

    def test_builds_grayscale_image_from_raw_bgra(self):
        """``Image.frombytes`` must be called with the BGRA buffer in
        ``"raw", "BGRX"`` mode and the resulting image converted to ``"L"``
        (grayscale) before reaching Tesseract."""
        raw = _make_raw_frame(width=1920, height=1080, bgra=b"\xff" * 32)
        rgb_img = MagicMock(name="rgb-image")
        gray_img = MagicMock(name="gray-image")
        rgb_img.convert.return_value = gray_img

        with (
            patch.object(_agent, "Image") as mock_image,
            patch.object(_agent, "pytesseract") as mock_tess,
        ):
            mock_image.frombytes.return_value = rgb_img
            mock_tess.image_to_string.return_value = "ignored"

            _agent._ocr_frame(raw)

        mock_image.frombytes.assert_called_once_with(
            "RGB", (1920, 1080), b"\xff" * 32, "raw", "BGRX"
        )
        rgb_img.convert.assert_called_once_with("L")
        # Tesseract must receive the grayscale image, not the RGB one.
        mock_tess.image_to_string.assert_called_once_with(gray_img, config=ANY)

    def test_invokes_tesseract_with_expected_config(self):
        """OCR engine mode 1 + page-segmentation mode 11 (sparse text) is the
        contract; changing it would alter detection behaviour and must be a
        deliberate, reviewed change."""
        raw = _make_raw_frame()
        with (
            patch.object(_agent, "Image") as mock_image,
            patch.object(_agent, "pytesseract") as mock_tess,
        ):
            mock_image.frombytes.return_value.convert.return_value = MagicMock()
            mock_tess.image_to_string.return_value = ""

            _agent._ocr_frame(raw)

        mock_tess.image_to_string.assert_called_once_with(
            ANY, config="--oem 1 --psm 11"
        )

    def test_returns_text_from_tesseract_unchanged(self):
        """The function must return Tesseract's output verbatim — no stripping,
        normalisation, or post-processing."""
        raw = _make_raw_frame()
        with (
            patch.object(_agent, "Image") as mock_image,
            patch.object(_agent, "pytesseract") as mock_tess,
        ):
            mock_image.frombytes.return_value.convert.return_value = MagicMock()
            mock_tess.image_to_string.return_value = "  Visit https://x.com/a  \n"

            result = _agent._ocr_frame(raw)

        assert result == "  Visit https://x.com/a  \n"

    def test_propagates_exceptions_from_tesseract(self):
        """``_ocr_frame`` must not swallow exceptions raised by Tesseract.

        The function deliberately has no ``try/except`` — the caller
        (:func:`_scanner_loop`) is responsible for distinguishing fatal
        errors (``TesseractNotFoundError`` → stop) from transient ones
        (→ retry on next tick).  Hiding errors here would break that
        contract and cause silent infinite retry on a broken install.
        """
        raw = _make_raw_frame()
        with (
            patch.object(_agent, "Image") as mock_image,
            patch.object(_agent, "pytesseract") as mock_tess,
        ):
            mock_image.frombytes.return_value.convert.return_value = MagicMock()
            mock_tess.image_to_string.side_effect = RuntimeError("tesseract crashed")

            with pytest.raises(RuntimeError, match="tesseract crashed"):
                _agent._ocr_frame(raw)
