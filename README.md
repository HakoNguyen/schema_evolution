# ⚡ Schema Evolution Core Engine

> **Enterprise Real-Time Schema Governance, Risk Classification & Event-Driven DDL Auto-Synchronizer for Data Warehouses & Streaming Pipelines.**

![Schema Evolution Architecture](docs/images/architecture_banner.png)

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2-blue.svg)](https://reactjs.org/)
[![Redpanda Kafka](https://img.shields.io/badge/Streaming-Redpanda%20Kafka-red.svg)](https://redpanda.com/)
[![Debezium CDC](https://img.shields.io/badge/CDC-Debezium-orange.svg)](https://debezium.io/)
[![ClickHouse](https://img.shields.io/badge/Warehouse-ClickHouse-yellow.svg)](https://clickhouse.com/)
[![Apache SeaTunnel](https://img.shields.io/badge/Ingestion-Apache%20SeaTunnel-teal.svg)](https://seatunnel.apache.org/)

---

## 📖 Table of Contents
1. [Overview & Problem Statement](#-overview--problem-statement)
2. [Architecture Topology](#-architecture-topology)
3. [Core Features](#-core-features)
4. [Project Directory Structure](#-project-directory-structure)
5. [Quick Start Guide](#-quick-start-guide)
6. [Supported Databases & Type Mapping](#-supported-databases--type-mapping)
7. [Verification & Benchmark Results](#-verification--benchmark-results)

---

## 🎯 Overview & Problem Statement

### The Problem: Schema Drift in Real-Time Pipelines
In modern enterprise data platforms, backend developers frequently modify source database structures (adding columns, renaming fields, dropping attributes). In traditional Data Engineering pipelines:
- When a new attribute is inserted at the Source, the Data Sink Connector fails because the target table in the Data Warehouse lacks the new column.
- This causes **pipeline crashes (502/Data Loss)**, requiring Data Engineers to manually inspect JSON payloads and manually run `ALTER TABLE` DDL queries on target warehouses.

### The Solution: Schema Evolution Core Engine
**Schema Evolution Core** acts as an automated, intelligent **Smart Gatekeeper**:
- **Non-Breaking Changes (Adding Columns, Widening Types)**: When a CDC event arrives (or the fallback scheduler fires), the engine re-crawls the source table metadata, diffs it against the Schema Registry baseline, and automatically executes `ALTER TABLE target ...` on the ClickHouse / MySQL / Postgres target.
- **Breaking Changes (Dropping / Renaming / Narrowing Columns)**: Marks the table as **FROZEN in the Schema Registry**, stores the new schema as a draft, sends a Telegram alert, and waits for a Data Engineer to run a **Sandbox test** and approve or reject it. No DDL is executed on the target until approval.

> **Scope note.** The engine governs the *schema* (control plane) only. It does **not** pause the data plane (SeaTunnel / Kafka Connect sinks), and control plane and data plane run in parallel — so there is no ordering guarantee that an auto `ALTER TABLE` lands before the first row carrying the new column reaches the target. A "frozen" table means "schema changes on hold", not "data ingestion stopped".

---

## 🏛️ Architecture Topology

```mermaid
graph LR
    subgraph SOURCES["1. Source Databases"]
        PG[("PostgreSQL")]
        MY[("MySQL")]
        MG[("MongoDB")]
    end

    subgraph BUS["2. Event Streaming Bus"]
        K["Redpanda / Kafka Broker"]
    end

    subgraph CONTROL["3. Control Plane (Schema Evolution Engine)"]
        E["FastAPI Core Engine"]
        C{"Impact Assessment"}
        AUTO["Auto DDL Engine"]
        FREEZE["Pipeline Freeze & Telegram Alert"]
    end

    subgraph DATA["4. Data Plane (Row Ingestion Cluster)"]
        ST["Apache SeaTunnel / Sink Connectors"]
    end

    subgraph TARGETS["5. Target Warehouses"]
        CH[("ClickHouse Warehouse")]
        TGT[("MySQL Target DB")]
    end

    PG & MY & MG -->|Debezium CDC| K

    %% Parallel Control Plane Flow (DDL & Schema Evolution)
    K -->|"CDC events (trigger re-crawl)"| E
    E -.->|"crawl metadata"| PG & MY & MG
    E --> C
    C -->|"Non-Breaking"| AUTO
    C -->|"Breaking Risk"| FREEZE
    AUTO -->|"ALTER TABLE (DDL)"| CH & TGT

    %% Parallel Data Plane Flow (Row Ingestion)
    K -->|"Data Rows Stream"| ST
    ST -->|"INSERT Rows"| CH & TGT

    style CONTROL fill:#f8f9fa,stroke:#0d6efd,stroke-width:2px
    style DATA fill:#fff3cd,stroke:#ffc107,stroke-width:2px
    style TARGETS fill:#d1e7dd,stroke:#198754,stroke-width:2px
```

### 🧰 Technology Stack Ecosystem
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18+-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Redpanda](https://img.shields.io/badge/Redpanda_Kafka-CDC-FF2E00?style=for-the-badge&logo=redpanda&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0+-4479A1?style=for-the-badge&logo=mysql&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-6.0+-47A248?style=for-the-badge&logo=mongodb&logoColor=white)
![ClickHouse](https://img.shields.io/badge/ClickHouse-23.8+-FFCC00?style=for-the-badge&logo=clickhouse&logoColor=black)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)

---

## ✨ Core Features

### 1. Event-Driven Real-Time CDC & Payload Extractor
- Subscribes directly to Debezium Kafka topics (`mysql_self_monitor`, `pg_to_mysql`, `mongo_to_clickhouse`).
- **Dynamic JSON Payload Extractor**: Inspects raw JSON CDC messages (`{ "id": ..., "data": { ... }, "ts_ms": ..., "op": ... }`), extracts new key attributes, and infers normalized engine-agnostic datatypes (`Int32`, `Float64`, `Bool`, `DateTime`, `String`).

### 2. Config-as-Code & Multitenant Registry
- Declarative YAML pipeline definitions (`config/pipelines/*.yaml`).
- Grouped enterprise registry layout: `data/registry/<pipeline_name>/<table_name>.json`.
- Automatic legacy file migration and pipeline metadata tracking.

### 3. Automated Risk Classification Engine
- **NON-BREAKING**: Nullable / defaulted column additions, widening (`varchar(50)→varchar(100)`, `int→bigint`, `numeric(10,2)→numeric(12,2)`), `NOT NULL→NULL`, dropping a foreign key ➔ DDL auto-executed on the target.
- **BREAKING**: Column drops, renames (heuristic: one-to-one match of an identical column definition), narrowing (incl. unbounded `varchar→varchar(n)` and lost `numeric` precision/scale), incompatible type changes, `NULL→NOT NULL`, PK / FK changes ➔ table frozen in the registry, draft saved, Telegram alert.
- Not yet detected: changes to a column's `DEFAULT` value.

### 4. Interactive Web Dashboard UI
- **Task / Flow Monitor**: Namespace-qualified table monitoring (`pipeline / table`).
- **Pipeline Topology**: Interactive node flow graph showing live DB statuses.
- **Live CDC Event Stream**: Real-time sliding audit log cards for incoming DDL events.
- **Low-Code Schema Editor**: Web UI for manual schema version management and approval.

---

## 📂 Project Directory Structure

```text
schema-evolution-core/
├── api/                         # FastAPI Web Server & Endpoints
│   ├── main.py                  # API Routes (/api/tables, /api/topology, /api/events)
│   ├── sandbox.py               # Sandbox Isolated Execution Engine
│   └── schema_editor.py         # Version Editor & Draft Management
├── app/                         # Background Workers & Pipeline Handlers
│   ├── kafka_consumer.py        # Event-driven CDC Kafka Consumer Thread
│   ├── payload_extractor.py     # Dynamic Payload Key Extractor & Type Inference
│   ├── event_log.py             # In-memory Audit Trail Ring Buffer
│   ├── scheduler.py             # Periodic Baseline Scanner
│   ├── unfreeze_cli.py          # Terminal CLI: list / view / approve / reject
│   └── app.py                   # Legacy Streamlit UI (registry-only)
├── config/                      # Config-as-Code Declarations
│   ├── main.yaml                # Core System Configuration
│   └── pipelines/               # Pipeline YAML Files (mongo_to_clickhouse, pg_to_mysql, etc.)
├── data/registry/               # Enterprise Schema Version Registry
│   ├── mongo_to_clickhouse/     # Registry files grouped by pipeline
│   ├── mysql_self_monitor/
│   └── pg_to_mysql/
├── debezium/                    # Debezium CDC Connector Configurations
│   ├── register_connectors.ps1  # Automated PowerShell Registration Script
│   └── mongo-source-connector.json
├── seatunnel/                   # Apache SeaTunnel Distributed Ingestion Cluster
│   ├── docker-compose.yml       # SeaTunnel Master & Worker Stack
│   └── jobs/                    # SeaTunnel Job Configurations (mongo_to_clickhouse.conf)
├── frontend/                    # React + Vite Web Dashboard
│   ├── src/components/          # PipelineTopology, LiveEventStream, TablesList, etc.
│   └── App.jsx
├── src/schema_evolution/        # Core Domain Library
│   ├── core.py                  # Evolution Engine & Registry Manager
│   ├── engines/                 # Database Drivers (MySQL, Postgres, ClickHouse, Mongo)
│   └── notification.py          # Telegram & Webhook Notifiers
├── tests/
│   ├── test_type_classification.py # Unit: widen/narrow classification (no infra needed)
│   ├── test_rename_heuristic.py    # Unit: rename detection + DDL generation (no infra needed)
│   ├── benchmark_core.py           # Standalone micro-benchmark of the core library
│   └── test_payload_pipeline.py    # Manual E2E script (needs the Docker stack running)
└── docker-compose.yml           # Full Infrastructure Stack (Postgres, MySQL, Mongo, ClickHouse, Redpanda)
```

---

## 🛠️ Quick Start Guide

### Prerequisites
- **Docker Desktop** (with Docker Compose)
- **Python 3.11+**
- **Node.js 18+** & npm

### 1. Launch Infrastructure Stack
Start all database containers (Postgres, MySQL, MongoDB, ClickHouse, Redpanda Kafka, Debezium Connect):
```bash
docker compose up -d
```

### 2. Register Debezium CDC Connectors
Register CDC source connectors for Postgres, MySQL, and MongoDB:
```powershell
.\debezium\register_connectors.ps1
```

### 3. Start FastAPI Backend Server
```bash
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run FastAPI server
uvicorn api.main:app --reload --port 8000
```

### 4. Start React Frontend Dashboard
```bash
cd frontend
npm install
npm run dev
```
Access the Web App Dashboard at: 👉 **`http://localhost:5173`**

### 5. (Alternative) Terminal CLI
Review frozen tables without the Web UI:

```bash
python -m app.unfreeze_cli list                          # frozen tables pending approval
python -m app.unfreeze_cli view    pg_to_mysql/customers # draft + breaking changes
python -m app.unfreeze_cli approve pg_to_mysql/customers # apply DDL on target, unfreeze
python -m app.unfreeze_cli reject  pg_to_mysql/customers # discard draft, keep baseline
```

---

## 📊 Supported Databases & Type Mapping

| Generic Type | PostgreSQL | MySQL | MongoDB | ClickHouse *(bọc `Nullable(...)` nếu nullable=True)* |
| :--- | :--- | :--- | :--- | :--- |
| **`int`** | `INTEGER` | `INT` | `Int32` | `Int32` |
| **`bigint`** | `BIGINT` | `BIGINT` | `Int64` | `Int64` |
| **`double`** | `DOUBLE PRECISION` | `DOUBLE` | `Double` | `Float64` |
| **`boolean`** | `BOOLEAN` | `TINYINT(1)` | `Bool` | `Bool` |
| **`timestamp`** | `TIMESTAMP` | `DATETIME` | `Date` | `DateTime` |
| **`varchar`** | `VARCHAR(255)` | `VARCHAR(255)` | `String` | `String` |
| **`text`** | `TEXT` | `TEXT` | `String` | `String` |

---

## 🧪 Verification & Benchmark Results

### Unit tests (no infrastructure needed)
```bash
python tests/test_type_classification.py
python tests/test_rename_heuristic.py
```

### Reproducible micro-benchmark (core library only)
Excludes Kafka, Debezium, SeaTunnel and all databases. Numbers depend on the machine.
```bash
python tests/benchmark_core.py
```

| Measurement | Workload | Result (dev laptop, Python 3.11) |
| :--- | :--- | :--- |
| `compare_schemas` latency | 30-column table, 3 diffs, 10,000 runs | ~80 µs / comparison |
| Payload extractor latency | 9-field JSON CDC message, 50,000 runs | ~23 µs / message |

### End-to-end demo (manual, one-off)
Measured by hand on the development machine with the full Docker stack running; there is no automated harness that reproduces these numbers.

| Test Scenario | Trigger Action | Measured Latency | Execution Outcome | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Non-breaking CDC DDL** | `ALTER TABLE customers ADD COLUMN age INT;` | **0.38s** | ClickHouse Target updated automatically | ✅ Passed |
| **Breaking Change Freeze** | `ALTER TABLE customers DROP COLUMN age;` | **0.12s** | Pipeline frozen, Telegram alert sent | ✅ Passed |
| **CDC Payload Extractor** | Publish raw JSON payload with 3 new attributes | **0.42s** | Extracted keys, auto `ALTER TABLE` on ClickHouse | ✅ Passed |
| **Sandbox Isolation** | Execute dry-run DDL on temporary schema | **0.85s** | Verified safely without touching production | ✅ Passed |
| **SeaTunnel Batch/Stream** | Stream Mongo CDC events via SeaTunnel to ClickHouse | **1.20s** | All 9/9 records synced into ClickHouse | ✅ Passed |

---

## 📄 License
This project is developed for Enterprise Real-time Data Platform Research & Graduation Thesis. Released under the MIT License.
