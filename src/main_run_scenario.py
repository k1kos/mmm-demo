import sys
from pathlib import Path
import pandas as pd

# Support both:
# - `python -m src.main_run_scenario` (package/module run)
# - running this file directly from VS Code
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import load_settings
from src.bq import get_client, load_dataframe, run_query
from src.model import run_scenario_model


def main() -> None:
    cfg = load_settings()
    client = get_client(cfg["project_id"])

    scenario_id = sys.argv[1] if len(sys.argv) > 1 else "scenario_001"

    inputs_query = f"""
    SELECT scenario_id, category, market, channel, spend
    FROM `{cfg["project_id"]}.{cfg["dataset"]}.scenario_inputs`
    WHERE scenario_id = '{scenario_id}'
    """

    bench_query = f"""
    SELECT category, market, channel, roi_low, roi_mid, roi_high,
           adstock_rate, saturation_alpha, saturation_gamma,
           max_efficient_spend, confidence_score
    FROM `{cfg["project_id"]}.{cfg["dataset"]}.benchmark_channel_curves`
    """

    kpi_query = f"""
    SELECT category, market, AVG(revenue) AS avg_revenue
    FROM `{cfg["project_id"]}.{cfg["dataset"]}.demo_business_kpis`
    GROUP BY 1,2
    """

    inputs_df = run_query(client, inputs_query)
    bench_df = run_query(client, bench_query)
    kpi_df = run_query(client, kpi_query)

    if inputs_df.empty:
        raise ValueError(f"No rows found for scenario_id={scenario_id}")

    result_df = run_scenario_model(inputs_df, bench_df, kpi_df, scenario_id)
    result_df["created_at"] = pd.to_datetime(result_df["created_at"], utc=True)

    result_table = f'{cfg["project_id"]}.{cfg["dataset"]}.scenario_results'
    load_dataframe(client, result_df, result_table, write_disposition="WRITE_APPEND")

    print(f"Scenario {scenario_id} written to scenario_results.")


if __name__ == "__main__":
    main()
