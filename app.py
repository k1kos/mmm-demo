import uuid
import pandas as pd
import streamlit as st
import altair as alt

from src.ai_insights import build_ai_payload, generate_ai_insights
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
    get_latest_scenario_id_by_label,
)

st.set_page_config(
    page_title="Media Mix Scenario Planner",
    page_icon="📈",
    layout="wide",
)

OFFLINE_CHANNELS = ["TV", "OOH", "Radio", "Print"]
DIGITAL_CHANNELS = ["Paid Search", "Social Media", "Online Video", "Display", "Email"]
CONFIDENCE_MODES = ["Conservative", "Base", "Aggressive"]


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

    if "confidence_mode" not in st.session_state:
        st.session_state["confidence_mode"] = "Base"

    if "baseline_scenario_label" not in st.session_state:
        st.session_state["baseline_scenario_label"] = ""

    if "scenario_note" not in st.session_state:
        st.session_state["scenario_note"] = ""

    if "base_revenue" not in st.session_state:
        st.session_state["base_revenue"] = 250000.0

    if "margin_pct" not in st.session_state:
        st.session_state["margin_pct"] = 35.0

    for channel in OFFLINE_CHANNELS + DIGITAL_CHANNELS:
        key = f"spend_{channel}"
        if key not in st.session_state:
            st.session_state[key] = 0.0


def mode_suffix(mode: str) -> str:
    return {
        "Conservative": "low",
        "Base": "mid",
        "Aggressive": "high",
    }.get(mode, "mid")


def mode_metric_label(mode: str) -> str:
    return {
        "Conservative": "Low",
        "Base": "Mid",
        "Aggressive": "High",
    }.get(mode, "Mid")


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


def build_input_dataframe(category: str, market: str, scenario_id: str, scenario_label: str, scenario_note: str) -> pd.DataFrame:
    rows = []

    for channel in OFFLINE_CHANNELS:
        rows.append(
            {
                "scenario_id": scenario_id,
                "scenario_label": scenario_label,
                "scenario_note": scenario_note,
                "category": category,
                "market": market,
                "channel_group": "Offline",
                "channel": channel,
                "spend": float(st.session_state[f"spend_{channel}"]),
                "base_revenue": float(st.session_state["base_revenue"]),
                "margin_pct": float(st.session_state["margin_pct"]),
            }
        )

    for channel in DIGITAL_CHANNELS:
        rows.append(
            {
                "scenario_id": scenario_id,
                "scenario_label": scenario_label,
                "scenario_note": scenario_note,
                "category": category,
                "market": market,
                "channel_group": "Digital",
                "channel": channel,
                "spend": float(st.session_state[f"spend_{channel}"]),
                "base_revenue": float(st.session_state["base_revenue"]),
                "margin_pct": float(st.session_state["margin_pct"]),
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

    if "scenario_label" in scenario_df.columns and pd.notna(scenario_df.iloc[0]["scenario_label"]):
        st.session_state["scenario_name"] = str(scenario_df.iloc[0]["scenario_label"])

    if "scenario_note" in scenario_df.columns and pd.notna(scenario_df.iloc[0]["scenario_note"]):
        st.session_state["scenario_note"] = str(scenario_df.iloc[0]["scenario_note"])

    if "base_revenue" in scenario_df.columns and pd.notna(scenario_df.iloc[0]["base_revenue"]):
        st.session_state["base_revenue"] = float(scenario_df.iloc[0]["base_revenue"])

    if "margin_pct" in scenario_df.columns and pd.notna(scenario_df.iloc[0]["margin_pct"]):
        st.session_state["margin_pct"] = float(scenario_df.iloc[0]["margin_pct"])


def make_bar_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    color_col: str | None = None,
    horizontal: bool = False,
    value_format: str = ",.0f",
):
    def _label(col: str) -> str:
        return col.replace("_", " ").title()

    base = alt.Chart(df).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)

    tooltip = [x_col, alt.Tooltip(y_col, format=value_format)]
    if color_col and color_col in df.columns:
        tooltip.append(color_col)

    if horizontal:
        chart = base.encode(
            y=alt.Y(f"{x_col}:N", sort="-x", title=_label(x_col)),
            x=alt.X(f"{y_col}:Q", title=_label(y_col)),
            color=alt.Color(f"{color_col}:N", legend=None) if color_col else alt.value("#4F46E5"),
            tooltip=tooltip,
        )
        text = alt.Chart(df).mark_text(
            align="center",
            baseline="middle",
            fontSize=11,
            color="#ffffff",
        ).encode(
            y=alt.Y(f"{x_col}:N", sort="-x"),
            x=alt.X(f"{y_col}:Q", stack="zero"),
            text=alt.Text(f"{y_col}:Q", format=value_format),
        )
    else:
        chart = base.encode(
            x=alt.X(f"{x_col}:N", sort="-y", title=_label(x_col)),
            y=alt.Y(f"{y_col}:Q", title=_label(y_col)),
            color=alt.Color(f"{color_col}:N", legend=None) if color_col else alt.value("#4F46E5"),
            tooltip=tooltip,
        )
        text = alt.Chart(df).mark_text(
            baseline="middle",
            fontSize=11,
            color="#ffffff",
        ).encode(
            x=alt.X(f"{x_col}:N", sort="-y"),
            y=alt.Y(f"{y_col}:Q", stack="zero"),
            text=alt.Text(f"{y_col}:Q", format=value_format),
        )

    return (chart + text).properties(title=title, height=320)


