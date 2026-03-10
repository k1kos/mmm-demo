from datetime import datetime, timezone
from typing import List

import pandas as pd

from src.bq import get_client, load_dataframe, run_query
from src.config import load_settings
from src.model import run_scenario_model


def _get_cfg():
    return load_settings()


def _get_client():
    cfg = _get_cfg()
    return get_client(cfg["project_id"])


def get_available_categories() -> List[str]:
    cfg = _get_cfg()
    client = _get_client()

    query = f"""
    SELECT DISTINCT category
    FROM `{cfg["project_id"]}.{cfg["dataset"]}.benchmark_channel_curves`
    ORDER BY category
    """
    df = run_query(client, query)
    return df["category"].dropna().astype(str).tolist()


def get_available_markets() -> List[str]:
    cfg = _get_cfg()
    client = _get_client()

    query = f"""
    SELECT DISTINCT market
    FROM `{cfg["project_id"]}.{cfg["dataset"]}.benchmark_channel_curves`
    ORDER BY market
    """
    df = run_query(client, query)
    return df["market"].dropna().astype(str).tolist()


def get_benchmark_rows(category: str, market: str) -> pd.DataFrame:
    cfg = _get_cfg()
    client = _get_client()

    query = f"""
    SELECT
      category,
      market,
      channel_group,
      channel,
      subchannel,
      roi_low,
      roi_mid,
      roi_high,
      adstock_rate,
      saturation_alpha,
      saturation_gamma,
      max_efficient_spend,
      confidence_score,
      source_label,
      suggested_spend
    FROM `{cfg["project_id"]}.{cfg["dataset"]}.benchmark_channel_curves`
    WHERE category = '{category}'
      AND market = '{market}'
    ORDER BY channel_group, channel, subchannel
    """
    return run_query(client, query)


def _get_avg_revenue_by_category_market() -> pd.DataFrame:
    cfg = _get_cfg()
    client = _get_client()

    query = f"""
    SELECT
      category,
      market,
      AVG(revenue) AS avg_revenue
    FROM `{cfg["project_id"]}.{cfg["dataset"]}.demo_business_kpis`
    GROUP BY 1,2
    """
    return run_query(client, query)


def _get_benchmarks_for_category_market(category: str, market: str) -> pd.DataFrame:
    cfg = _get_cfg()
    client = _get_client()

    query = f"""
    SELECT
      category,
      market,
      channel_group,
      channel,
      subchannel,
      roi_low,
      roi_mid,
      roi_high,
      adstock_rate,
      saturation_alpha,
      saturation_gamma,
      max_efficient_spend,
      confidence_score,
      source_label,
      suggested_spend
    FROM `{cfg["project_id"]}.{cfg["dataset"]}.benchmark_channel_curves`
    WHERE category = '{category}'
      AND market = '{market}'
    """
    return run_query(client, query)


def save_scenario_inputs(inputs_df: pd.DataFrame) -> None:
    cfg = _get_cfg()
    client = _get_client()

    df = inputs_df.copy()
    df["created_at"] = pd.Timestamp.now(tz="UTC")

    expected_cols = [
        "scenario_id",
        "created_at",
        "category",
        "market",
        "channel_group",
        "channel",
        "spend",
    ]

    for col in expected_cols:
        if col not in df.columns:
            if col == "created_at":
                df[col] = pd.Timestamp.now(tz="UTC")
            else:
                df[col] = None

    df = df[expected_cols]

    table = f'{cfg["project_id"]}.{cfg["dataset"]}.scenario_inputs'
    load_dataframe(client, df, table, write_disposition="WRITE_APPEND")


def run_and_store_scenario(inputs_df: pd.DataFrame) -> str:
    if inputs_df.empty:
        raise ValueError("inputs_df is empty")

    required = {"scenario_id", "category", "market", "channel_group", "channel", "spend"}
    missing = required - set(inputs_df.columns)
    if missing:
        raise ValueError(f"Missing required input columns: {', '.join(sorted(missing))}")

    category = str(inputs_df["category"].iloc[0])
    market = str(inputs_df["market"].iloc[0])
    scenario_id = str(inputs_df["scenario_id"].iloc[0])

    if inputs_df["scenario_id"].nunique() != 1:
        raise ValueError("inputs_df must contain exactly one scenario_id")

    if inputs_df["category"].nunique() != 1 or inputs_df["market"].nunique() != 1:
        raise ValueError("inputs_df must contain exactly one category and one market")

    save_scenario_inputs(inputs_df)

    bench_df = _get_benchmarks_for_category_market(category, market)
    if bench_df.empty:
        raise ValueError(f"No benchmark rows found for category={category}, market={market}")

    kpi_df = _get_avg_revenue_by_category_market()

    model_inputs_df = inputs_df.copy()

    result_df = run_scenario_model(
        inputs_df=model_inputs_df,
        bench_df=bench_df,
        kpi_df=kpi_df,
        scenario_id=scenario_id,
    )

    result_df["created_at"] = pd.to_datetime(result_df["created_at"], utc=True)

    cfg = _get_cfg()
    client = _get_client()
    result_table = f'{cfg["project_id"]}.{cfg["dataset"]}.scenario_results'
    load_dataframe(client, result_df, result_table, write_disposition="WRITE_APPEND")

    return scenario_id


