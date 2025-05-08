import boto3
import json

# Define Minio connection parameters
minio_client = boto3.client(
    's3',
    endpoint_url='http://localhost:9000',  # Minio IP address from docker inspect
    aws_access_key_id='minio',
    aws_secret_access_key='minio123',
    region_name='us-east-1'
)

# Specify the bucket and metadata file path
bucket_name = 'iceberg'
metadata_file_key = 'default/stock_prices_ff743113-f0dc-4c09-b45b-7445943cb832/metadata/00001-71df54f3-4533-440d-9bfb-07c170d1c0ec.metadata.json'

# Download the metadata file
metadata_file = minio_client.get_object(Bucket=bucket_name, Key=metadata_file_key)
metadata_content = metadata_file['Body'].read().decode('utf-8')

# Parse and print the metadata content
metadata_json = json.loads(metadata_content)
print(json.dumps(metadata_json, indent=4))

# Download the metadata file
metadata_file = minio_client.get_object(Bucket=bucket_name, Key=metadata_file_key)
metadata_content = metadata_file['Body'].read().decode('utf-8')

# Parse and print the metadata content
metadata_json = json.loads(metadata_content)
print(json.dumps(metadata_json, indent=4))