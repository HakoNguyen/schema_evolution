"""
Dựng (hoặc dựng lại) toàn bộ luồng demo: market_trades + market_tickers.

    python -m demo.setup           # tạo nếu chưa có (chạy lại nhiều lần không sao)
    python -m demo.setup --reset   # xóa sạch dữ liệu demo rồi tạo lại schema v1

--reset xóa: connector + replication slot, DB exchange, DB analytics, topic CDC,
consumer group của loader và registry của pipeline. Nên tắt ingestor/loader/backend trước.

Mức 3: thêm sink Kafka Connect có sẵn (Debezium JDBC sink) chép tickers sang DB exchange_replica.
Pipeline market_tickers_replica giữ schema bảng replica và pause/resume sink theo freeze.
"""
import argparse
import json
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

import clickhouse_connect
import psycopg2
import requests
from kafka.admin import KafkaAdminClient
from kafka.errors import UnknownTopicOrPartitionError

from demo import config as c

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


@contextmanager
def _pg_admin():
    # Không dùng "with conn": psycopg2 2.9 mở transaction kể cả khi autocommit -> CREATE DATABASE lỗi.
    conn = psycopg2.connect(**{**c.PG, "dbname": c.PG_ADMIN_DB})
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def _sql_statements(path: Path, **params) -> list[str]:
    text = "\n".join(l for l in path.read_text(encoding="utf-8").splitlines() if not l.strip().startswith("--"))
    if params:
        text = text.format(**params)
    return [s.strip() for s in text.split(";") if s.strip()]


def reset() -> None:
    print("[reset] connectors")
    for name in (c.SINK_CONNECTOR_NAME, c.CONNECTOR_NAME):
        requests.delete(f"{c.CONNECT_URL}/connectors/{name}", timeout=10)

    print("[reset] postgres: replication slot + DB exchange")
    with _pg_admin() as cur:
        # Slot giữ WAL vô hạn nếu bị bỏ lại; connector vừa xóa có thể cần vài giây để nhả slot.
        for _ in range(10):
            cur.execute("SELECT active FROM pg_replication_slots WHERE slot_name = 'market_slot'")
            row = cur.fetchone()
            if row is None:
                break
            if not row[0]:
                cur.execute("SELECT pg_drop_replication_slot('market_slot')")
                break
            time.sleep(1)
        cur.execute("DROP DATABASE IF EXISTS exchange WITH (FORCE)")
        cur.execute(f"DROP DATABASE IF EXISTS {c.REPLICA_DB} WITH (FORCE)")

    print(f"[reset] clickhouse: DB {c.CH_DATABASE}, {c.CH_NAIVE_DATABASE}")
    ch = clickhouse_connect.get_client(**c.CH)
    for db in (c.CH_DATABASE, c.CH_NAIVE_DATABASE):
        ch.command(f"DROP DATABASE IF EXISTS {db}")

    print("[reset] kafka: topic + consumer group")
    admin = KafkaAdminClient(bootstrap_servers=c.KAFKA_BOOTSTRAP)
    try:
        admin.delete_topics([c.TOPIC, f"market.public.{c.TICKERS_TABLE}"])
    except UnknownTopicOrPartitionError:
        pass
    # kafka-python 3.x: delete_groups (2.x là delete_consumer_groups). Nhóm chưa tồn tại -> bỏ qua.
    existing = {g["group_id"] for g in admin.list_groups()}
    groups = [g for g in (c.LOADER_GROUP, c.LOADER_NAIVE_GROUP, f"{c.LOADER_GROUP}-{c.TICKERS_TABLE}", c.SINK_GROUP)
              if g in existing]
    if groups:
        admin.delete_groups(groups)
    admin.close()

    print("[reset] registry")
    for pipeline in (c.PIPELINE_NAME, c.TICKERS_PIPELINE, c.REPLICA_PIPELINE):
        shutil.rmtree(ROOT / "data" / "registry" / pipeline, ignore_errors=True)


def setup() -> None:
    print("[setup] postgres: DB exchange + bảng trades, tickers")
    with _pg_admin() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'exchange'")
        if cur.fetchone() is None:
            cur.execute("CREATE DATABASE exchange")
    with psycopg2.connect(**c.PG) as conn, conn.cursor() as cur:
        for stmt in _sql_statements(HERE / "sql" / "source.sql"):
            cur.execute(stmt)

    print(f"[setup] clickhouse: {c.CH_DATABASE} + {c.CH_NAIVE_DATABASE} (đối chứng)")
    ch = clickhouse_connect.get_client(**c.CH)
    for db in (c.CH_DATABASE, c.CH_NAIVE_DATABASE):
        for stmt in _sql_statements(HERE / "sql" / "warehouse.sql", db=db):
            ch.command(stmt)

    print("[setup] debezium connector")
    _register(c.CONNECTOR_NAME, "connector.json")

    print(f"[setup] mức 3: DB {c.REPLICA_DB} + sink Kafka Connect {c.SINK_CONNECTOR_NAME}")
    with _pg_admin() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (c.REPLICA_DB,))
        if cur.fetchone() is None:
            cur.execute(f"CREATE DATABASE {c.REPLICA_DB}")
    with psycopg2.connect(**{**c.PG, "dbname": c.REPLICA_DB}) as conn, conn.cursor() as cur:
        cur.execute(_replica_ddl(c.TICKERS_TABLE))
    _register(c.SINK_CONNECTOR_NAME, "sink_connector.json")
    print("[setup] xong")


def _replica_ddl(table: str) -> str:
    """CREATE TABLE replica theo cấu trúc HIỆN TẠI của bảng nguồn (không phải v1 trong source.sql):
    nguồn đã qua vài kịch bản thì replica vẫn khớp baseline engine đọc từ nguồn."""
    with psycopg2.connect(**c.PG) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull, array_position(i.indkey::int2[], a.attnum)
            FROM pg_attribute a LEFT JOIN pg_index i ON i.indrelid = a.attrelid AND i.indisprimary
            WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum""",
                    (f"public.{table}",))
        cols = cur.fetchall()
    defs = [f'"{n}" {t}{" NOT NULL" if notnull else ""}' for n, t, notnull, _ in cols]
    # indkey là int2vector đánh số từ 0: vị trí 0 hợp lệ, chỉ None mới là "không thuộc khoá chính".
    pk = ", ".join(f'"{n}"' for n, _, _, pos in sorted((col for col in cols if col[3] is not None), key=lambda col: col[3]))
    return f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(defs)}, PRIMARY KEY ({pk}))"


def _register(name: str, config_file: str) -> None:
    cfg = json.loads((HERE / config_file).read_text(encoding="utf-8"))
    r = requests.put(f"{c.CONNECT_URL}/connectors/{name}/config", json=cfg, timeout=30)
    r.raise_for_status()
    for _ in range(30):
        st = requests.get(f"{c.CONNECT_URL}/connectors/{name}/status", timeout=10)
        if st.ok:
            tasks = st.json().get("tasks", [])
            if tasks and tasks[0]["state"] == "RUNNING":
                print(f"  {name} RUNNING")
                return
            if tasks and tasks[0]["state"] == "FAILED":
                raise SystemExit(f"{name} FAILED: {tasks[0].get('trace', '')[:500]}")
        time.sleep(1)
    raise SystemExit(f"{name} chưa RUNNING sau 30s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="xóa sạch dữ liệu demo trước khi dựng lại")
    args = ap.parse_args()
    if args.reset:
        reset()
    setup()
