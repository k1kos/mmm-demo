import json
import os
from typing import Any

import pandas as pd
from openai import OpenAI


def _format_channel_rows(channel_df: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for _, row in channel_df.iterrows():
        rows.append(
            {
                "channel_group": str(row.get("channel_group", "")),
                "channel": str(row.get("channel", "")),
                "spend": float(row.get("spend", 0.0)),
                "incremental_revenue_mid": float(row.get("incremental_revenue_mid", 0.0)),
                "roi_mid": float(row.get("roi_mid", 0.0)),
                "saturation_flag": bool(row.get("saturation_flag", False)),
            }
        )
    return rows


def build_ai_payload(
    category: str,
    market: str,
    summary_df: pd.DataFrame,
    channel_df: pd.DataFrame,
    history_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    if summary_df.empty:
        raise ValueError("summary_df is empty")

    summary = summary_df.iloc[0]

    payload = {
        "category": category,
        "market": market,
        "scenario": {
            "scenario_id": str(summary.get("scenario_id", "")),
            "total_spend": float(summary.get("total_spend", 0.0)),
            "incremental_revenue_mid": float(summary.get("incremental_revenue_mid", 0.0)),
            "total_revenue_mid": float(summary.get("total_revenue_mid", 0.0)),
            "projected_profit_mid": float(summary.get("total_revenue_mid", 0.0))
            - float(summary.get("total_spend", 0.0)),
        },
        "channels": _format_channel_rows(channel_df),
    }

    if history_df is not None and not history_df.empty:
        history_cols = [
            c
            for c in [
                "scenario_id",
                "total_spend",
                "projected_profit_mid",
                "profit_change_vs_first_pct",
                "created_at",
            ]
            if c in history_df.columns
        ]
        payload["history"] = history_df[history_cols].head(10).to_dict(orient="records")

    return payload


def generate_ai_insights(payload: dict[str, Any], model: str = "gpt-5.4") -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing")

    client = OpenAI(api_key=api_key)

    instructions = (
        "You are a marketing effectiveness analyst helping a user interpret a benchmark-based media mix scenario. "
        "Use only the provided data. Do not invent numbers. "
        "This is not a true MMM or forecast, so describe results as directional and benchmark-based. "
        "Return concise markdown with exactly these sections: "
        "1) Key insights, 2) Risks, 3) Suggested next tests. "
        "In Key insights, give 3 short bullets. "
        "In Risks, give 2 short bullets. "
        "In Suggested next tests, give 2 short bullets. "
        "Call out saturated channels if present. "
        "Mention profit impact, not revenue impact, when discussing scenario change."
    )

    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=f"Analyze this scenario payload:\n\n{json.dumps(payload, indent=2, default=str)}",
    )

    return response.output_text.strip()
