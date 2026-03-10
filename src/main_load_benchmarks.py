from pathlib import Path

import pandas as pd

from src.config import load_settings
from src.bq import get_client, load_dataframe


def main() -> None:
    cfg = load_settings()
    client = get_client(cfg["project_id"])

    csv_path = Path("config/benchmark_channel_curves.csv")
    if not csv_path.exists():
        raise FileNotFoundError(f"Benchmark CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    required_cols = [
        "category",
        "market",
        "channel_group",
        "channel",
        "subchannel",
        "roi_low",
        "roi_mid",
        "roi_high",
        "adstock_rate",
        "saturation_alpha",
        "saturation_gamma",
        "max_efficient_spend",
        "confidence_score",
        "source_label",
        "suggested_spend",
    ]

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required benchmark columns: {', '.join(missing)}")

    for col in [
        "roi_low",
        "roi_mid",
        "roi_high",
        "adstock_rate",
        "saturation_alpha",
        "saturation_gamma",
        "max_efficient_spend",
        "confidence_score",
        "suggested_spend",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df[required_cols].isna().any().any():
        bad_cols = df[required_cols].columns[df[required_cols].isna().any()].tolist()
        raise ValueError(f"Benchmark CSV has blank/invalid values in: {', '.join(bad_cols)}")

    table = f'{cfg["project_id"]}.{cfg["dataset"]}.benchmark_channel_curves'
    load_dataframe(client, df[required_cols], table, write_disposition="WRITE_TRUNCATE")

    print(f"Loaded {len(df)} benchmark rows into {table}")


if __name__ == "__main__":
    main()