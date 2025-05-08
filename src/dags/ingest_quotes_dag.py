"""
DAG: ingest_daily_quotes_docker
Runs on weekdays at 17:00 UTC (≅02:00 KST+1) after US market close.
Submits a Spark job using DockerOperator to ingest data into Nessie/Iceberg.
"""

import os
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from datetime import datetime, timedelta
from airflow.models.dag import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.operators.empty import EmptyOperator
from airflow.models.param import Param
from airflow.utils.trigger_rule import TriggerRule
from airflow.utils.state import State

# --- Configuration ---
DOCKER_CONN_ID = "docker_default"
SPARK_APP_DOCKER_IMAGE = "registry:5000/spark-quotes-ingest:latest"
DOCKER_NETWORK = os.getenv("COMPOSE_PROJECT_NAME", "ducklake") + "_data-net"

SPARK_MASTER_URL = "spark://spark-master:7077"
SPARK_APP_FILE_PATH = "/app/quotes_ingest.py"
NESSIE_URI = os.getenv("AIRFLOW_VAR_NESSIE_URI", "http://nessie:19120/api/v1")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minio123")
MINIO_ENDPOINT_URL = os.getenv("AIRFLOW_VAR_MINIO_ENDPOINT_URL", "http://minio:9000")
ICEBERG_WAREHOUSE_PATH = os.getenv("AIRFLOW_VAR_ICEBERG_WAREHOUSE_PATH", "s3a://iceberg")
TARGET_CATALOG = os.getenv("AIRFLOW_VAR_TARGET_CATALOG", "nessie")
TARGET_DB = os.getenv("AIRFLOW_VAR_TARGET_DB", "default")
TARGET_TABLE_NAME = os.getenv("AIRFLOW_VAR_TARGET_TABLE_NAME", "stock_prices")
NESSIE_REF = os.getenv("AIRFLOW_VAR_NESSIE_REF", "main")

MINIO_CONN_ID = "minio_s3_conn"

# --- Default Arguments ---
default_args = {
    "owner": "ducklake-docker",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "docker_conn_id": DOCKER_CONN_ID,
}

# --- DAG Definition ---
with DAG(
    dag_id="ingest_daily_quotes_docker_nessie",
    default_args=default_args,
    start_date=datetime(2025, 5, 5),
    schedule="0 17 * * 1-5",        # Mon-Fri at 17:00 UTC
    catchup=False,
    tags=["finance", "iceberg", "nessie", "docker"],
    doc_md="""
    ### Ingest Daily Stock Quotes via Spark (DockerOperator) into Nessie

    Fetches daily OHLCV data from Yahoo Finance for specified tickers
    and appends it to an Iceberg table managed by Nessie Catalog, stored in MinIO.

    Uses Airflow's DockerOperator to run the Spark job container,
    connecting to the Spark cluster running within the Docker Compose environment.

    **Parameters:**
    - `tickers`: Comma-separated list of stock symbols (default: AAPL,MSFT,GOOGL).
    - `logical_date`: The logical date for the DAG run (YYYY-MM-DD).
    """,
    params={
        "tickers": Param("AAPL,MSFT,GOOGL", type="string", title="Tickers", description="Comma-separated stock symbols to ingest."),
    }
) as dag:

    start = EmptyOperator(task_id="start")

    # Construct the spark-submit command to run inside the DockerOperator container
    # Note: Templated fields {{ ds }} and {{ params.tickers }} are handled by Airflow
    # Environment variables like ${NESSIE_URI} are substituted by DockerOperator
    spark_submit_command = f"""
    spark-submit \
        --master {SPARK_MASTER_URL} \
        --deploy-mode client \
        --driver-memory 1g \
        --executor-memory 2g \
        --executor-cores 1 \
        --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.9.0,org.projectnessie.nessie-integrations:nessie-spark-extensions-3.5_2.12:0.103.6,org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.671 \
        --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions,org.projectnessie.spark.extensions.NessieSparkSessionExtensions \
        --conf spark.sql.catalog.{TARGET_CATALOG}=org.apache.iceberg.spark.SparkCatalog \
        --conf spark.sql.catalog.{TARGET_CATALOG}.catalog-impl=org.apache.iceberg.nessie.NessieCatalog \
        --conf spark.sql.catalog.{TARGET_CATALOG}.uri={NESSIE_URI} \
        --conf spark.sql.catalog.{TARGET_CATALOG}.ref={NESSIE_REF} \
        --conf spark.sql.catalog.{TARGET_CATALOG}.authentication.type=NONE \
        --conf spark.sql.catalog.{TARGET_CATALOG}.warehouse={ICEBERG_WAREHOUSE_PATH} \
        --conf spark.hadoop.fs.s3a.endpoint={MINIO_ENDPOINT_URL} \
        --conf spark.hadoop.fs.s3a.access.key={MINIO_ACCESS_KEY} \
        --conf spark.hadoop.fs.s3a.secret.key={MINIO_SECRET_KEY} \
        --conf spark.hadoop.fs.s3a.path.style.access=true \
        --conf spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem \
        {SPARK_APP_FILE_PATH} \
        --trade-date {{{{ ds }}}} \
        --tickers {{{{ params.tickers }}}}
    """
    logger.info(f"Spark submit command: {spark_submit_command}")

    spark_ingest_docker = DockerOperator(
        task_id="spark_ingest_quotes_docker",
        image=SPARK_APP_DOCKER_IMAGE,
        command=spark_submit_command,
        mount_tmp_dir=False,
        network_mode=DOCKER_NETWORK,
        auto_remove=True,
        api_version="auto",
        environment={
            "NESSIE_URI": NESSIE_URI,
            "MINIO_ENDPOINT_URL": MINIO_ENDPOINT_URL,
            "ICEBERG_WAREHOUSE_PATH": ICEBERG_WAREHOUSE_PATH,
            "TARGET_CATALOG": TARGET_CATALOG,
            "TARGET_DB": TARGET_DB,
            "TARGET_TABLE_NAME": TARGET_TABLE_NAME,
            "NESSIE_REF": NESSIE_REF,
            "MINIO_ACCESS_KEY": f"{{{{ conn.{MINIO_CONN_ID}.login }}}}",
            "MINIO_SECRET_KEY": f"{{{{ conn.{MINIO_CONN_ID}.password }}}}",
            "PYTHONUNBUFFERED": "1"
        },
        force_pull=True,
        docker_conn_id="docker_default",
        tty=True,
    )

    end_success = EmptyOperator(task_id="end_success")

    end_failure = EmptyOperator(
        task_id="end_failure",
        trigger_rule=TriggerRule.ONE_FAILED
    )

    start >> spark_ingest_docker
    spark_ingest_docker >> end_success
    spark_ingest_docker >> end_failure

