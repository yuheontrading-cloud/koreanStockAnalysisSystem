"""Load config from config.yaml and .env."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

_config = None


def load_config():
    global _config
    if _config is None:
        config_path = PROJECT_ROOT / "config" / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            _config = yaml.safe_load(f)
        # Replace numeric literals in YAML (e.g. 5_000_000 is read as int 5000000)
        for key in ("min_volume", "min_trading_value"):
            if key in _config.get("screener", {}):
                val = _config["screener"][key]
                if isinstance(val, str) and "_" in val:
                    _config["screener"][key] = int(val.replace("_", ""))
    return _config


def get_naver_credentials():
    return {
        "client_id": os.getenv("NAVER_CLIENT_ID", "").strip(),
        "client_secret": os.getenv("NAVER_CLIENT_SECRET", "").strip(),
    }
