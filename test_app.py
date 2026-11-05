"""Standalone test runner for MUSE AI MV Studio.

Usage:
    python test_app.py              # run the full E2E suite
    python test_app.py -k stitch    # run a subset
    python test_app.py --fast       # skip the slow network image test

The runner uses the project's virtualenv when available, installs pytest on
demand, and exits non-zero if any scenario fails.
"""

import os
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent
TEST_FILE = PROJECT_ROOT / "tests" / "test_full_workflow.py"


def _python_executable() -> str:
    """Prefer the project venv so dependencies match the running app."""
    candidates = [
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _ensure_pytest(python: str) -> bool:
    check = subprocess.run(
        [python, "-c", "import pytest"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if check.returncode == 0:
        return True
    print("[test_app] pytest chưa được cài — đang cài đặt...")
    install = subprocess.run(
        [python, "-m", "pip", "install", "pytest", "--quiet"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if install.returncode != 0:
        print("[test_app] Không cài được pytest:\n" + (install.stderr or "")[-800:])
        return False
    return True


def main() -> int:
    python = _python_executable()
    print(f"[test_app] Python: {python}")

    if not _ensure_pytest(python):
        return 2

    if not TEST_FILE.exists():
        print(f"[test_app] Không tìm thấy file test: {TEST_FILE}")
        return 2

    args = sys.argv[1:]
    cmd = [python, "-m", "pytest", str(TEST_FILE), "-v", "--tb=short", "-p", "no:cacheprovider"]
    cmd.extend(args)

    print("[test_app] Chạy bộ kiểm thử E2E...\n")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    print()
    if result.returncode == 0:
        print("=" * 70)
        print("  ✅ TOÀN BỘ KỊCH BẢN ĐẠT 100% PASS")
        print("=" * 70)
    else:
        print("=" * 70)
        print("  ❌ CÓ KỊCH BẢN THẤT BẠI — xem log phía trên")
        print("=" * 70)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
