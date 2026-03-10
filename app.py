import uuid
import pandas as pd
import streamlit as st

from src.config import load_settings
from src.scenario_service import (
    get_available_categories,
    get_available_markets,
    get_benchmark_rows,
    run_and_store_scenario,
    get_latest_scenario_summary,
    get_latest_channel_results,
    get_scenario_history_for_category_market,
    clear_scenario_history,
    get_saved_scenarios,
    get_scenario_inputs_by_id,
)

st.set_page_config(
    page_title="Media Mix Scenario Planner",
    page_icon="📈",
    layout="wide",
)

OFFLINE_CHANNELS = ["TV", "OOH", "Radio", "Print"]
DIGITAL_CHANNELS = ["Paid Search", "Social Media", "Online Video", "Display", "Email"]


@st.cache_data(show_spinner=False)
def load_reference_data():
    categories = get_available_categories()
    markets = get_available_markets()
    return categories, markets


def initialize_session_state(default_category: str, default_market: str):
    if "scenario_name" not in st.session_state:
        st.session_state["scenario_name"] = "demo_scenario"

    if "selected_category" not in st.session_state:
        st.session_state["selected_category"] = default_category

    if "selected_market" not in st.session_state:
        st.session_state["selected_market"] = default_market

    if "channel_defaults_loaded" not in st.session_state:
        st.session_state["channel_defaults_loaded"] = False

    for channel in OFFLINE_CHANNELS + DIGITAL_CHANNELS:
        key = f"spend_{channel}"
        if key not in st.session_state:
            st.session_state[key] = 0.0


def seed_channel_spends_from_benchmarks(category: str, market: str):
    bench_df = get_benchmark_rows(category, market)

    if bench_df.empty:
        for channel in OFFLINE_CHANNELS + DIGITAL_CHANNELS:
            st.session_state[f"spend_{channel}"] = 0.0
        return

    for channel in OFFLINE_CHANNELS + DIGITAL_CHANNELS:
        key = f"spend_{channel}"
        match = bench_df.loc[bench_df["channel"] == channel]
        if not match.empty:
            st.session_state[key] = float(match.iloc[0]["suggested_spend"])
        else:
            st.session_state[key] = 0.0


def build_input_dataframe(category: str, market: str, scenario_id: str) -> pd.DataFrame:
    rows = []

    for channel in OFFLINE_CHANNELS:
        rows.append(
            {
                "scenario_id": scenario_id,
                "category": category,
                "market": market,
                "channel_group": "Offline",
                "channel": channel,
                "spend": float(st.session_state[f"spend_{channel}"]),
            }
        )

    for channel in DIGITAL_CHANNELS:
        rows.append(
            {
                "scenario_id": scenario_id,
                "category": category,
                "market": market,
                "channel_group": "Digital",
                "channel": channel,
                "spend": float(st.session_state[f"spend_{channel}"]),
            }
        )

    return pd.DataFrame(rows)

def load_scenario_into_form(scenario_id: str):
    scenario_df = get_scenario_inputs_by_id(scenario_id)

    if scenario_df.empty:
        st.warning(f"No saved scenario inputs found for: {scenario_id}")
        return

    for channel in OFFLINE_CHANNELS + DIGITAL_CHANNELS:
        st.session_state[f"spend_{channel}"] = 0.0

    for _, row in scenario_df.iterrows():
        channel = str(row["channel"])
        if f"spend_{channel}" in st.session_state:
            st.session_state[f"spend_{channel}"] = float(row["spend"])

    st.session_state["scenario_name"] = scenario_id

def render_sidebar(categories, markets):
    st.sidebar.header("Scenario Setup")
    st.sidebar.caption("Choose category and market, then edit spend by channel.")

    selected_category = st.sidebar.selectbox(
        "Category",
        options=categories,
        index=categories.index(st.session_state["selected_category"])
        if st.session_state["selected_category"] in categories
        else 0,
    )

    selected_market = st.sidebar.selectbox(
        "Market",
        options=markets,
        index=markets.index(st.session_state["selected_market"])
        if st.session_state["selected_market"] in markets
        else 0,
    )

    scenario_name = st.sidebar.text_input(
        "Scenario name",
        value=st.session_state["scenario_name"],
        help="This label will appear in scenario history.",
    )

    reload_defaults = st.sidebar.button("Load suggested spends")
    clear_all = st.sidebar.button("Clear all spends")

    st.sidebar.markdown("---")
    st.sidebar.info(
        "Suggested spends come from benchmark assumptions for the selected category and market."
    )

    saved_df = get_saved_scenarios(selected_category, selected_market, limit=100)

    saved_options = []
    if not saved_df.empty:
        saved_options = saved_df["scenario_id"].astype(str).tolist()

    selected_saved_scenario = st.sidebar.selectbox(
        "Saved scenarios",
        options=[""] + saved_options,
        index=0,
        help="Choose a previously saved scenario and load its spend settings into the form.",
    )

    load_saved = st.sidebar.button("Load selected scenario")

    st.session_state["selected_category"] = selected_category
    st.session_state["selected_market"] = selected_market
    st.session_state["scenario_name"] = scenario_name

    if reload_defaults:
        seed_channel_spends_from_benchmarks(selected_category, selected_market)

    if clear_all:
        for channel in OFFLINE_CHANNELS + DIGITAL_CHANNELS:
            st.session_state[f"spend_{channel}"] = 0.0

    if load_saved and selected_saved_scenario:
        load_scenario_into_form(selected_saved_scenario)
        st.sidebar.success(f"Loaded scenario: {selected_saved_scenario}")

    return selected_category, selected_market, scenario_name


