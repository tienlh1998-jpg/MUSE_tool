"""Pytest configuration and session-wide test isolation for MUSE AI Studio."""

import os
import tempfile
from pathlib import Path

# Set up isolated temporary directories before any application module is imported
if "MUSE_DATA_DIR" not in os.environ:
    _TEMP_ROOT = tempfile.mkdtemp(prefix="muse_pytest_iso_")
    os.environ["MUSE_DATA_DIR"] = _TEMP_ROOT
    os.environ["MUSE_DOWNLOADS_DIR"] = os.path.join(_TEMP_ROOT, "downloads")
