CREATE TABLE IF NOT EXISTS `data-uplaod.mmm_demo.benchmark_channel_curves` (
  category STRING,
  market STRING,
  channel_group STRING,
  channel STRING,
  subchannel STRING,
  roi_low FLOAT64,
  roi_mid FLOAT64,
  roi_high FLOAT64,
  adstock_rate FLOAT64,
  saturation_alpha FLOAT64,
  saturation_gamma FLOAT64,
  max_efficient_spend FLOAT64,
  confidence_score FLOAT64,
  source_label STRING,
  suggested_spend FLOAT64
);

CREATE TABLE IF NOT EXISTS `data-uplaod.mmm_demo.demo_media_spend` (
  dt DATE,
  category STRING,
  market STRING,
  channel STRING,
  spend FLOAT64,
  impressions FLOAT64,
  clicks FLOAT64
);

CREATE TABLE IF NOT EXISTS `data-uplaod.mmm_demo.demo_business_kpis` (
  dt DATE,
  category STRING,
  market STRING,
  sessions FLOAT64,
  orders FLOAT64,
  revenue FLOAT64,
  baseline_demand_index FLOAT64
);

CREATE TABLE IF NOT EXISTS `data-uplaod.mmm_demo.scenario_inputs` (
  scenario_id STRING,
  created_at TIMESTAMP,
  category STRING,
  market STRING,
  channel_group STRING,
  channel STRING,
  spend FLOAT64
);

CREATE TABLE IF NOT EXISTS `data-uplaod.mmm_demo.scenario_results` (
  scenario_id STRING,
  created_at TIMESTAMP,
  category STRING,
  market STRING,
  channel_group STRING,
  channel STRING,
  subchannel STRING,
  spend FLOAT64,
  incremental_revenue_low FLOAT64,
  incremental_revenue_mid FLOAT64,
  incremental_revenue_high FLOAT64,
  roi_low FLOAT64,
  roi_mid FLOAT64,
  roi_high FLOAT64,
  saturation_flag BOOL,
  baseline_revenue FLOAT64,
  total_revenue_low FLOAT64,
  total_revenue_mid FLOAT64,
  total_revenue_high FLOAT64,
  confidence_score FLOAT64,
  source_label STRING
);