def render_inputs():
    st.subheader("1. Media Spend Inputs")
    st.caption("Enter the planned spend for each channel.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Offline Media")
        st.caption("Broad-reach media typically used for awareness.")
        for channel in OFFLINE_CHANNELS:
            st.number_input(channel, min_value=0.0, step=1000.0, key=f"spend_{channel}")

    with col2:
        st.markdown("### Digital Media")
        st.caption("More targeted and performance-oriented channels.")
        for channel in DIGITAL_CHANNELS:
            st.number_input(channel, min_value=0.0, step=1000.0, key=f"spend_{channel}")


def render_mix_summary():
    st.subheader("2. Budget Summary")
    st.caption("Summary of the current media allocation.")

    mix_rows = []
    for channel in OFFLINE_CHANNELS + DIGITAL_CHANNELS:
        spend = float(st.session_state[f"spend_{channel}"])
        group = "Offline" if channel in OFFLINE_CHANNELS else "Digital"
        mix_rows.append({"channel_group": group, "channel": channel, "spend": spend})

    mix_df = pd.DataFrame(mix_rows)
    total_spend = float(mix_df["spend"].sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Spend", f"{total_spend:,.0f}")
    c2.metric("Offline Spend", f"{mix_df.loc[mix_df['channel_group'] == 'Offline', 'spend'].sum():,.0f}")
    c3.metric("Digital Spend", f"{mix_df.loc[mix_df['channel_group'] == 'Digital', 'spend'].sum():,.0f}")

    st.caption("This shows total budget and how it is split between Offline and Digital channels.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Spend by Channel")
        st.bar_chart(mix_df.set_index("channel")["spend"], width="stretch")
        st.caption("Budget allocated to each media channel.")

    with col2:
        group_df = mix_df.groupby("channel_group", as_index=False)["spend"].sum()
        st.markdown("#### Offline vs Digital Split")
        st.bar_chart(group_df.set_index("channel_group")["spend"], width="stretch")
        st.caption("Budget split between Offline and Digital groups.")


def render_results(summary_df: pd.DataFrame, channel_df: pd.DataFrame):
    st.subheader("3. Projected Outcome")
    st.caption("Directional benchmark-based estimates for the current scenario.")

    if summary_df.empty:
        st.info("Run a scenario to see projected revenue and profit.")
        return

    summary_row = summary_df.iloc[0]
    projected_profit_mid = float(summary_row["total_revenue_mid"]) - float(summary_row["total_spend"])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Incremental Revenue (Low)", f"{float(summary_row['incremental_revenue_low']):,.0f}")
    c2.metric("Incremental Revenue (Mid)", f"{float(summary_row['incremental_revenue_mid']):,.0f}")
    c3.metric("Incremental Revenue (High)", f"{float(summary_row['incremental_revenue_high']):,.0f}")
    c4.metric("Projected Total Revenue", f"{float(summary_row['total_revenue_mid']):,.0f}")
    c5.metric("Projected Profit", f"{projected_profit_mid:,.0f}")

    st.caption(
        "Projected Profit here is modeled projected total revenue minus total media spend. "
        "This is a simplified demo metric, not a finance-grade profit calculation."
    )

    if not channel_df.empty:
        impact_df = channel_df.copy().sort_values("incremental_revenue_mid", ascending=False)

        st.markdown("### Channel Impact")
        st.caption("How each channel contributes to the modeled revenue impact.")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Incremental Revenue by Channel")
            st.bar_chart(impact_df.set_index("channel")["incremental_revenue_mid"], width="stretch")
            st.caption("Mid-case estimate of incremental revenue contribution by channel.")

        with col2:
            roi_df = impact_df[["channel", "roi_mid"]].set_index("channel")
            st.markdown("#### ROI by Channel")
            st.bar_chart(roi_df["roi_mid"], width="stretch")
            st.caption("Benchmark-based ROI assumption used for each channel.")

        display_cols = [
            "channel_group",
            "channel",
            "spend",
            "incremental_revenue_low",
            "incremental_revenue_mid",
            "incremental_revenue_high",
            "roi_mid",
            "saturation_flag",
        ]
        st.markdown("### Detailed Results")
        st.dataframe(impact_df[display_cols], width="stretch", hide_index=True)
        st.caption("Saturation Flag means the entered spend may be above the model’s efficient range for that channel.")


def render_scenario_history(category: str, market: str):
    st.subheader("4. Scenario History")
    st.caption("Compare previous runs for the selected category and market.")

    top_col1, top_col2 = st.columns([4, 1])

    with top_col2:
        if st.button("Clear history", type="secondary"):
            clear_scenario_history(category, market)
            st.session_state.pop("latest_scenario_id", None)
            st.success("Scenario history cleared for this category and market.")
            st.rerun()

    history_df = get_scenario_history_for_category_market(category, market, limit=50)

    if history_df.empty:
        st.info("No historical scenarios found yet for this category and market.")
        return

    best_profit = float(history_df["projected_profit_mid"].max())

    chart_df = history_df.copy()
    chart_df["scenario_label"] = chart_df["scenario_id"]

    st.markdown("#### Projected Revenue by Scenario")
    history_chart = chart_df[["scenario_label", "total_revenue_mid"]].sort_values("total_revenue_mid", ascending=False)
    st.bar_chart(history_chart.set_index("scenario_label")["total_revenue_mid"], width="stretch")
    st.caption("Projected total revenue for each saved scenario.")

    st.markdown("#### Profit by Scenario")
    profit_chart = chart_df[["scenario_label", "projected_profit_mid"]].sort_values("projected_profit_mid", ascending=False)
    st.bar_chart(profit_chart.set_index("scenario_label")["projected_profit_mid"], width="stretch")
    st.caption("Projected profit for each scenario, calculated as projected revenue minus media spend.")

    show_df = history_df.copy()
    show_df["best_scenario"] = show_df["projected_profit_mid"].apply(
        lambda x: "🏆 Best" if float(x) == best_profit else ""
    )
    show_df["change_vs_first_pct"] = show_df["revenue_delta_pct_vs_first"].round(2)

    display_cols = [
        "best_scenario",
        "scenario_id",
        "created_at",
        "total_spend",
        "incremental_revenue_mid",
        "total_revenue_mid",
        "projected_profit_mid",
        "change_vs_first_pct",
    ]

    def style_change_vs_first(val):
        if pd.isna(val):
            return ""
        if float(val) > 0:
            return "color: green; font-weight: bold;"
        if float(val) < 0:
            return "color: red; font-weight: bold;"
        return ""

    st.markdown("#### Scenario Comparison Table")
    styled_df = show_df[display_cols].style.format(
        {
            "total_spend": "{:,.0f}",
            "incremental_revenue_mid": "{:,.0f}",
            "total_revenue_mid": "{:,.0f}",
            "projected_profit_mid": "{:,.0f}",
            "change_vs_first_pct": "{:+.2f}%",
        }
    ).map(style_change_vs_first, subset=["change_vs_first_pct"])

    st.dataframe(
        styled_df,
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "Change vs First % shows how projected total revenue changed relative to the first scenario ever run for this category and market. "
        "Positive means revenue increased. Negative means revenue decreased."
    )


def main():
    cfg = load_settings()
    categories, markets = load_reference_data()

    default_category = cfg["default_category"] if cfg["default_category"] in categories else categories[0]
    default_market = cfg["default_market"] if cfg["default_market"] in markets else markets[0]

    initialize_session_state(default_category, default_market)

    if not st.session_state["channel_defaults_loaded"]:
        seed_channel_spends_from_benchmarks(
            st.session_state["selected_category"],
            st.session_state["selected_market"],
        )
        st.session_state["channel_defaults_loaded"] = True

    st.title("Media Mix Scenario Planner")
    st.caption("Benchmark-based simulator for testing how media mix changes may affect projected revenue.")

    st.info(
        "This is a proof-of-concept tool using synthetic benchmark assumptions and synthetic KPI baselines. "
        "Treat outputs as directional estimates."
    )

    selected_category, selected_market, scenario_name = render_sidebar(categories, markets)

    current_key = f"{selected_category}|{selected_market}"
    last_key = st.session_state.get("last_category_market_key")

    if last_key != current_key:
        seed_channel_spends_from_benchmarks(selected_category, selected_market)
        st.session_state["last_category_market_key"] = current_key

    render_inputs()
    render_mix_summary()

    if st.button("Run scenario", type="primary"):
        scenario_id = f"{scenario_name.strip().replace(' ', '_').lower()}_{uuid.uuid4().hex[:8]}"
        inputs_df = build_input_dataframe(selected_category, selected_market, scenario_id)

        with st.spinner("Running scenario..."):
            run_and_store_scenario(inputs_df)

        st.session_state["latest_scenario_id"] = scenario_id
        st.success(f"Scenario completed: {scenario_id}")

    latest_scenario_id = st.session_state.get("latest_scenario_id")

    if latest_scenario_id:
        summary_df = get_latest_scenario_summary(latest_scenario_id)
        channel_df = get_latest_channel_results(latest_scenario_id)
        render_results(summary_df, channel_df)
    else:
        st.info("No scenario run yet in this session.")

    render_scenario_history(selected_category, selected_market)


if __name__ == "__main__":
    main()