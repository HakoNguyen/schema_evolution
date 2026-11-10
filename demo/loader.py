"""
Loader (data plane): topic CDC Debezium -> ClickHouse.

    python -m demo.loader           # pipeline có engine bảo vệ -> analytics.trades
    python -m demo.loader --naive   # pipeline đối chứng, không có engine -> analytics_naive.trades

Đảm bảo không mất dữ liệu (chế độ thường):
- Chỉ commit offset Kafka SAU khi đã ghi ClickHouse thành công (at-least-once;
  bản ghi trùng được ReplacingMergeTree gộp lại, đếm bằng SELECT ... FINAL).
- PAUSE khi engine đóng băng bảng (thay đổi breaking chờ duyệt): không ghi, không
  commit; message nằm an toàn trong Kafka cho đến khi Approve/Reject.
- HOLD nếu message có cột mà bảng đích CHƯA có (nguồn vừa ADD/RENAME COLUMN): không bỏ
  cột đó đi mà chờ engine đồng bộ schema đích.

Chế độ --naive mô phỏng một sink connector thông thường: ghi thẳng, gặp cột lạ thì
lỗi và dừng hẳn (task FAILED) -> dữ liệu ngừng chảy vào warehouse.
"""
import argparse
import base64
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import clickhouse_connect
from kafka import KafkaConsumer

import demo  # noqa: F401  (UTF-8 console)
from demo import config as c

DECIMAL = "org.apache.kafka.connect.data.Decimal"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def decode_decimal(b64: str, scale: int) -> Decimal:
    raw = base64.b64decode(b64)
    return Decimal(int.from_bytes(raw, "big", signed=True)).scaleb(-scale)


def _decoder(field: dict):
    name = field.get("name")
    if name == DECIMAL:
        scale = int(field["parameters"]["scale"])
        return lambda v: decode_decimal(v, scale)
    if name == "io.debezium.time.ZonedTimestamp":
        return datetime.fromisoformat
    if name in ("io.debezium.time.Timestamp", "org.apache.kafka.connect.data.Timestamp"):
        return lambda v: EPOCH + timedelta(milliseconds=v)
    if name == "io.debezium.time.MicroTimestamp":
        return lambda v: EPOCH + timedelta(microseconds=v)
    if name == "io.debezium.time.Date":
        return lambda v: date(1970, 1, 1) + timedelta(days=v)
    return None


_decoder_cache: dict[str, dict] = {}


def parse_message(raw: bytes | None) -> dict | None:
    """Debezium JSON (schemas.enable=true) -> dict cột->giá trị. None nếu là delete/tombstone."""
    if raw is None:
        return None
    msg = json.loads(raw)
    payload, schema = msg.get("payload", msg), msg.get("schema")
    if payload.get("op") not in ("c", "r", "u") or payload.get("after") is None:
        return None  # trade là insert-only; delete không được nhân bản sang warehouse
    after = payload["after"]
    decoders = {}
    if schema:
        after_schema = next(f for f in schema["fields"] if f["field"] == "after")
        key = json.dumps(after_schema, sort_keys=True)
        if key not in _decoder_cache:
            _decoder_cache[key] = {f["field"]: d for f in after_schema["fields"] if (d := _decoder(f))}
        decoders = _decoder_cache[key]
    return {k: (decoders[k](v) if v is not None and k in decoders else v) for k, v in after.items()}


class ClickHouseTable:
    def __init__(self, client, table: str):
        self.client, self.table = client, table
        self.columns: set[str] = set()
        self.refresh()

    def refresh(self):
        res = self.client.query(
            "SELECT name FROM system.columns WHERE database = currentDatabase() AND table = %(t)s",
            parameters={"t": self.table},
        )
        self.columns = {r[0] for r in res.result_rows}

    def write(self, rows: list[dict]) -> None:
        # Gom theo tập cột: các message trước/sau một ALTER có cấu trúc khác nhau.
        groups: dict[tuple, list[dict]] = {}
        for r in rows:
            groups.setdefault(tuple(r), []).append(r)
        for cols, grp in groups.items():
            self._wait_for_columns(set(cols))
            self.client.insert(self.table, [[r[k] for k in cols] for r in grp], column_names=list(cols))

    def _wait_for_columns(self, needed: set[str]) -> None:
        missing = needed - self.columns
        if not missing:
            return
        self.refresh()
        started = next_log = time.monotonic()
        while missing := needed - self.columns:
            if time.monotonic() >= next_log:
                print(f"[loader] HOLD: bảng đích chưa có cột {sorted(missing)} "
                      f"-> chờ engine đồng bộ schema ({time.monotonic() - started:.0f}s)")
                next_log += 5
            time.sleep(1)
            self.refresh()
        print(f"[loader] RESUME: đích đã có {sorted(needed & self.columns)} sau {time.monotonic() - started:.1f}s")

    def write_naive(self, rows: list[dict]) -> None:
        """Sink "thông thường": ghi thẳng mọi cột, không chờ, không hỏi ai."""
        groups: dict[tuple, list[dict]] = {}
        for r in rows:
            groups.setdefault(tuple(r), []).append(r)
        for cols, grp in groups.items():
            self.client.insert(self.table, [[r[k] for k in cols] for r in grp], column_names=list(cols))


