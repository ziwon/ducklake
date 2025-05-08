# ──────────────────────────────────────────────────────────────
#  File:  src/jobs/spark/quotes_ingest.py
#  Desc:  Pulls OHLCV data from Yahoo Finance for a specific date
#         and appends it to an Iceberg table using Nessie Catalog.
#         Designed to be run via Spark, orchestrated by Airflow.
# ──────────────────────────────────────────────────────────────

import argparse
import logging
import os
from datetime import datetime, date

import pandas as pd
import yfinance as yf
from typing import List, Optional
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, lit, to_date
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    DateType,
    DoubleType,
    LongType,
)


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Configuration (Fetched from Environment Variables or Arguments) ---
NESSIE_URI = os.getenv("NESSIE_URI", "http://nessie:19120/api/v1")
MINIO_ENDPOINT_URL = os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minio123")
ICEBERG_WAREHOUSE_PATH = os.getenv("ICEBERG_WAREHOUSE_PATH", "s3a://iceberg")
TARGET_CATALOG = os.getenv("TARGET_CATALOG", "nessie")
TARGET_DB = os.getenv("TARGET_DB", "default")
TARGET_TABLE_NAME = os.getenv("TARGET_TABLE_NAME", "stock_prices")
NESSIE_REF = os.getenv("NESSIE_REF", "main")

TARGET_TABLE_FULL_NAME = f"{TARGET_CATALOG}.{TARGET_DB}.{TARGET_TABLE_NAME}"

# --- Helper Functions ---

def parse_arguments():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Ingest stock quotes for a specific date using Nessie.")
    parser.add_argument(
        "--trade-date",
        type=str,
        required=True,
        help="The date for which to fetch data (YYYY-MM-DD). Typically {{ ds }} from Airflow.",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        required=True,
        help="Comma-separated list of stock tickers (e.g., 'AAPL,MSFT,GOOGL').",
    )
    return parser.parse_args()

def get_spark_session() -> SparkSession:
    """
    Initializes and returns a SparkSession configured for Iceberg with Nessie Catalog and S3.
    Relies on configurations passed via spark-submit command (e.g., by DockerOperator).
    """
    logger.info("Initializing Spark session (expecting Nessie/S3 config via spark-submit)...")
    if not all([MINIO_ENDPOINT_URL, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, NESSIE_URI]):
         raise ValueError("Missing required environment variables MINIO_*, NESSIE_URI.")

    try:
        spark = SparkSession.builder.appName("quotes_ingest_nessie_docker").getOrCreate()
        logger.info("Spark session initialized successfully.")
        return spark
    except Exception as e:
        logger.error(f"Failed to create Spark session: {e}", exc_info=True)
        raise

def fetch_quotes(tickers: List[str], fetch_date: date) -> Optional[pd.DataFrame]:
    """Fetches stock data for the given tickers and date using yfinance."""
    logger.info(f"Fetching quotes for {tickers} on {fetch_date.strftime('%Y-%m-%d')}")
    try:
        fetch_end_date = fetch_date + pd.Timedelta(days=7)
        pdf = yf.download(
            tickers=tickers,
            start=fetch_date.strftime("%Y-%m-%d"),
            end=fetch_end_date.strftime("%Y-%m-%d"),
            group_by="ticker",
            threads=True,
            auto_adjust=False,
            progress=False,
        )

        if pdf.empty:
            logger.warning(f"No data returned from yfinance for {tickers} on {fetch_date}.")
            return None

        if isinstance(pdf.columns, pd.MultiIndex):
            pdf = pdf.stack(level=0)
            pdf.index.names = ["trade_date_ts", "symbol"]
            pdf = pdf.reset_index()
        else:
            pdf = pdf.reset_index().rename(columns={"Date": "trade_date_ts"})
            pdf["symbol"] = tickers[0]

        pdf = pdf.rename(
            columns={
                "trade_date_ts": "trade_date_ts",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
            }
        )
        
        logger.info(f"Columns after rename: {pdf.columns.tolist()}")

        if "trade_date_ts" not in pdf.columns:
            logger.error("'trade_date_ts' column not found after rename. Check 'Date' column name after reset_index.")
            return None

        pdf["trade_date"] = pd.to_datetime(pdf["trade_date_ts"]).dt.date
        
        if "symbol" not in pdf.columns:
            logger.error(f"'symbol' column is missing before filter. Current columns: {pdf.columns.tolist()}")
            return None

        pdf = pdf.filter(items=["trade_date", "open", "high", "low", "close", "adj_close", "volume", "symbol"])
        
        logger.info(f"Columns after filter: {pdf.columns.tolist()}")

        pdf = pdf[pdf['trade_date'] == fetch_date]

        logger.info(f"Columns in quotes_pdf before returning: {pdf.columns.tolist()}")
        logger.info(f"First 5 rows of quotes_pdf before returning:\n{pdf.head().to_string()}")

        logger.info(f"Successfully fetched {len(pdf)} records.")
        return pdf

    except Exception as e:
        logger.error(f"Error fetching data from yfinance: {e}", exc_info=True)
        return None

