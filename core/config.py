import os
import json
from pydantic import BaseModel
from typing import Optional

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "config.json")
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "downloads")

class AppConfig(BaseModel):
    # AI Provider Settings
    ai_provider: str = "custom_proxy"  # "gemini", "openai", "deepseek", "claude", "custom_proxy"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = "gpt-4o"
    ai_network_proxy: Optional[str] = None  # e.g. "http://127.0.0.1:7890" or "socks5://..."
    
    # Muse Engine Settings
    concurrency: int = 3
    rotation_mode: str = "round_robin"  # "round_robin", "least_used"
    auto_failover: bool = True
    auto_download: bool = True
    download_dir: str = DOWNLOADS_DIR
    
    # Custom Proxy Presets or Defaults
    custom_headers: Optional[dict] = None

def get_default_config() -> AppConfig:
    return AppConfig()

def load_config() -> AppConfig:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return AppConfig(**data)
        except Exception as e:
            print(f"[Config] Error loading config: {e}")
    cfg = get_default_config()
    save_config(cfg)
    return cfg

def save_config(cfg: AppConfig):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg.model_dump(), f, indent=2, ensure_ascii=False)