def make_group_split_chart(df: pd.DataFrame, title: str):
    donut = (
        alt.Chart(df)
        .mark_arc(innerRadius=55, outerRadius=115)
        .encode(
            theta=alt.Theta("spend:Q"),
            color=alt.Color("channel_group:N", title="Group"),
            tooltip=["channel_group", alt.Tooltip("spend:Q", format=",.0f")],
        )
    )

    labels = (
        alt.Chart(df)
        .mark_text(
            radius=82,
            fontSize=12,
            fontWeight="bold",
            align="center",
            baseline="middle",
        )
        .encode(
            theta=alt.Theta("spend:Q"),
            text=alt.Text("spend:Q", format=",.0f"),
            color=alt.value("#ffffff"),
        )
    )

    return (donut + labels).properties(title=title, height=320)


def make_history_chart(df: pd.DataFrame, metric_col: str, title: str):
    is_profit = "profit" in metric_col.lower()

    bars = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
        .encode(
            x=alt.X("scenario_label:N", sort="-y", title="Scenario"),
            y=alt.Y(f"{metric_col}:Q", title=metric_col.replace("_", " ").title()),
            color=alt.condition(
                alt.datum[metric_col] > 0,
                alt.value("#16A34A"),
                alt.value("#DC2626"),
            ) if is_profit else alt.value("#4F46E5"),
            tooltip=[
                "scenario_label",
                "scenario_id",
                alt.Tooltip(metric_col, format=",.0f"),
                "created_at",
            ],
        )
    )

    labels = (
        alt.Chart(df)
        .mark_text(
            baseline="middle",
            fontSize=11,
            color="#ffffff",
        )
        .encode(
            x=alt.X("scenario_label:N", sort="-y"),
            y=alt.Y(f"{metric_col}:Q", stack="zero"),
            text=alt.Text(f"{metric_col}:Q", format=",.0f"),
        )
    )

    return (bars + labels).properties(title=title, height=360)


def make_profit_delta_chart(df: pd.DataFrame, title: str):
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
        .encode(
            y=alt.Y("channel:N", sort="-x", title="Channel"),
            x=alt.X("delta_projected_channel_profit:Q", title="Delta Projected Channel Profit"),
            color=alt.condition(
                alt.datum.delta_projected_channel_profit > 0,
                alt.value("#16A34A"),
                alt.value("#DC2626"),
            ),
            tooltip=[
                "channel",
                alt.Tooltip("delta_projected_channel_profit:Q", format=",.0f"),
            ],
        )
        .properties(title=title, height=360)
    )


def prepare_channel_metrics(channel_df: pd.DataFrame, mode: str) -> pd.DataFrame:
    suffix = mode_suffix(mode)
    revenue_col = f"incremental_revenue_{suffix}"

    df = channel_df.copy()
    total_spend = float(df["spend"].sum()) if not df.empty else 0.0
    total_incremental = float(df[revenue_col].sum()) if not df.empty else 0.0
    margin_pct = float(df["margin_pct"].iloc[0]) if "margin_pct" in df.columns and not df.empty else 100.0

    df["selected_incremental_revenue"] = df[revenue_col]
    df["projected_channel_profit"] = (df["selected_incremental_revenue"] * (margin_pct / 100.0)) - df["spend"]
    df["spend_share_pct"] = (df["spend"] / total_spend * 100) if total_spend else 0.0
    df["contribution_share_pct"] = (df["selected_incremental_revenue"] / total_incremental * 100) if total_incremental else 0.0
    df["efficiency_index"] = (df["contribution_share_pct"] / df["spend_share_pct"]) if total_spend and total_incremental else 0.0

    return df


