import math
import pandas as pd


def response_curve(spend: float, roi: float, alpha: float, gamma: float, adstock_rate: float = 0.0) -> float:
    gamma = max(float(gamma), 1.0)
    alpha = max(float(alpha), 0.1)
    adstock_rate = min(max(float(adstock_rate), 0.0), 0.95)

    carryover_multiplier = 1.0 + adstock_rate
    spend_factor = 1 - math.exp(-spend / gamma)

    return spend * roi * spend_factor * carryover_multiplier / alpha


def apply_confidence_band(value: float, confidence_score: float, direction: str) -> float:
    confidence_score = min(max(float(confidence_score), 0.0), 1.0)
    uncertainty = 1.0 - confidence_score

    if direction == "low":
        return value * (1 - 0.35 * uncertainty)
    if direction == "high":
        return value * (1 + 0.35 * uncertainty)
    return value


def run_scenario_model(
    inputs_df: pd.DataFrame,
    bench_df: pd.DataFrame,
    kpi_df: pd.DataFrame,
    scenario_id: str,
) -> pd.DataFrame:
    join_keys = ["category", "market", "channel_group", "channel"]

    df = inputs_df.merge(
        bench_df[
            [
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
        ],
        on=join_keys,
        how="left",
    )

    df = df.merge(kpi_df, on=["category", "market"], how="left")

    missing = df[df["roi_mid"].isna()]
    if not missing.empty:
        missing_rows = (
            missing[["channel_group", "channel"]]
            .drop_duplicates()
            .astype(str)
            .apply(lambda r: f"{r['channel_group']} / {r['channel']}", axis=1)
            .tolist()
        )
        raise ValueError(f"Missing benchmark rows for channels: {', '.join(sorted(missing_rows))}")

    if df["avg_revenue"].isna().any():
        bad = df[df["avg_revenue"].isna()][["category", "market"]].drop_duplicates()
        pairs = bad.astype(str).apply(lambda r: f"{r['category']} / {r['market']}", axis=1).tolist()
        raise ValueError(f"Missing KPI baseline revenue for: {', '.join(sorted(pairs))}")

    results = []

    for _, row in df.iterrows():
        spend = float(row["spend"])
        max_eff = float(row["max_efficient_spend"])
        confidence_score = float(row["confidence_score"])
        avg_revenue = float(row["avg_revenue"])
        adstock_rate = float(row["adstock_rate"])

        raw_low = response_curve(
            spend=spend,
            roi=float(row["roi_low"]),
            alpha=float(row["saturation_alpha"]),
            gamma=float(row["saturation_gamma"]),
            adstock_rate=adstock_rate,
        )
        raw_mid = response_curve(
            spend=spend,
            roi=float(row["roi_mid"]),
            alpha=float(row["saturation_alpha"]),
            gamma=float(row["saturation_gamma"]),
            adstock_rate=adstock_rate,
        )
        raw_high = response_curve(
            spend=spend,
            roi=float(row["roi_high"]),
            alpha=float(row["saturation_alpha"]),
            gamma=float(row["saturation_gamma"]),
            adstock_rate=adstock_rate,
        )

        inc_low = apply_confidence_band(raw_low, confidence_score, "low")
        inc_mid = apply_confidence_band(raw_mid, confidence_score, "mid")
        inc_high = apply_confidence_band(raw_high, confidence_score, "high")

        results.append(
            {
                "scenario_id": scenario_id,
                "created_at": pd.Timestamp.now(tz="UTC"),
                "category": row["category"],
                "market": row["market"],
                "channel_group": row["channel_group"],
                "channel": row["channel"],
                "subchannel": row["subchannel"] if pd.notna(row["subchannel"]) else row["channel"],
                "spend": spend,
                "incremental_revenue_low": round(inc_low, 2),
                "incremental_revenue_mid": round(inc_mid, 2),
                "incremental_revenue_high": round(inc_high, 2),
                "roi_low": float(row["roi_low"]),
                "roi_mid": float(row["roi_mid"]),
                "roi_high": float(row["roi_high"]),
                "saturation_flag": spend > max_eff,
                "baseline_revenue": round(avg_revenue, 2),
                "total_revenue_low": round(avg_revenue + inc_low, 2),
                "total_revenue_mid": round(avg_revenue + inc_mid, 2),
                "total_revenue_high": round(avg_revenue + inc_high, 2),
                "confidence_score": confidence_score,
                "source_label": row["source_label"],
            }
        )

    result_df = pd.DataFrame(results)

    ordered_cols = [
        "scenario_id",
        "created_at",
        "category",
        "market",
        "channel_group",
        "channel",
        "subchannel",
        "spend",
        "incremental_revenue_low",
        "incremental_revenue_mid",
        "incremental_revenue_high",
        "roi_low",
        "roi_mid",
        "roi_high",
        "saturation_flag",
        "baseline_revenue",
        "total_revenue_low",
        "total_revenue_mid",
        "total_revenue_high",
        "confidence_score",
        "source_label",
    ]

    return result_df[ordered_cols]