def get_latest_scenario_summary(scenario_id: str) -> pd.DataFrame:
    cfg = _get_cfg()
    client = _get_client()

    query = f"""
    WITH base AS (
      SELECT
        category,
        market,
        AVG(revenue) AS baseline_revenue
      FROM `{cfg["project_id"]}.{cfg["dataset"]}.demo_business_kpis`
      GROUP BY 1,2
    ),
    agg AS (
      SELECT
        scenario_id,
        category,
        market,
        SUM(spend) AS total_spend,
        SUM(incremental_revenue_low) AS incremental_revenue_low,
        SUM(incremental_revenue_mid) AS incremental_revenue_mid,
        SUM(incremental_revenue_high) AS incremental_revenue_high
      FROM `{cfg["project_id"]}.{cfg["dataset"]}.scenario_results`
      WHERE scenario_id = '{scenario_id}'
      GROUP BY 1,2,3
    )
    SELECT
      a.scenario_id,
      a.category,
      a.market,
      a.total_spend,
      a.incremental_revenue_low,
      a.incremental_revenue_mid,
      a.incremental_revenue_high,
      b.baseline_revenue + a.incremental_revenue_low AS total_revenue_low,
      b.baseline_revenue + a.incremental_revenue_mid AS total_revenue_mid,
      b.baseline_revenue + a.incremental_revenue_high AS total_revenue_high
    FROM agg a
    JOIN base b
      ON a.category = b.category
     AND a.market = b.market
    """
    return run_query(client, query)


def get_latest_channel_results(scenario_id: str) -> pd.DataFrame:
    cfg = _get_cfg()
    client = _get_client()

    query = f"""
    SELECT
      scenario_id,
      category,
      market,
      channel_group,
      channel,
      subchannel,
      spend,
      incremental_revenue_low,
      incremental_revenue_mid,
      incremental_revenue_high,
      roi_low,
      roi_mid,
      roi_high,
      saturation_flag,
      created_at
    FROM `{cfg["project_id"]}.{cfg["dataset"]}.scenario_results`
    WHERE scenario_id = '{scenario_id}'
    ORDER BY channel_group, channel, subchannel
    """
    return run_query(client, query)

def get_scenario_history(limit: int = 50) -> pd.DataFrame:
    cfg = _get_cfg()
    client = _get_client()

    query = f"""
    WITH base AS (
      SELECT
        category,
        market,
        AVG(revenue) AS baseline_revenue
      FROM `{cfg["project_id"]}.{cfg["dataset"]}.demo_business_kpis`
      GROUP BY 1,2
    ),
    agg AS (
      SELECT
        scenario_id,
        category,
        market,
        MIN(created_at) AS created_at,
        SUM(spend) AS total_spend,
        SUM(incremental_revenue_low) AS incremental_revenue_low,
        SUM(incremental_revenue_mid) AS incremental_revenue_mid,
        SUM(incremental_revenue_high) AS incremental_revenue_high
      FROM `{cfg["project_id"]}.{cfg["dataset"]}.scenario_results`
      GROUP BY 1,2,3
    )
    SELECT
      a.scenario_id,
      a.category,
      a.market,
      a.created_at,
      a.total_spend,
      a.incremental_revenue_low,
      a.incremental_revenue_mid,
      a.incremental_revenue_high,
      b.baseline_revenue + a.incremental_revenue_low AS total_revenue_low,
      b.baseline_revenue + a.incremental_revenue_mid AS total_revenue_mid,
      b.baseline_revenue + a.incremental_revenue_high AS total_revenue_high
    FROM agg a
    JOIN base b
      ON a.category = b.category
     AND a.market = b.market
    ORDER BY a.created_at DESC
    LIMIT {int(limit)}
    """
    return run_query(client, query)