def build_comparison_channel_df(current_df: pd.DataFrame, baseline_df: pd.DataFrame, mode: str) -> pd.DataFrame:
    current_metrics = prepare_channel_metrics(current_df, mode)[["channel", "spend", "projected_channel_profit"]].rename(
        columns={
            "spend": "current_spend",
            "projected_channel_profit": "current_projected_channel_profit",
        }
    )
    baseline_metrics = prepare_channel_metrics(baseline_df, mode)[["channel", "spend", "projected_channel_profit"]].rename(
        columns={
            "spend": "baseline_spend",
            "projected_channel_profit": "baseline_projected_channel_profit",
        }
    )

    merged = current_metrics.merge(baseline_metrics, on="channel", how="outer").fillna(0)
    merged["delta_spend"] = merged["current_spend"] - merged["baseline_spend"]
    merged["delta_projected_channel_profit"] = merged["current_projected_channel_profit"] - merged["baseline_projected_channel_profit"]
    return merged


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

    st.sidebar.markdown("---")
    st.sidebar.subheader("Baseline Business Inputs")

    st.sidebar.number_input(
        "Base Revenue",
        min_value=0.0,
        step=10000.0,
        key="base_revenue",
        help="Starting revenue before scenario uplift is applied.",
    )

    st.sidebar.number_input(
        "Margin %",
        min_value=0.0,
        max_value=100.0,
        step=1.0,
        key="margin_pct",
        help="Used to estimate projected profit from projected revenue.",
    )

    st.sidebar.markdown("---")

    scenario_name = st.sidebar.text_input(
        "Scenario label",
        value=st.session_state["scenario_name"],
        help="Human-friendly scenario name. Multiple runs can share the same label.",
    )

    confidence_mode = st.sidebar.selectbox(
        "Confidence mode",
        options=CONFIDENCE_MODES,
        index=CONFIDENCE_MODES.index(st.session_state["confidence_mode"]),
        help="Controls whether the app shows conservative, base, or aggressive scenario outputs.",
    )

    reset_to_benchmark = st.sidebar.button("Reset to benchmark mix")
    clear_all = st.sidebar.button("Clear all spends")

    st.sidebar.markdown("---")
    st.sidebar.info(
        "Suggested spends come from benchmark assumptions for the selected category and market."
    )

    saved_df = get_saved_scenarios(selected_category, selected_market, limit=100)
    label_options = saved_df["scenario_label"].astype(str).tolist() if not saved_df.empty else []

    selected_saved_label = st.sidebar.selectbox(
        "Saved scenario labels",
        options=[""] + label_options,
        index=0,
        help="Choose a saved scenario label and load its latest version.",
    )

    load_saved = st.sidebar.button("Load selected saved scenario")

    baseline_label = st.sidebar.selectbox(
        "Baseline scenario label",
        options=[""] + label_options,
        index=([""] + label_options).index(st.session_state["baseline_scenario_label"])
        if st.session_state["baseline_scenario_label"] in ([""] + label_options)
        else 0,
        help="Pick a saved scenario label to compare against the current selected scenario.",
    )

    st.sidebar.text_area(
        "Scenario note",
        key="scenario_note",
        height=100,
        help="This note will be saved with the scenario run.",
    )

    st.session_state["selected_category"] = selected_category
    st.session_state["selected_market"] = selected_market
    st.session_state["scenario_name"] = scenario_name
    st.session_state["confidence_mode"] = confidence_mode
    st.session_state["baseline_scenario_label"] = baseline_label

    if reset_to_benchmark:
        seed_channel_spends_from_benchmarks(selected_category, selected_market)

    if clear_all:
        for channel in OFFLINE_CHANNELS + DIGITAL_CHANNELS:
            st.session_state[f"spend_{channel}"] = 0.0

    if load_saved and selected_saved_label:
        latest_id = get_latest_scenario_id_by_label(selected_category, selected_market, selected_saved_label)
        if latest_id:
            load_scenario_into_form(latest_id)
            st.sidebar.success(f"Loaded latest version of: {selected_saved_label}")

    if not saved_df.empty:
        with st.sidebar.expander("Saved scenario versions", expanded=False):
            st.dataframe(
                saved_df[["scenario_label", "version_count", "last_created_at", "latest_scenario_note"]],
                width="stretch",
                hide_index=True,
            )

    return selected_category, selected_market, scenario_name, confidence_mode, baseline_label


