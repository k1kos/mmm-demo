import math
import pandas as pd


def _channel_shape_defaults(channel: str) -> dict:
    channel = str(channel).strip().lower()

    defaults = {
        "tv": {"seasonality": 0.20, "ctr": 0.004, "impression_multiplier": 220.0},
        "ooh": {"seasonality": 0.12, "ctr": 0.002, "impression_multiplier": 260.0},
        "radio": {"seasonality": 0.10, "ctr": 0.003, "impression_multiplier": 180.0},
        "print": {"seasonality": 0.08, "ctr": 0.002, "impression_multiplier": 140.0},
        "paid search": {"seasonality": 0.18, "ctr": 0.025, "impression_multiplier": 70.0},
        "social media": {"seasonality": 0.22, "ctr": 0.018, "impression_multiplier": 110.0},
        "online video": {"seasonality": 0.20, "ctr": 0.010, "impression_multiplier": 150.0},
        "display": {"seasonality": 0.14, "ctr": 0.008, "impression_multiplier": 140.0},
        "email": {"seasonality": 0.06, "ctr": 0.035, "impression_multiplier": 45.0},
    }

    return defaults.get(
        channel,
        {"seasonality": 0.15, "ctr": 0.012, "impression_multiplier": 100.0},
    )


def _category_demand_multiplier(category: str) -> float:
    category = str(category).strip().lower()

    mapping = {
        "beverages": 1.10,
        "automotive": 1.25,
        "banking": 1.05,
        "retail": 1.15,
        "telecom": 1.12,
        "travel": 1.20,
        "insurance": 1.00,
        "pharma": 0.98,
    }

    return mapping.get(category, 1.0)


def _market_demand_multiplier(market: str) -> float:
    market = str(market).strip().upper()

    mapping = {
        "US": 1.20,
        "EU": 1.00,
    }

    return mapping.get(market, 1.0)


def generate_media_spend_and_kpis(
    start_date,
    weeks: int,
    category: str,
    market: str,
    channels: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    spend_rows = []
    kpi_rows = []

    category_mult = _category_demand_multiplier(category)
    market_mult = _market_demand_multiplier(market)

    for i in range(weeks):
        dt = pd.to_datetime(start_date) + pd.Timedelta(days=i * 7)

        annual_wave = math.sin(i / max(weeks, 1) * 2 * math.pi)
        half_wave = math.cos(i / max(weeks // 2, 1) * 2 * math.pi)

        week_factor = 1 + 0.18 * annual_wave
        demand_index = (100 + 14 * annual_wave + 5 * half_wave) * category_mult * market_mult

        total_spend = 0.0

        for channel, cfg in channels.items():
            shape = _channel_shape_defaults(channel)

            seasonality = cfg.get("seasonality", shape["seasonality"])
            ctr = cfg.get("ctr", shape["ctr"])
            impression_multiplier = cfg.get("impression_multiplier", shape["impression_multiplier"])

            base_spend = float(cfg["base_spend"])
            seasonal_component = 1 + seasonality * math.sin(i / max(weeks, 1) * 2 * math.pi + len(channel))
            spend = base_spend * week_factor * seasonal_component

            impressions = max(spend * impression_multiplier, 0.0)
            clicks = max(impressions * ctr, 0.0)

            spend_rows.append(
                {
                    "dt": dt.date(),
                    "category": category,
                    "market": market,
                    "channel": channel,
                    "spend": round(spend, 2),
                    "impressions": round(impressions, 0),
                    "clicks": round(clicks, 0),
                }
            )

            total_spend += spend

        revenue = (
            40000
            + (demand_index * 280)
            + (total_spend * 0.85)
            + (5000 * category_mult)
            + (3000 * market_mult)
        )
        orders = revenue / 95
        sessions = 10000 + demand_index * 55 + total_spend * 0.07

        kpi_rows.append(
            {
                "dt": dt.date(),
                "category": category,
                "market": market,
                "sessions": round(sessions, 0),
                "orders": round(orders, 0),
                "revenue": round(revenue, 2),
                "baseline_demand_index": round(demand_index, 2),
            }
        )

    return pd.DataFrame(spend_rows), pd.DataFrame(kpi_rows)