from pathlib import Path
import os
import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "settings.yaml"


def load_settings() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg["project_id"] = os.getenv("GOOGLE_CLOUD_PROJECT", cfg.get("project_id", ""))
    cfg["dataset"] = os.getenv("BQ_DATASET", cfg.get("dataset", "mmm_demo"))
    cfg["default_category"] = os.getenv("DEFAULT_CATEGORY", cfg.get("default_category", "Retail"))
    cfg["default_market"] = os.getenv("DEFAULT_MARKET", cfg.get("default_market", "US"))
    cfg["start_date"] = cfg.get("start_date", "2024-01-01")
    cfg["weeks"] = int(cfg.get("weeks", 52))

    if not cfg["project_id"]:
        raise ValueError(
            "Missing project_id. Set GOOGLE_CLOUD_PROJECT in .env or config/settings.yaml"
        )

    if not cfg["dataset"]:
        raise ValueError(
            "Missing dataset. Set BQ_DATASET in .env or config/settings.yaml"
        )

    return cfg