-- Airflow
CREATE USER airflow WITH ENCRYPTED PASSWORD 'airflow';
CREATE DATABASE airflow OWNER airflow;
GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow;

-- Hive Metastore DB
CREATE USER hive  WITH ENCRYPTED PASSWORD 'hive';
CREATE DATABASE metastore OWNER hive;
GRANT ALL PRIVILEGES ON DATABASE metastore TO hive;

-- Nessie persistence DB
CREATE USER nessie WITH ENCRYPTED PASSWORD 'nessie';
CREATE DATABASE nessie OWNER nessie;
GRANT ALL PRIVILEGES ON DATABASE nessie TO nessie;