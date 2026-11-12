# Schema Evolution Engine

**English** | [Tiếng Việt](README.vi.md)

> A schema governance layer that sits next to an existing CDC pipeline: it applies safe changes automatically, holds dangerous ones for review, and **loses no rows**.

![Schema Evolution Architecture](docs/images/architecture_banner.png)

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/UI-React%20%2B%20Vite-blue.svg)](https://react.dev/)
[![Debezium](https://img.shields.io/badge/CDC-Debezium-orange.svg)](https://debezium.io/)
[![Redpanda](https://img.shields.io/badge/Kafka-Redpanda-red.svg)](https://redpanda.com/)
[![ClickHouse](https://img.shields.io/badge/Warehouse-ClickHouse-yellow.svg)](https://clickhouse.com/)

## Contents

1. [The problem](#1-the-problem)
2. [Architecture](#2-architecture)
3. [Features](#3-features)
4. [Supported databases](#4-supported-databases)
5. [Setup and running the demo](#5-setup-and-running-the-demo)
6. [Demo scenarios](#6-demo-scenarios)
7. [Declaring a pipeline](#7-declaring-a-pipeline)
8. [Integrating your data plane](#8-integrating-your-data-plane)
9. [Measured results](#9-measured-results)
10. [Tests](#10-tests)
11. [Repository layout](#11-repository-layout)
12. [Known limitations](#12-known-limitations)

---

## 1. The problem

In a CDC pipeline (Postgres → Debezium → Kafka → loader → warehouse), developers can change the source schema at any time. A typical pipeline then does one of two things:

- **Breaks immediately**: the sink meets an unknown column, the warehouse rejects it (`Unrecognized column ...`), and the sink stops. No data reaches the warehouse until someone runs `ALTER TABLE` by hand.
- **Breaks silently**: a renamed column breaks dashboards, or a narrowed type truncates data, and nobody is told.

Schema Evolution Engine watches the source schema, compares it with a stored **baseline**, and decides:

| Change | Example | What the engine does |
|---|---|---|
| **Non-breaking** | Add a column, widen a type (`NUMERIC(18,8)` → `NUMERIC(24,8)`) | Runs `ALTER` on the target within about a second. Data keeps flowing. |
| **Breaking** | Rename, drop, narrow, incompatible type change | **Freezes** that table only, keeps the data waiting in Kafka, sends a Telegram alert, and waits for a human (who can dry-run the change on a copy first). |
| **Source reverts to the baseline** | The developer rolls the change back | Unfreezes automatically. Data flows again. |

Three design principles:

1. **The engine never copies data.** It governs the schema only (control plane). Data keeps flowing through your own pipeline (data plane).
2. **The two sides talk over APIs.** A loader asks the **Gate API** whether a table is open or frozen, and reports its state through the **Reporting API**. For sinks whose code you cannot change (Kafka Connect), the engine pauses and resumes the connector itself.
3. **A freeze loses no data.** While a table is frozen, the loader stops writing and does not commit offsets, so the data waits in Kafka. Once the table opens again, the loader continues exactly where it stopped.

---

## 2. Architecture

```
                    DATA PLANE (your existing pipeline)
 Postgres / MySQL / MongoDB ─► Debezium ─► Kafka (Redpanda) ─┬─► your loader ─────────► ClickHouse / MySQL / Postgres
                                                             └─► Kafka Connect sink ─► (target table)
                                   │                               ▲          ▲
          CDC messages carry the   │ table structure               │ Gate API │ pause / resume
                                   ▼                               │          │
 ┌─────────────────────────── CONTROL PLANE: Schema Evolution Engine ──────────────────────────┐
 │ Kafka consumer ─► per-pipeline worker ─► read source schema ─► diff against baseline        │
 │   • non-breaking → ALTER the target      • breaking → freeze, store draft, Telegram alert    │
 │ FastAPI: Gate API · Reporting API · approve / reject · sandbox · config  ─►  Web UI (React) │
 └─────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Event-driven detection.** The engine reads Debezium messages and re-reads the source schema only when the *structure* of the messages changes (a different fingerprint). A periodic scan runs as a fallback, in case an event is missed.
- **The registry** (`data/registry/`) stores each table's baseline, schema version history, pending drafts and freeze state.
- **Each pipeline has its own worker, registry entries and freeze state**, so a problem in one pipeline never stops another, even when they share a Kafka topic.

---

## 3. Features

**Engine**
- Automatic classification: add column, widen type and `NOT NULL → NULL` are non-breaking; rename (inferred from a dropped/added column pair), drop column, narrow type and incompatible type changes are breaking.
- **Lossless** target types: `NUMERIC` → `Decimal` (never `Float64`, which rounds money), `TIMESTAMP` → `DateTime64(6)`, `DATE` → `Date32`.
- **Sandbox before approval**: Postgres runs the DDL in a transaction and rolls it back; MySQL and ClickHouse clone the table, copy a sample of real rows and run the DDL on the copy.
- **Approve or reject** in the web UI or the CLI (`python -m app.unfreeze_cli list | view | approve | reject <pipeline/table>`). The history records who approved.
- **Safe renames for old messages**: when a `RENAME` is approved, the engine stores an `old → new` mapping before opening the table. Loaders read it from the Gate API and write old messages into the new column.
- **MongoDB sources (no schema)**: the engine infers the schema from the 10,000 newest documents. A field missing from new documents is not treated as dropped, so there are no false freezes.
- **Several pipelines in parallel**, fully isolated from one another.

**Operations**
- **Config as code**: one `config/pipelines/*.yaml` file per pipeline. Edit it in the web UI or in the file; the engine reloads it within about 3 seconds, without a restart. A broken file disables only that pipeline, with a clear error.
- **Secrets kept apart**: YAML holds only `${NAME}` references, and the real values live in `config/secrets.env` (gitignored). Passwords typed in the web form are moved there automatically.
- **Telegram alerts** for breaking changes, approvals, and changes reverted at the source.
- **Optional API authentication**: tokens with an `admin` role (all writes) or a `reporter` role (Reporting API only).
- **Three integration levels**: (1) declare a YAML file, nothing more; (2) also declare the pipeline's components, so the engine measures consumer lag and flags components that stop reporting; (3) let the engine control an existing Kafka Connect sink.

**Web UI** (`http://localhost:5173`)
- **Pipelines Overview**: one pipeline per screen with `‹ ›` buttons, newest first. Shows each table's gate state, the data-plane components (rows/s, lag, sparkline), and the Live CDC Event Stream.
- **Monitored Tables**: table list, version history, pending drafts, sandbox, Approve and Reject. The page refreshes itself every 2 seconds, no F5 needed.
- **Live CDC Stream**: schema events, paginated, with delete-one and clear-all.
- **Pipeline Topology**, **Configuration** (edit `main.yaml` and the pipelines), **Schema Editor**. English and Vietnamese, light and dark themes.

---

## 4. Supported databases

| Role | Supported |
|---|---|
| **Source** | PostgreSQL, MySQL, MongoDB |
| **Target** | ClickHouse, PostgreSQL, MySQL, or `none` (monitor and alert only, no DDL) |

Source and target may be different systems, for example MongoDB → ClickHouse or Postgres → MySQL. The engine uses one shared set of type names (`int`, `bigint`, `numeric`, `text`, `timestamp`, `json`...) and renders each one in the target's own type.

To add another database (SQL Server, Oracle...), write a class that extends `BaseEngine` in [`src/schema_evolution/engines/`](src/schema_evolution/engines/) ([`mysql.py`](src/schema_evolution/engines/mysql.py) is a good template) and register it in `ENGINE_REGISTRY` in [`app/scheduler.py`](app/scheduler.py).

---

## 5. Setup and running the demo

The demo is a live pipeline: Binance trades go into Postgres, Debezium publishes them to Kafka, and a loader writes them to ClickHouse. A MongoDB pipeline and a Kafka Connect sink run alongside it. The start script targets **Windows + PowerShell**.

**Requirements:** Docker Desktop, Python 3.11, Node.js 18 or later.

```powershell
git clone https://github.com/HakoNguyen/schema_evolution.git
cd schema_evolution

python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend; npm install; cd ..

Copy-Item config\secrets.env.example config\secrets.env   # the Docker stack's default passwords are already filled in
powershell -ExecutionPolicy Bypass -File demo\start.ps1 -Reset
```

To receive Telegram alerts, fill in `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `config/secrets.env`. If they are empty, the engine skips alerts.

`start.ps1 -Reset` does the following, in order:
1. Starts Postgres, MongoDB, ClickHouse, Redpanda and Debezium.
2. Rebuilds all demo data at schema v1, with 3 connectors (Postgres, MongoDB, JDBC sink).
3. Opens one window per process: `backend`, `frontend`, `ingestor`, `loader`, `naive-loader`, `tickers-loader`, `orders-app`, `orders-loader`, `check`.

After about **one minute**, open **http://localhost:5173**. Use `localhost`, not `127.0.0.1`.

| Service | Address on the host |
|---|---|
| Web UI (Vite) | http://localhost:5173 |
| Engine API (FastAPI) | http://127.0.0.1:8000 |
| Postgres (source) | `localhost:5431`: `admin` / `password123` |
| MongoDB (replica set `rs0`) | `localhost:27018`, connect with `directConnection=true` |
| ClickHouse | `localhost:8123`: `default` / `clickhouse123` |
| Kafka (Redpanda) | `localhost:19092`, Redpanda Console at http://localhost:8086 |
| Kafka Connect (Debezium) | http://localhost:8083 |

**Running from one Docker image.** The engine, API and web UI are packaged in one image, served on one port:

```powershell
docker compose up -d --build engine     # then open http://localhost:8000
docker compose stop engine
```

The image uses the same `config/` and `data/` as the host. Do **not** run it alongside `uvicorn` on the host: both use port 8000.

---

## 6. Demo scenarios

Each command below plays the developer changing the source schema, then measures how long the engine takes to react. Run them in PowerShell after `.\venv\Scripts\Activate.ps1`.

**Pipeline `market_trades` (Postgres → ClickHouse)**

| `python -m demo.scenario ...` | SQL run on the source | Expected result |
|---|---|---|
| `add_column` | `ALTER TABLE trades ADD COLUMN is_buyer_maker BOOLEAN` | ClickHouse gets the new column automatically. `loader` keeps running; `naive-loader` (the control pipeline, no engine) dies with `Unrecognized column` |
| `widen` | `ALTER TABLE trades ALTER COLUMN price TYPE NUMERIC(24,8)` | `price` in ClickHouse becomes `Decimal(24, 8)` automatically |
| `rename` | `ALTER TABLE trades RENAME COLUMN qty TO quantity` | The table freezes and the loader shows `paused`. Approve it in the UI (Sandbox, then Approve) and the loader continues, including old messages that still carry `qty` |
| `narrow` | `ALTER TABLE trades ALTER COLUMN symbol TYPE VARCHAR(10)` | The table freezes (risk of truncation). Do **not** approve |
| `rollback` | `ALTER TABLE trades ALTER COLUMN symbol TYPE VARCHAR(20)` | The source matches the baseline again, so the engine unfreezes the table |

**Pipeline `market_tickers`**: `tickers_drop` (`DROP COLUMN low_price`) freezes **only** this pipeline while `market_trades` keeps running. `tickers_restore` adds the column back and the table reopens. If the `market_tickers_replica` pipeline (level 3) is enabled, the engine also **pauses** its Kafka Connect sink during the freeze and **resumes** it afterwards.

**Pipeline `shop_orders` (MongoDB → ClickHouse).** MongoDB has no `ALTER`; a "schema change" is the app shipping a release that writes documents of a different shape:

| Command | What the app does | Expected result |
|---|---|---|
| `orders_add_field` | Writes a new `coupon_code` field | ClickHouse gets a `coupon_code` column automatically |
| `orders_drop_field` | Stops writing `note` | **No** false freeze: a missing field does not mean a dropped one |
| `orders_bad_type` | Writes `amount` as the string `"12.50"` | The table freezes and the loader stops |
| `orders_fix` | Rolls the app back and converts string amounts to numbers | The engine unfreezes the table |

The final check is `python -m demo.check`: up to a given point in time, the source and the warehouse must **match row for row**.

Step-by-step details, how to read the output and common problems: see [`demo/README.md`](demo/README.md).

---

## 7. Declaring a pipeline

Either drop a YAML file into `config/pipelines/`, or fill in the form on the **Configuration** page. Example:

```yaml
name: market_trades
detection:
  mode: event_driven                  # or polling (with interval_seconds)
  kafka:
    topic: market                     # Debezium topic prefix: matches market.public.trades
  fallback_polling_interval_seconds: 60
source:
  type: postgres
  config: {host: localhost, port: 5431, dbname: exchange, user: admin, password: "${EXCHANGE_PG_PASSWORD}"}
target:
  type: clickhouse
  config: {host: localhost, port: 8123, database: analytics, user: default, password: "${ANALYTICS_CH_PASSWORD}"}
tables:
  - trades
```

- `kafka.topic` is a **prefix**: `market` matches `market.public.trades`. With the wrong value the engine receives no events and only notices changes at the fallback scan.
- When you create a pipeline in the form, the source port defaults to `5432`; for the demo stack it must be **`5431`**.
- Full reference: [`CONFIGURATION_GUIDE.md`](CONFIGURATION_GUIDE.md) (in Vietnamese). It also covers several Kafka clusters, renamed target tables, which settings need a restart, the `components:` block, and authentication.

---

## 8. Integrating your data plane

The engine does not need to know how your loader works. The loader only needs to:

```http
GET /api/gate/{pipeline}/{table}
→ {"state": "open" | "frozen", "schema_version": 4,
   "pending_changes": [{"change_type": "rename_column", "column": "qty"}],
   "column_renames": {"qty": "quantity"}}
```

- `frozen`: **stop writing** that table and do not commit offsets until the state is `open` again.
- A message with a column the target does not have yet: **wait** (HOLD) until the engine has added it; do not drop the column.
- Engine unreachable: keep the last known state (fail-static).

Optionally, report the loader's state so it appears on the Overview:

```http
POST /api/pipelines/{pipeline}/components/{name}
{"state": "running", "role": "warehouse sink", "metrics": {"rows_per_sec": 512.3, "lag_seconds": 1.6}}
```

A complete example is [`demo/loader.py`](demo/loader.py) (`FreezeGate`, `Reporter`). For a Kafka Connect sink whose code you cannot change, declare it under `components:` in the pipeline YAML and the engine pauses and resumes the connector itself (see section 5 of `CONFIGURATION_GUIDE.md`).

---

## 9. Measured results

Full demo rehearsal on **2026-11-12** (Windows 11, Docker Desktop, live Binance data). Each scenario ran once; times are measured from the moment the change takes effect at the source.

| Scenario | Result | Time |
|---|---|---|
| Add a column (Postgres) | ClickHouse gets the column; the control pipeline dies | 1.08 s |
| Widen `price` | `Decimal(18,8)` becomes `Decimal(24,8)` | 0.95 s |
| Narrow a type (breaking) | Table frozen, loader `paused` | 0.99 s |
| Source reverts | Engine unfreezes the table | 0.58 s |
| Approve a `RENAME` | Sandbox passes, table reopens at v4, loader continues | 7.4 s (until the loader runs again) |
| Add a field (MongoDB) | ClickHouse gets `coupon_code` | 0.78 s |
| Kafka Connect sink (level 3) | Connector PAUSED on freeze, RUNNING on reopen | about 4 s each way |
| Final check (`demo.check`) | **21,098 / 21,098 rows match**; the control pipeline is missing 17,509 rows | |
| Replica table (level 3) | Identical to the source table (same md5 hash) | |

Repeated measurements (p50, p95) produced by `python -m demo.bench` are stored in [`demo/results/`](demo/results/).

---

## 10. Tests

The tests need no infrastructure. Each test file runs directly with Python (the repository does not use pytest):

```powershell
Get-ChildItem tests\test_*.py | ForEach-Object { python $_.FullName }
```

`tests/test_payload_pipeline.py` is an old integration test: it expects a pipeline named `mongo_to_clickhouse` (no longer in the repository) and a MongoDB on port 27017, so it currently fails.

---

## 11. Repository layout

```
api/            FastAPI: Gate API, Reporting API, approve / reject, sandbox, configuration
app/            PipelineManager (config reload), Kafka consumer, per-pipeline workers, components (levels 2-3), CLI
src/schema_evolution/
  core.py       registry, schema diff and classification, check-and-freeze flow
  engines/      Postgres, MySQL, MongoDB, ClickHouse: metadata, DDL generation, sandbox
frontend/       Web UI (React + Vite)
config/         main.yaml, pipelines/*.yaml, secrets.env.example
demo/           demo pipeline: ingestor, loader, orders_app, setup, scenario, check, bench, start.ps1
debezium/       docker-compose for Redpanda + Debezium Connect
tests/          unit and integration tests
Dockerfile      one image for the engine, API and web UI
```

---

## 12. Known limitations

- **A baseline must exist before the schema changes.** If the engine cannot reach the source or target yet (wrong port, wrong password) while the source schema changes, baseline v1 captures the change itself and the engine never reacts to it. Before each scenario, check that the table shows `vN open` with N ≥ 1.
- **MongoDB:** the engine cannot recognise a renamed field (it only sees a new one). Fixing a bad type also requires fixing the documents already written, because the engine samples the 10,000 newest documents.
- **ClickHouse uses the `latest` image.** Version 26.x compresses with ZSTD by default, so DBeaver's 0.8.x JDBC driver reports `Invalid LZ4 magic byte`. Fix: set the driver property `compress=false`.
- The demo start script (`start.ps1`) is Windows-only. The engine and API run anywhere Python runs, or from the Docker image.

---

## License

MIT. See [`LICENSE`](LICENSE).
