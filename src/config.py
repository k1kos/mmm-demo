import json
import os
from pathlib import Path

import streamlit as st
import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "settings.yaml"


def _get_streamlit_secret(key: str):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        return None
    return None


def get_secret(key: str, default=None):
    value = os.getenv(key)
    if value not in (None, ""):
        return value

    streamlit_value = _get_streamlit_secret(key)
    if streamlit_value not in (None, ""):
        return streamlit_value

    return default


def get_gcp_service_account_info() -> dict | None:
    try:
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
    except Exception:
        pass

    raw_json = get_secret("GOOGLE_CREDENTIALS_JSON")
    if raw_json:
        return json.loads(raw_json)

    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if credentials_path:
        path = Path(credentials_path)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))

    for candidate in ROOT.glob("*.json"):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if payload.get("type") == "service_account":
            return payload

    return None


def load_settings() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg["project_id"] = get_secret("GOOGLE_CLOUD_PROJECT", cfg.get("project_id", ""))
    cfg["dataset"] = get_secret("BQ_DATASET", cfg.get("dataset", "mmm_demo"))
    cfg["default_category"] = get_secret("DEFAULT_CATEGORY", cfg.get("default_category", "Retail"))
    cfg["default_market"] = get_secret("DEFAULT_MARKET", cfg.get("default_market", "US"))
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
