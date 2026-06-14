"""
Vercel serverless entrypoint.

Vercel's Python runtime executes from the repo root (/var/task), so the
`server/` package directory is not on sys.path by default.  We add it here
before importing anything from the server package.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from server import app  # noqa: E402 — path manipulation must come first
