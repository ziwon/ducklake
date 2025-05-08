from pyiceberg.catalog import load_catalog
from pyiceberg.io.pyarrow import PyArrowFileIO
import duckdb
import os

# 환경 변수 설정
nessie_api_uri = "http://nessie:19120"
s3_endpoint_url = "http://minio:9000"

os.environ["AWS_S3_ENDPOINT"] = s3_endpoint_url  
os.environ["AWS_ACCESS_KEY_ID"] = "minio"
os.environ["AWS_SECRET_ACCESS_KEY"] = "minio123"
os.environ["AWS_S3_ALLOW_UNSAFE_RENAME"] = "true" 
os.environ["AWS_S3_ADDRESSING_STYLE"] = "path"  

# Iceberg 카탈로그 속성.. not working
catalog_properties = {
    "uri": f"{nessie_api_uri}/api",  
    "config": "",  
    "ref": "main",
    "type": "rest",  
    "io-impl": "org.apache.iceberg.aws.s3.S3FileIO",  
    "s3.endpoint": s3_endpoint_url,  
    "s3.access-key-id": "minio",
    "s3.secret-access-key": "minio123",
    "s3.path-style-access": "true",  
}

try:
    
    catalog = load_catalog(
        name="stock_prices",
        **catalog_properties
    )

    table_identifier = "default.stock_prices"
    print(f"Attempting to load table: {table_identifier}")
    table = catalog.load_table(table_identifier)
    print(f"Table '{table_identifier}' loaded successfully. Schema: {table.schema()}")

    
    print("Scanning table with DuckDB...")
    duckdb_conn = duckdb.connect()  #   
    scan = table.scan()
    arrow_table = scan.to_arrow()   
    duckdb_conn.register("stock_prices", arrow_table)   

    result = duckdb_conn.execute("SELECT * FROM stock_prices LIMIT 10").fetchall()
    print("Query Result:")
    print(result)

except Exception as e:
    print(f"An error occurred: {e}")
    import traceback
    traceback.print_exc()

finally:
    if 'duckdb_conn' in locals():
        duckdb_conn.close()  # DuckDB 연결 종료