from google.cloud import bigquery
from google.api_core.retry import Retry
import pandas as pd

BQ_RETRY = Retry(
    initial=1.0,
    maximum=20.0,
    multiplier=2.0,
    deadline=120.0,
)

def get_client(project_id: str) -> bigquery.Client:
    return bigquery.Client(project=project_id)

def load_dataframe(
    client: bigquery.Client,
    dataframe: pd.DataFrame,
    table_fqn: str,
    write_disposition: str = "WRITE_APPEND",
) -> None:
    job_config = bigquery.LoadJobConfig(write_disposition=write_disposition)
    job = client.load_table_from_dataframe(
        dataframe,
        table_fqn,
        job_config=job_config,
        timeout=120,
    )
    job.result(retry=BQ_RETRY)

def run_query(client: bigquery.Client, query: str) -> pd.DataFrame:
    return client.query(query).to_dataframe()
