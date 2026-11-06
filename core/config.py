"""Application configuration and filesystem layout.

All user data lives under ``data/`` so the project can be cloned and run
without mixing generated media with source files.  The ``MUSE_DATA_DIR``
environment variable lets the automated test suite point the whole app at an
isolated temporary directory.
"""

import json
import os
import shutil
from typing import Optional

from pydantic import BaseModel

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# An explicit override is used by the E2E test-suite.  When it is present we
# never touch the developer's real data or legacy downloads folder.
IS_ISOLATED = bool(os.environ.get("MUSE_DATA_DIR"))

DATA_DIR = os.path.abspath(
    os.environ.get("MUSE_DATA_DIR", os.path.join(BASE_DIR, "data"))
)
DOWNLOADS_DIR = os.path.abspath(
    os.environ.get("MUSE_DOWNLOADS_DIR", os.path.join(DATA_DIR, "downloads"))
)
IMAGES_DIR = os.path.join(DOWNLOADS_DIR, "images")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# Pre-V3.1 builds stored renders in ``<project>/downloads``.  They are migrated
# once on startup so old project URLs such as ``/downloads/muse_xxx.mp4`` keep
# working after the media root moved under ``data/``.
LEGACY_DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")


class AppConfig(BaseModel):
    # AI provider used by the MV Director and by the image engine.
    ai_provider: str = "custom_proxy"  # "gemini", "openai", "custom_proxy"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = "gpt-4o"
    # Optional dedicated model for image generation.  When empty the engine
    # derives a sensible default from the provider (imagen-3.0 / dall-e-3).
    ai_image_model: str = ""
    ai_network_proxy: Optional[str] = None  # e.g. "http://127.0.0.1:7890"

    # Zero-config fallback that generates images without an API key.
    # Disabled by default for users to prevent Pollinations 503; active in isolated test mode.
    free_image_fallback: bool = True if IS_ISOLATED else False

    # Video rendering behavior: When True, disallow silent fallback to static FFmpeg camera zooms.
    strict_ai_video: bool = False if IS_ISOLATED else True

    # Muse Engine settings
    concurrency: int = 1
    rotation_mode: str = "round_robin"  # "round_robin", "least_used"
    auto_failover: bool = True
    auto_download: bool = True
    download_dir: str = DOWNLOADS_DIR
    muse_gateway_url: Optional[str] = None

    # Optional extra headers for custom reverse proxies.
    custom_headers: Optional[dict] = None


def get_default_config() -> AppConfig:
    return AppConfig()


def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)


def migrate_legacy_downloads():
    """Move renders from the old ``<project>/downloads`` folder into data/.

    The operation is intentionally conservative: existing destination files are
    never overwritten and files are moved (not deleted).  It is skipped entirely
    in isolated test mode.
    """
    if IS_ISOLATED:
        return
    if os.path.abspath(LEGACY_DOWNLOADS_DIR) == os.path.abspath(DOWNLOADS_DIR):
        return
    if not os.path.isdir(LEGACY_DOWNLOADS_DIR):
        return

    _ensure_dirs()
    for root, _dirs, files in os.walk(LEGACY_DOWNLOADS_DIR):
        rel = os.path.relpath(root, LEGACY_DOWNLOADS_DIR)
        dest_root = DOWNLOADS_DIR if rel == "." else os.path.join(DOWNLOADS_DIR, rel)
        os.makedirs(dest_root, exist_ok=True)
        for name in files:
            if name in (".gitkeep", "all_renders.zip"):
                continue
            src = os.path.join(root, name)
            dst = os.path.join(dest_root, name)
            if os.path.exists(dst):
                continue
            try:
                shutil.move(src, dst)
            except Exception as exc:  # pragma: no cover - best effort migration
                print(f"[Config] Không thể di chuyển {src}: {exc}")


def load_config() -> AppConfig:
    _ensure_dirs()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = AppConfig(**data)
            # Normalise a stale path saved by an older build.
            legacy = os.path.abspath(str(cfg.download_dir or ""))
            if not cfg.download_dir or legacy == os.path.abspath(LEGACY_DOWNLOADS_DIR):
                cfg.download_dir = DOWNLOADS_DIR
            os.makedirs(cfg.download_dir, exist_ok=True)
            os.makedirs(os.path.join(cfg.download_dir, "images"), exist_ok=True)
            return cfg
        except Exception as exc:
            print(f"[Config] Error loading config: {exc}")

    cfg = get_default_config()
    save_config(cfg)
    return cfg


def save_config(cfg: AppConfig):
    _ensure_dirs()
    tmp_path = CONFIG_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cfg.model_dump(), f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, CONFIG_FILE)
