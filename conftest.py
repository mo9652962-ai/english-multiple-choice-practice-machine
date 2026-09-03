"""Pytest path setup for the repository-wide test suite.

The backend is an importable package whose modules also use ``app`` as their
top-level package name.  Keep both the repository root (for ``tools``) and
``backend`` (for ``app``) on sys.path so the documented root-level pytest
command works without a shell-specific PYTHONPATH.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"

for path in (ROOT_DIR, BACKEND_DIR):
    path_string = str(path)
    if path_string not in sys.path:
        sys.path.insert(0, path_string)