def render_inputs():
    st.subheader("1. 📥 Media Spend Inputs")
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
    st.subheader("2. 📊 Budget Summary")
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
        st.altair_chart(
            make_bar_chart(
                mix_df.sort_values("spend", ascending=False),
                x_col="channel",
                y_col="spend",
                title="Spend by Channel",
                color_col="channel_group",
            ),
            width="stretch",
        )
        st.caption("Budget allocated to each media channel.")

    with col2:
        group_df = mix_df.groupby("channel_group", as_index=False)["spend"].sum()
        st.altair_chart(
            make_group_split_chart(group_df, "Offline vs Digital Split"),
            width="stretch",
        )
        st.caption("Budget split between Offline and Digital groups.")


def render_results(summary_df: pd.DataFrame, channel_df: pd.DataFrame, confidence_mode: str):
    st.subheader("3. 💰 Projected Outcome")
    st.caption("Directional benchmark-based estimates for the current scenario.")

    if summary_df.empty:
        st.info("Run a scenario to see projected revenue and profit.")
        return

    suffix = mode_suffix(confidence_mode)
    mode_label = mode_metric_label(confidence_mode)
    summary_row = summary_df.iloc[0]

    incremental_revenue = float(summary_row[f"incremental_revenue_{suffix}"])
    projected_total_revenue = float(summary_row[f"total_revenue_{suffix}"])
    base_revenue = float(summary_row["base_revenue"])
    margin_pct = float(summary_row["margin_pct"])
    projected_profit = (projected_total_revenue * (margin_pct / 100.0)) - float(summary_row["total_spend"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Spend", f"{float(summary_row['total_spend']):,.0f}")
    c2.metric(f"Incremental Revenue ({mode_label})", f"{incremental_revenue:,.0f}")
    c3.metric(f"Projected Revenue ({mode_label})", f"{projected_total_revenue:,.0f}")
    c4.metric(f"Projected Profit ({mode_label})", f"{projected_profit:,.0f}")

    st.caption(
        f"Confidence mode is currently set to {confidence_mode}. "
        f"Projected Profit uses Base Revenue = {base_revenue:,.0f} and Margin = {margin_pct:.1f}%."
    )

    if not channel_df.empty:
        impact_df = prepare_channel_metrics(channel_df, confidence_mode).sort_values(
            "selected_incremental_revenue", ascending=False
        )

        st.markdown("### Channel Impact")
        st.caption("How each channel contributes to the modeled scenario outcome.")

        col1, col2 = st.columns(2)

        with col1:
            st.altair_chart(
                make_bar_chart(
                    impact_df.sort_values("selected_incremental_revenue", ascending=False),
                    x_col="channel",
                    y_col="selected_incremental_revenue",
                    title=f"Incremental Revenue by Channel ({mode_label})",
                    color_col="channel_group",
                ),
                width="stretch",
            )
            st.caption("Selected-mode estimate of incremental revenue contribution by channel.")

        with col2:
            roi_df = impact_df[["channel", "roi_mid", "channel_group"]].copy()
            st.altair_chart(
                make_bar_chart(
                    roi_df.sort_values("roi_mid", ascending=False),
                    x_col="channel",
                    y_col="roi_mid",
                    title="ROI by Channel",
                    color_col="channel_group",
                    value_format=".2f",
                ),
                width="stretch",
            )
            st.caption("Benchmark-based ROI assumption used for each channel.")

        st.markdown("### Channel Efficiency Metrics")
        efficiency_cols = [
            "channel_group",
            "channel",
            "spend",
            "spend_share_pct",
            "selected_incremental_revenue",
            "contribution_share_pct",
            "projected_channel_profit",
            "roi_mid",
            "efficiency_index",
            "saturation_flag",
        ]
        st.dataframe(
            impact_df[efficiency_cols].style.format(
                {
                    "spend": "{:,.0f}",
                    "spend_share_pct": "{:.2f}%",
                    "selected_incremental_revenue": "{:,.0f}",
                    "contribution_share_pct": "{:.2f}%",
                    "projected_channel_profit": "{:,.0f}",
                    "roi_mid": "{:.2f}",
                    "efficiency_index": "{:.2f}",
                }
            ),
            width="stretch",
            hide_index=True,
        )
        st.caption("Efficiency Index compares contribution share to spend share. Above 1.00 means the channel contributes more than its share of spend.")


def render_comparison_section(
    baseline_scenario_label: str,
    latest_scenario_id: str,
    selected_category: str,
    selected_market: str,
    confidence_mode: str,
    history_df: pd.DataFrame,
):
    if not baseline_scenario_label or not latest_scenario_id or history_df.empty:
        return

    current_summary_df = get_latest_scenario_summary(latest_scenario_id)
    current_channel_df = get_latest_channel_results(latest_scenario_id)

    if current_summary_df.empty or current_channel_df.empty:
        return

    current_label = str(current_summary_df.iloc[0].get("scenario_label", ""))

    baseline_candidates = history_df.loc[
        history_df["scenario_label"].astype(str) == str(baseline_scenario_label)
    ].copy()

    if baseline_candidates.empty:
        st.info("No baseline scenario found for the selected baseline label.")
        return

    if baseline_scenario_label == current_label:
        baseline_candidates = baseline_candidates.loc[
            baseline_candidates["scenario_id"].astype(str) != str(latest_scenario_id)
        ]

    if baseline_candidates.empty:
        st.info("No previous baseline version available to compare against.")
        return

    baseline_candidates = baseline_candidates.sort_values("created_at", ascending=False)
    baseline_scenario_id = str(baseline_candidates.iloc[0]["scenario_id"])

    baseline_summary_df = get_latest_scenario_summary(baseline_scenario_id)
    baseline_channel_df = get_latest_channel_results(baseline_scenario_id)

    if baseline_summary_df.empty or baseline_channel_df.empty:
        st.info("Baseline scenario details could not be loaded.")
        return

    suffix = mode_suffix(confidence_mode)
    mode_label = mode_metric_label(confidence_mode)

    base = baseline_summary_df.iloc[0]
    curr = current_summary_df.iloc[0]

    base_spend = float(base["total_spend"])
    curr_spend = float(curr["total_spend"])

    base_revenue = float(base[f"total_revenue_{suffix}"])
    curr_revenue = float(curr[f"total_revenue_{suffix}"])

    base_margin_pct = float(base["margin_pct"])
    curr_margin_pct = float(curr["margin_pct"])

    base_profit = (base_revenue * (base_margin_pct / 100.0)) - base_spend
    curr_profit = (curr_revenue * (curr_margin_pct / 100.0)) - curr_spend

    delta_spend = curr_spend - base_spend
    delta_revenue = curr_revenue - base_revenue
    delta_profit = curr_profit - base_profit

    st.subheader("4. 🔄 Baseline vs Current Scenario")
    st.caption(
        f"Comparing current scenario `{latest_scenario_id}` against baseline `{baseline_scenario_id}` using {confidence_mode} mode."
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Δ Spend", f"{delta_spend:,.0f}")
    c2.metric(f"Δ Projected Revenue ({mode_label})", f"{delta_revenue:,.0f}")
    c3.metric(f"Δ Projected Profit ({mode_label})", f"{delta_profit:,.0f}")

    comparison_df = build_comparison_channel_df(current_channel_df, baseline_channel_df, confidence_mode)

    col1, col2 = st.columns(2)
    with col1:
        st.altair_chart(
            make_profit_delta_chart(
                comparison_df.sort_values("delta_projected_channel_profit", ascending=False),
                f"Delta Channel Profit vs Baseline ({mode_label})",
            ),
            width="stretch",
        )
        st.caption("Shows which channels improved or hurt projected profit versus the selected baseline.")

    with col2:
        st.dataframe(
            comparison_df[
                [
                    "channel",
                    "baseline_spend",
                    "current_spend",
                    "delta_spend",
                    "baseline_projected_channel_profit",
                    "current_projected_channel_profit",
                    "delta_projected_channel_profit",
                ]
            ].style.format(
                {
                    "baseline_spend": "{:,.0f}",
                    "current_spend": "{:,.0f}",
                    "delta_spend": "{:,.0f}",
                    "baseline_projected_channel_profit": "{:,.0f}",
                    "current_projected_channel_profit": "{:,.0f}",
                    "delta_projected_channel_profit": "{:,.0f}",
                }
            ),
            width="stretch",
            hide_index=True,
        )
        st.caption("Channel-by-channel comparison of spend and projected profit versus baseline.")


def render_benchmark_panel(category: str, market: str):
    bench_df = get_benchmark_rows(category, market)

    with st.expander("Benchmark assumptions", expanded=False):
        st.caption("These are the benchmark assumptions currently used for the selected category and market.")

        if bench_df.empty:
            st.info("No benchmark assumptions found for this category and market.")
            return

        display_cols = [
            "channel_group",
            "channel",
            "subchannel",
            "roi_low",
            "roi_mid",
            "roi_high",
            "adstock_rate",
            "confidence_score",
            "max_efficient_spend",
            "suggested_spend",
        ]
        st.dataframe(
            bench_df[display_cols].style.format(
                {
                    "roi_low": "{:.2f}",
                    "roi_mid": "{:.2f}",
                    "roi_high": "{:.2f}",
                    "adstock_rate": "{:.2f}",
                    "confidence_score": "{:.2f}",
                    "max_efficient_spend": "{:,.0f}",
                    "suggested_spend": "{:,.0f}",
                }
            ),
            width="stretch",
            hide_index=True,
        )


def render_scenario_history(category: str, market: str):
    st.subheader("5. 🕘 Scenario History")
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

    col1, col2 = st.columns(2)

    with col1:
        st.altair_chart(
            make_history_chart(history_df, "total_revenue_mid", "Projected Revenue by Scenario"),
            width="stretch",
        )
        st.caption("Projected total revenue for each saved scenario.")

    with col2:
        st.altair_chart(
            make_history_chart(history_df, "projected_profit_mid", "Projected Profit by Scenario"),
            width="stretch",
        )
        st.caption("Projected profit for each scenario, calculated using base revenue, margin, and media spend.")

    show_df = history_df.copy()
    show_df["best_scenario"] = show_df["projected_profit_mid"].apply(
        lambda x: "🏆 Best" if float(x) == best_profit else ""
    )
    show_df["profit_change_vs_first_pct"] = show_df["profit_change_vs_first_pct"].round(2)

    display_cols = [
        "best_scenario",
        "scenario_label",
        "scenario_id",
        "scenario_note",
        "created_at",
        "base_revenue",
        "margin_pct",
        "total_spend",
        "incremental_revenue_mid",
        "total_revenue_mid",
        "projected_profit_mid",
        "profit_change_vs_first_pct",
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
            "base_revenue": "{:,.0f}",
            "margin_pct": "{:.1f}%",
            "total_spend": "{:,.0f}",
            "incremental_revenue_mid": "{:,.0f}",
            "total_revenue_mid": "{:,.0f}",
            "projected_profit_mid": "{:,.0f}",
            "profit_change_vs_first_pct": "{:+.2f}%",
        }
    ).map(style_change_vs_first, subset=["profit_change_vs_first_pct"])

    st.dataframe(styled_df, width="stretch", hide_index=True)
    st.caption("Profit Change vs First % compares projected profit against the first scenario run for this category and market.")


def render_ai_insights(category: str, market: str, summary_df: pd.DataFrame, channel_df: pd.DataFrame, history_df: pd.DataFrame):
    st.subheader("6. 🤖 AI Insights")
    st.caption("Generate plain-English commentary on the current scenario using the selected scenario results and recent scenario history.")

    if summary_df.empty or channel_df.empty:
        st.info("Run a scenario first to generate AI insights.")
        return

    if st.button("Generate AI insights"):
        with st.spinner("Generating AI insights..."):
            payload = build_ai_payload(
                category=category,
                market=market,
                summary_df=summary_df,
                channel_df=channel_df,
                history_df=history_df,
            )
            try:
                insights = generate_ai_insights(payload)
                st.session_state["ai_insights_text"] = insights
            except Exception as e:
                st.error(f"AI insights failed: {e}")
                return

    insights_text = st.session_state.get("ai_insights_text")
    if insights_text:
        st.markdown(insights_text)
        st.caption("These insights are AI-generated commentary based on the scenario data shown in the app. Treat them as directional suggestions.")


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

    st.markdown("""
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stMetric"] {
        background-color: transparent;
        border: 1px solid color-mix(in srgb, currentColor 20%, transparent);
        padding: 12px;
        border-radius: 12px;
        min-height: 108px;
        display: flex;
        flex-direction: column;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
    }
    div[data-testid="stMetric"] > div {
        width: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
    }
    div[data-testid="stMetricLabel"] {
        width: 100%;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
    }
    div[data-testid="stMetricValue"] {
        width: 100%;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
    }
    div[data-testid="stMetricDelta"] {
        width: 100%;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
    }
    div[data-testid="stMetricLabel"] * {
        width: 100%;
        text-align: center !important;
        color: color-mix(in srgb, currentColor 85%, transparent) !important;
    }
    div[data-testid="stMetricValue"] * {
        width: 100%;
        text-align: center !important;
        color: currentColor !important;
    }
    div[data-testid="stMetricDelta"] * {
        width: 100%;
        text-align: center !important;
        color: color-mix(in srgb, currentColor 75%, transparent) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("Media Mix Scenario Planner")
    st.caption("Benchmark-based simulator for testing how media mix changes may affect projected profit.")

    st.info(
        "This is a proof-of-concept tool using synthetic benchmark assumptions and synthetic KPI baselines. "
        "Treat outputs as directional estimates."
    )

    selected_category, selected_market, scenario_name, confidence_mode, baseline_scenario_label = render_sidebar(categories, markets)

    current_key = f"{selected_category}|{selected_market}"
    last_key = st.session_state.get("last_category_market_key")

    if last_key != current_key:
        seed_channel_spends_from_benchmarks(selected_category, selected_market)
        st.session_state["last_category_market_key"] = current_key
        st.session_state.pop("ai_insights_text", None)
        st.session_state.pop("latest_scenario_id", None)

    with st.form("scenario_form"):
        with st.container(border=True):
            render_inputs()
            render_mix_summary()
            run_clicked = st.form_submit_button("Run scenario", type="primary")

    if run_clicked:
        scenario_label = scenario_name.strip().replace(" ", "_").lower()
        scenario_note = st.session_state.get("scenario_note", "").strip()
        scenario_id = f"{scenario_label}_{uuid.uuid4().hex[:8]}"
        inputs_df = build_input_dataframe(
            selected_category,
            selected_market,
            scenario_id,
            scenario_label,
            scenario_note,
        )

        with st.spinner("Running scenario..."):
            run_and_store_scenario(inputs_df)

        st.session_state["latest_scenario_id"] = scenario_id
        st.session_state.pop("ai_insights_text", None)
        st.success(f"Scenario completed: {scenario_id}")

    latest_scenario_id = st.session_state.get("latest_scenario_id")

    summary_df = pd.DataFrame()
    channel_df = pd.DataFrame()
    history_df = get_scenario_history_for_category_market(selected_category, selected_market, limit=50)

    render_benchmark_panel(selected_category, selected_market)

    if latest_scenario_id:
        with st.container(border=True):
            summary_df = get_latest_scenario_summary(latest_scenario_id)
            channel_df = get_latest_channel_results(latest_scenario_id)
            render_results(summary_df, channel_df, confidence_mode)

        if baseline_scenario_label:
            with st.container(border=True):
                render_comparison_section(
                    baseline_scenario_label=baseline_scenario_label,
                    latest_scenario_id=latest_scenario_id,
                    selected_category=selected_category,
                    selected_market=selected_market,
                    confidence_mode=confidence_mode,
                    history_df=history_df,
                )
    else:
        st.info("No scenario run yet in this session.")

    with st.expander("Scenario history", expanded=True):
        with st.container(border=True):
            render_scenario_history(selected_category, selected_market)

    if latest_scenario_id and not summary_df.empty and not channel_df.empty:
        with st.container(border=True):
            render_ai_insights(
                category=selected_category,
                market=selected_market,
                summary_df=summary_df,
                channel_df=channel_df,
                history_df=history_df,
            )


if __name__ == "__main__":
    main()