def define_schema() -> StructType:
    """Defines the explicit schema for the stock_prices table."""
    return StructType(
        [
            StructField("trade_date", DateType(), False),
            StructField("open", DoubleType(), True),
            StructField("high", DoubleType(), True),
            StructField("low", DoubleType(), True),
            StructField("close", DoubleType(), True),
            StructField("adj_close", DoubleType(), True),
            StructField("volume", LongType(), True),
            StructField("symbol", StringType(), False),
        ]
    )

def create_table_if_not_exists(spark: SparkSession, schema: StructType):
    """Creates the Iceberg table using Nessie catalog if it doesn't exist."""
    logger.info(f"Checking if table {TARGET_TABLE_FULL_NAME} exists on ref '{NESSIE_REF}'...")
    try:
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {TARGET_CATALOG}.{TARGET_DB}")
        logger.info(f"Database {TARGET_CATALOG}.{TARGET_DB} ensured to exist.")

        spark.sql(f"""
            CREATE TABLE IF NOT EXISTS {TARGET_TABLE_FULL_NAME} (
                trade_date DATE,
                open       DOUBLE,
                high       DOUBLE,
                low        DOUBLE,
                close      DOUBLE,
                adj_close  DOUBLE,
                volume     BIGINT,
                symbol     STRING
            )
            USING iceberg
            PARTITIONED BY (symbol, days(trade_date)) -- Partition by symbol and day
            -- Optional: Add table properties
            TBLPROPERTIES ('write.format.default'='parquet', 'nessie.commit.message'='Initial table creation')
        """)
        logger.info(f"Table {TARGET_TABLE_FULL_NAME} ensured to exist on ref '{NESSIE_REF}'.")
    except Exception as e:
        logger.error(f"Failed to create or verify table {TARGET_TABLE_FULL_NAME}: {e}", exc_info=True)
        raise

def check_data_exists(spark: SparkSession, fetch_date: date, tickers: list[str]) -> bool:
    """Checks if data for the given date and tickers already exists in the table on the specific Nessie ref."""
    try:
        logger.info(f"Checking for existing data in {TARGET_TABLE_FULL_NAME} for date {fetch_date} and tickers {tickers} on ref '{NESSIE_REF}'...")
        date_str = fetch_date.strftime('%Y-%m-%d')
        ticker_list_str = ', '.join(f"'{t}'" for t in tickers)
        query = f"""
            SELECT 
                COUNT(*) as count
            FROM 
                {TARGET_TABLE_FULL_NAME}
            WHERE 
                trade_date = '{date_str}' 
            AND 
                symbol IN ({ticker_list_str})
        """
        count_df = spark.sql(query)
        count = count_df.first()["count"]
        exists = count > 0
        logger.info(f"Data check complete. Found {count} existing records. Exists: {exists}")
        return exists
    except Exception as e:
        logger.warning(f"Could not check for existing data in {TARGET_TABLE_FULL_NAME} (might be first run or SQL error): {e}")
        return False


def append_data(spark: SparkSession, df: DataFrame):
    """Appends the DataFrame to the target Iceberg table using Nessie."""
    logger.info(f"Appending {df.count()} rows to {TARGET_TABLE_FULL_NAME} on ref '{NESSIE_REF}'...")
    try:
        (
            df.writeTo(TARGET_TABLE_FULL_NAME)
            .append()
        )
        logger.info("Data appended successfully.")
    except Exception as e:
        logger.error(f"Failed to append data to {TARGET_TABLE_FULL_NAME}: {e}", exc_info=True)
        raise

# --- Main Execution Logic ---

def main():
    args = parse_arguments()
    try:
        trade_date_obj = datetime.strptime(args.trade_date, "%Y-%m-%d").date()
        tickers_list = [ticker.strip().upper() for ticker in args.tickers.split(",")]
    except ValueError as e:
        logger.error(f"Invalid argument format: {e}")
        exit(1)

    spark = None
    try:
        spark = get_spark_session()
        schema = define_schema()

        create_table_if_not_exists(spark, schema)

        if check_data_exists(spark, trade_date_obj, tickers_list):
            logger.warning(f"Data for {trade_date_obj} and tickers {tickers_list} already exists in {TARGET_TABLE_FULL_NAME} on ref '{NESSIE_REF}'. Skipping ingestion.")
            return

        quotes_pdf = fetch_quotes(tickers_list, trade_date_obj)

        if quotes_pdf is None or quotes_pdf.empty:
            logger.warning("No data fetched from yfinance. Nothing to ingest.")
            return

        try:
            quotes_df = spark.createDataFrame(quotes_pdf, schema=schema)
        except Exception as e:
            logger.error(f"Failed to create Spark DataFrame: {e}", exc_info=True)
            raise

        append_data(spark, quotes_df)

        logger.info(f"Ingestion process to {TARGET_TABLE_FULL_NAME} on ref '{NESSIE_REF}' completed successfully.")

    except Exception as e:
        logger.error(f"An error occurred during the Nessie ingestion process: {e}", exc_info=True)
        raise

    finally:
        if spark:
            logger.info("Stopping Spark session.")
            spark.stop()


if __name__ == "__main__":
    main()