class FreezeGate:
    """Đọc trạng thái freeze của bảng trong Schema Registry do engine ghi."""

    def __init__(self):
        from src.schema_evolution.core import SchemaRegistry
        self.registry = SchemaRegistry(c.REGISTRY_DIR)
        self.frozen = False

    def check(self) -> bool:
        try:
            self.frozen = self.registry.is_frozen(c.REGISTRY_KEY)
        except (ValueError, OSError):
            pass  # engine đang ghi dở file registry -> giữ trạng thái cũ, đọc lại lượt sau
        return self.frozen

    def wait_until_open(self) -> None:
        if not self.check():
            return
        started = next_log = time.monotonic()
        while self.check():
            if time.monotonic() >= next_log:
                print(f"[loader] PAUSE: bảng {c.REGISTRY_KEY} đang bị freeze (thay đổi breaking chờ duyệt) "
                      f"-> dừng ghi, dữ liệu giữ trong Kafka ({time.monotonic() - started:.0f}s)")
                next_log += 5
            time.sleep(1)
        print(f"[loader] RESUME: bảng đã được mở lại sau {time.monotonic() - started:.1f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--naive", action="store_true", help="pipeline đối chứng: không có engine bảo vệ")
    naive = ap.parse_args().naive
    database = c.CH_NAIVE_DATABASE if naive else c.CH_DATABASE
    name = "naive-loader" if naive else "loader"

    client = clickhouse_connect.get_client(**c.CH, database=database)
    table = ClickHouseTable(client, c.SOURCE_TABLE)
    gate = None if naive else FreezeGate()
    consumer = KafkaConsumer(
        c.TOPIC,
        bootstrap_servers=c.KAFKA_BOOTSTRAP,
        group_id=c.LOADER_NAIVE_GROUP if naive else c.LOADER_GROUP,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        max_poll_records=5000,
        max_poll_interval_ms=3_600_000,  # PAUSE/HOLD trong lúc chờ duyệt có thể kéo dài nhiều phút
        metadata_max_age_ms=5000,  # topic CDC chỉ được tạo khi có message đầu tiên; mặc định 5 phút mới thấy
    )
    print(f"[{name}] {c.TOPIC} -> clickhouse {database}.{c.SOURCE_TABLE}")

    loaded, last_report, last_lag = 0, time.monotonic(), None
    while True:
        polled = consumer.poll(timeout_ms=500)
        rows = [r for msgs in polled.values() for m in msgs if (r := parse_message(m.value)) is not None]
        if rows:
            if naive:
                try:
                    table.write_naive(rows)
                except Exception as e:
                    print(f"[{name}] FAILED: {type(e).__name__}: {str(e).strip().splitlines()[0][:300]}")
                    print(f"[{name}] task dừng hẳn — warehouse {database} không nhận thêm dữ liệu nào nữa.")
                    sys.exit(1)
            else:
                gate.wait_until_open()
                table.write(rows)
            loaded += len(rows)
            tt = max((r["trade_time"] for r in rows if isinstance(r.get("trade_time"), datetime)), default=None)
            if tt:
                last_lag = (datetime.now(timezone.utc) - tt).total_seconds()
        if polled:
            consumer.commit()
        now = time.monotonic()
        if now - last_report >= 5:
            lag = f"{last_lag:.2f}s" if last_lag is not None else "-"
            print(f"[{name}] {loaded / (now - last_report):6.1f} row/s | e2e lag {lag}")
            loaded, last_report = 0, now


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[loader] stopped")