def get_scenario_history_for_category_market(category: str, market: str, limit: int = 50) -> pd.DataFrame:
    cfg = _get_cfg()
    client = _get_client()

    query = f"""
    WITH base AS (
      SELECT
        category,
        market,
        AVG(revenue) AS baseline_revenue
      FROM `{cfg["project_id"]}.{cfg["dataset"]}.demo_business_kpis`
      GROUP BY 1,2
    ),
    agg AS (
      SELECT
        scenario_id,
        category,
        market,
        MIN(created_at) AS created_at,
        SUM(spend) AS total_spend,
        SUM(incremental_revenue_low) AS incremental_revenue_low,
        SUM(incremental_revenue_mid) AS incremental_revenue_mid,
        SUM(incremental_revenue_high) AS incremental_revenue_high
      FROM `{cfg["project_id"]}.{cfg["dataset"]}.scenario_results`
      WHERE category = '{category}'
        AND market = '{market}'
      GROUP BY 1,2,3
    ),
    scenario_totals AS (
      SELECT
        a.scenario_id,
        a.category,
        a.market,
        a.created_at,
        a.total_spend,
        a.incremental_revenue_low,
        a.incremental_revenue_mid,
        a.incremental_revenue_high,
        b.baseline_revenue + a.incremental_revenue_low AS total_revenue_low,
        b.baseline_revenue + a.incremental_revenue_mid AS total_revenue_mid,
        b.baseline_revenue + a.incremental_revenue_high AS total_revenue_high,
        (b.baseline_revenue + a.incremental_revenue_mid) - a.total_spend AS projected_profit_mid
      FROM agg a
      JOIN base b
        ON a.category = b.category
       AND a.market = b.market
    ),
    first_scenario AS (
      SELECT
        scenario_id AS first_scenario_id,
        created_at AS first_created_at,
        total_revenue_mid AS first_total_revenue_mid
      FROM scenario_totals
      ORDER BY created_at ASC
      LIMIT 1
    )
    SELECT
      s.*,
      f.first_scenario_id,
      f.first_created_at,
      f.first_total_revenue_mid,
      s.total_revenue_mid - f.first_total_revenue_mid AS revenue_delta_vs_first,
      ROUND(
        SAFE_DIVIDE(
          s.total_revenue_mid - f.first_total_revenue_mid,
          f.first_total_revenue_mid
        ) * 100,
        2
      ) AS revenue_delta_pct_vs_first
    FROM scenario_totals s
    CROSS JOIN first_scenario f
    ORDER BY s.created_at DESC
    LIMIT {int(limit)}
    """
    return run_query(client, query)

def get_first_scenario_id_for_category_market(category: str, market: str) -> str | None:
    cfg = _get_cfg()
    client = _get_client()

    query = f"""
    SELECT scenario_id
    FROM `{cfg["project_id"]}.{cfg["dataset"]}.scenario_results`
    WHERE category = '{category}'
      AND market = '{market}'
    GROUP BY scenario_id
    ORDER BY MIN(created_at) ASC
    LIMIT 1
    """
    df = run_query(client, query)
    if df.empty:
        return None
    return str(df.iloc[0]["scenario_id"])


def clear_scenario_history(category: str | None = None, market: str | None = None) -> None:
    cfg = _get_cfg()
    client = _get_client()

    where_clause = ""
    if category and market:
        where_clause = f"WHERE category = '{category}' AND market = '{market}'"

    delete_inputs = f"""
    DELETE FROM `{cfg["project_id"]}.{cfg["dataset"]}.scenario_inputs`
    {where_clause}
    """
    delete_results = f"""
    DELETE FROM `{cfg["project_id"]}.{cfg["dataset"]}.scenario_results`
    {where_clause}
    """

    client.query(delete_inputs).result()
    client.query(delete_results).result()


def get_saved_scenarios(category: str, market: str, limit: int = 100) -> pd.DataFrame:
    cfg = _get_cfg()
    client = _get_client()

    query = f"""
    SELECT
      scenario_id,
      MIN(created_at) AS created_at,
      SUM(spend) AS total_spend
    FROM `{cfg["project_id"]}.{cfg["dataset"]}.scenario_inputs`
    WHERE category = '{category}'
      AND market = '{market}'
    GROUP BY scenario_id
    ORDER BY created_at DESC
    LIMIT {int(limit)}
    """
    return run_query(client, query)


def get_scenario_inputs_by_id(scenario_id: str) -> pd.DataFrame:
    cfg = _get_cfg()
    client = _get_client()

    query = f"""
    SELECT
      scenario_id,
      created_at,
      category,
      market,
      channel_group,
      channel,
      spend
    FROM `{cfg["project_id"]}.{cfg["dataset"]}.scenario_inputs`
    WHERE scenario_id = '{scenario_id}'
    ORDER BY channel_group, channel
    """
    return run_query(client, query)
