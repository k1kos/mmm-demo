# Media Mix Scenario Planner

https://mmm-demo.streamlit.app/

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

## Deploy to Streamlit Community Cloud

Use `app.py` as the app entrypoint.

### 1. Push the repo to GitHub

Make sure the repository includes:

- `app.py`
- `requirements.txt`
- `config/settings.yaml`
- `src/`

Do not commit local credentials. This repo now ignores:

- `.env`
- `.streamlit/secrets.toml`
- common service account JSON filenames

### 2. Create the Streamlit app

In Streamlit Community Cloud:

- select your GitHub repo
- set the main file path to `app.py`
- deploy the app

### 3. Add secrets in Streamlit Cloud

In the app settings, open `Secrets` and paste values based on `.streamlit/secrets.toml.example`.

Required secrets:

- `GOOGLE_CLOUD_PROJECT`
- `BQ_DATASET`
- `DEFAULT_CATEGORY`
- `DEFAULT_MARKET`
- `OPENAI_API_KEY`
- `[gcp_service_account]` with the full Google service account JSON fields

### 4. BigQuery access

The service account must have permission to:

- read benchmark and KPI tables
- write scenario history tables

If your dataset and tables are not created yet, run the local setup scripts before deployment.

### 5. Local development

For local runs, the app supports:

- `.env`
- `GOOGLE_APPLICATION_CREDENTIALS`
- a root-level service account JSON file
- Streamlit secrets

For Streamlit Cloud deployment, prefer `Secrets` instead of committing a JSON key file.

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
