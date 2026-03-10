import pandas as pd

from src.config import load_settings
from src.bq import get_client, load_dataframe, run_query
from src.generators import generate_media_spend_and_kpis


def get_category_market_pairs(project_id: str, dataset: str, client) -> pd.DataFrame:
    query = f"""
    SELECT DISTINCT category, market
    FROM `{project_id}.{dataset}.benchmark_channel_curves`
    ORDER BY category, market
    """
    return run_query(client, query)


def get_channel_defaults(project_id: str, dataset: str, client, category: str, market: str) -> dict:
    query = f"""
    SELECT channel, suggested_spend
    FROM `{project_id}.{dataset}.benchmark_channel_curves`
    WHERE category = '{category}'
      AND market = '{market}'
    """
    df = run_query(client, query)

    if df.empty:
        return {}

    channel_cfg = {}
    for _, row in df.iterrows():
        channel_cfg[str(row["channel"])] = {
            "base_spend": float(row["suggested_spend"]),
            "seasonality": 0.15,
            "ctr": 0.015,
            "impression_multiplier": 100.0,
        }

    return channel_cfg


def main() -> None:
    cfg = load_settings()
    client = get_client(cfg["project_id"])

    pairs_df = get_category_market_pairs(cfg["project_id"], cfg["dataset"], client)
    if pairs_df.empty:
        raise ValueError(
            "No category/market pairs found in benchmark_channel_curves. "
            "Run python -m src.main_load_benchmarks first."
        )

    all_spend = []
    all_kpis = []

    for _, pair in pairs_df.iterrows():
        category = str(pair["category"])
        market = str(pair["market"])

        channels = get_channel_defaults(
            cfg["project_id"],
            cfg["dataset"],
            client,
            category,
            market,
        )

        if not channels:
            continue

        spend_df, kpi_df = generate_media_spend_and_kpis(
            start_date=cfg["start_date"],
            weeks=cfg["weeks"],
            category=category,
            market=market,
            channels=channels,
        )

        all_spend.append(spend_df)
        all_kpis.append(kpi_df)

    if not all_spend or not all_kpis:
        raise ValueError("No demo data was generated. Check benchmark_channel_curves contents.")

    spend_df = pd.concat(all_spend, ignore_index=True)
    kpi_df = pd.concat(all_kpis, ignore_index=True)

    spend_table = f'{cfg["project_id"]}.{cfg["dataset"]}.demo_media_spend'
    kpi_table = f'{cfg["project_id"]}.{cfg["dataset"]}.demo_business_kpis'

    load_dataframe(client, spend_df, spend_table, write_disposition="WRITE_TRUNCATE")
    load_dataframe(client, kpi_df, kpi_table, write_disposition="WRITE_TRUNCATE")

    print(
        f"Demo media spend and KPI tables loaded. "
        f"Rows: spend={len(spend_df)}, kpi={len(kpi_df)}"
    )


if __name__ == "__main__":
    main()