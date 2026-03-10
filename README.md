# Media Mix Scenario Planner

A benchmark-based media mix demo app built with:

- BigQuery
- Python
- Streamlit

The app lets a user change spend by media channel and see a directional estimate of how projected sales may change.

This is a **proof-of-concept simulator**, not a true marketing mix model.  
It uses synthetic benchmark assumptions and synthetic KPI generation for demo purposes.

---

## What the app does

The user can:

- select a category
- select a market
- enter spend by media channel
- run a scenario
- see projected revenue impact

The app supports both **offline** and **digital** media.

### Offline channels
- TV
- OOH
- Radio
- Print

### Digital channels
- Paid Search
- Social Media
- Online Video
- Display
- Email

### Demo categories
- Beverages
- Automotive
- Banking
- Retail
- Telecom
- Travel
- Insurance
- Pharma

### Demo markets
- US
- EU

---

## Important limitation

This project does **not** use brand-specific historical sales and media data.

That means:

- outputs are directional
- outputs are benchmark-based
- outputs should not be used as real forecasts
- this is a demo / prototype tool

---

## Project structure

```text
mmm-demo/
├─ app.py
├─ README.md
├─ requirements.txt
├─ .env.example
├─ config/
│  ├─ settings.yaml
│  └─ benchmark_channel_curves.csv
├─ sql/
│  └─ 01_create_tables.sql
├─ src/
│  ├─ __init__.py
│  ├─ bq.py
│  ├─ config.py
│  ├─ generators.py
│  ├─ main_generate_demo_data.py
│  ├─ main_load_benchmarks.py
│  ├─ model.py
│  └─ scenario_service.py