### ✨ What is Ducklake?
Ducklake is a minimalist, cloud-native data catalog and lakehouse engine designed for:
- Interactive analytics via DuckDB
- GitOps-style data versioning via Project Nessie
- Reliable, schema-evolving lake storage via Apache Iceberg
- Object-store-first design (S3, MinIO)

It enables building small, private ponds of structured or semi-structured data — "smallponds" — to power deep semantic search, dashboards, experimentation, and governed ML workflows.

### 🧱 Architecture Overview

     ┌────────────┐       Git-style Metadata        ┌────────────┐
     │  DuckDB    │  <--------------------------->  │   Nessie   │
     │  (Read)    │                                 └────────────┘
     └────┬───────┘                                        ▲
          │        Snapshot-aware Reads                    │
     ┌────▼───────┐   (Iceberg table metadata)       Branch/Tag Mgmt
     │  Spark     │  ------------------------------>  (REST API)
     │  (Ingest)  │
     └────┬───────┘
          │        Parquet/ORC + Manifest Storage
     ┌────▼───────┐     (Iceberg format v2)
     │   MinIO    │  <------------------------------┐
     │ (S3 API)   │                                 │
     └────────────┘                            Write once
                                                append-only
### 🔧 Features
- 🚀 GitOps for data — safely test and deploy schema + data changes with Nessie branches
- 🧊 Iceberg v2 catalog — schema evolution, time travel, rollback
- 🦆 DuckDB-native — interactive SQL queries and metadata inspection
- ☁️ Object-storage first — runs on MinIO, AWS S3, GCS, or Azure Blob
- ⚙️ Composable services — minimal Docker Compose stack; ready for CI/CD and K8s
- 📦 On-demand Spark ingestion — run by Airflow DAGs using ephemeral containers
- 🧪 Backwards-compatible HiveCatalog (optional, for legacy engines)

### 🌱 Use Cases
- Lightweight data discovery (DeepSearch-style)
- Branchable ML training datasets
- Interactive notebook exploration with DuckDB
- Analytics versioning & reproducibility
- GitHub Actions–driven data pipeline promotion (e.g. dev → staging → prod)

### 🚀 Quickstart (dev)

```
# Hive mode (default)
docker compose -f compose/base/docker-compose.base.yml \
               -f compose/hive/docker-compose.hive.yml up -d

# Or: Project Nessie mode
docker compose -f compose/base/docker-compose.base.yml \
               -f compose/nessie/docker-compose.nessie.yml up -d
```
Trigger an Airflow DAG run via UI or airflow dags trigger ingest_quotes.

### 📍 Roadmap 
- Web UI for data lineage + schema diffing
- CLI for Nessie-backed data versioning (ducklake branch, ducklake merge)
- Federated metadata search over smallponds
- Optional GPU-native ingestion (Spark RAPIDS / DuckDB extensions)
- Iceberg/Delta/Hudi hybrid catalog support
- Data validation with Great Expectations (Auto data-docs per Nessie branch)
- Semantic modeling with dbt (CI validation before table promotion)
