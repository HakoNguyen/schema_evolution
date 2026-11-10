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
from collections import deque
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import clickhouse_connect
import requests
from clickhouse_connect.driver.exceptions import ProgrammingError
from kafka import KafkaConsumer

import demo  # noqa: F401  (UTF-8 console)
from demo import config as c

RATE_WINDOW_SECONDS = 5


class Reporter:
    """Báo trạng thái lên engine qua Reporting API (POST /api/pipelines/{p}/components/{name})."""

    def __init__(self, name: str, role: str, database: str):
        self.url = f"{c.ENGINE_API}/api/pipelines/{c.PIPELINE_NAME}/components/{name}"
        self.role = role
        self.state, self.message = "starting", ""
        self.metrics = {"target_table": f"{database}.{c.SOURCE_TABLE}"}
        self.sent_at = 0.0
        self.session = requests.Session()

    def update(self, state: str, message: str = "", **metrics) -> None:
        changed = (state, message) != (self.state, self.message)
        self.state, self.message = state, message
        self.metrics.update(metrics)
        if not changed and time.monotonic() - self.sent_at < 1:
            return
        try:
            self.session.post(self.url, timeout=2, json={
                "state": state, "role": self.role, "metrics": self.metrics, "message": message})
        except requests.RequestException:
            pass  # engine tạm không liên lạc được: dữ liệu vẫn chảy, lần sau gửi lại
        self.sent_at = time.monotonic()

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


def apply_renames(row: dict, renames: dict[str, str], target_columns: set[str]) -> dict:
    """Message cũ còn mang tên cột đã được đổi (RENAME đã duyệt) -> ghi vào cột tên mới."""
    if not renames:
        return row
    return {(renames[k] if k in renames and k not in target_columns else k): v for k, v in row.items()}


class ClickHouseTable:
    def __init__(self, client, table: str, status: Reporter | None = None, gate=None):
        self.client, self.table, self.status, self.gate = client, table, status, gate
        self.columns: set[str] = set()
        self.refresh()

    def refresh(self):
        res = self.client.query(
            "SELECT name FROM system.columns WHERE database = currentDatabase() AND table = %(t)s",
            parameters={"t": self.table},
        )
        self.columns = {r[0] for r in res.result_rows}

    def write(self, rows: list[dict]) -> None:
        while True:
            renames = self.gate.renames if self.gate else {}
            # Gom theo tập cột (sau khi ánh xạ tên cột đã đổi): message trước/sau một ALTER khác cấu trúc.
            groups: dict[tuple, list[dict]] = {}
            for r in rows:
                r = apply_renames(r, renames, self.columns)
                groups.setdefault(tuple(r), []).append(r)
            try:
                for cols, grp in groups.items():
                    self._wait_for_columns(set(cols))
                    self.client.insert(self.table, [[r[k] for k in cols] for r in grp], column_names=list(cols))
                return
            except ProgrammingError as e:
                if "Unrecognized column" not in str(e):
                    raise
                # Schema đích vừa đổi sau lần đọc trước (VD vừa duyệt RENAME): đọc lại rồi ghi lại cả lô.
                # Nhóm đã ghi sẽ bị ghi trùng -> ReplacingMergeTree gộp lại (at-least-once).
                print(f"[loader] target schema changed ({e}) -> refreshing and retrying the batch")
                self.refresh()
                if self.gate:
                    self.gate.check()

    def _wait_for_columns(self, needed: set[str]) -> None:
        missing = needed - self.columns
        if not missing:
            return
        self.refresh()
        started = next_log = time.monotonic()
        while missing := needed - self.columns:
            if self.status:
                # Đích thiếu cột VÌ bảng đang chờ duyệt (VD rename) -> báo "paused" để UI hiện nút duyệt.
                frozen = self.gate is not None and self.gate.check()
                self.status.update("paused" if frozen else "hold", rows_per_sec=0.0,
                                   message=f"target is missing columns {sorted(missing)} — waiting for the engine to add them")
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
    """Hỏi engine qua Gate API (GET /api/gate/{pipeline}/{table}) bảng có đang bị freeze không."""

    def __init__(self, status: Reporter):
        self.url = f"{c.ENGINE_API}/api/gate/{c.PIPELINE_NAME}/{c.SOURCE_TABLE}"
        self.session = requests.Session()
        self.frozen = False
        self.renames: dict[str, str] = {}  # RENAME đã duyệt: tên cũ -> tên mới
        self.unreachable = False
        self.status = status

    def check(self) -> bool:
        try:
            resp = self.session.get(self.url, timeout=2)
            resp.raise_for_status()
            gate = resp.json()
            self.frozen = gate["state"] == "frozen"
            self.renames = gate.get("column_renames") or {}
            if self.unreachable:
                print("[loader] Gate API reachable again")
            self.unreachable = False
        except (requests.RequestException, ValueError, KeyError) as e:
            # Fail-static: giữ trạng thái đã biết gần nhất. HOLD (cột lạ) vẫn bảo vệ dữ liệu khi engine vắng mặt.
            if not self.unreachable:
                print(f"[loader] Gate API unreachable ({e}) -> keeping last known state: "
                      f"{'frozen' if self.frozen else 'open'}")
            self.unreachable = True
        return self.frozen

    def wait_until_open(self) -> None:
        if not self.check():
            return
        started = next_log = time.monotonic()
        while self.check():
            self.status.update("paused", message="table frozen: breaking change awaiting approval — data kept in Kafka",
                               rows_per_sec=0.0)
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

    status = Reporter(name, "baseline sink (no engine)" if naive else "warehouse sink", database)
    client = clickhouse_connect.get_client(**c.CH, database=database)
    gate = None if naive else FreezeGate(status)
    table = ClickHouseTable(client, c.SOURCE_TABLE, status, gate)
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
    window: deque[tuple[float, int]] = deque()  # (thời điểm ghi xong, số dòng) trong RATE_WINDOW_SECONDS
    while True:
        polled = consumer.poll(timeout_ms=500)
        rows = [r for msgs in polled.values() for m in msgs if (r := parse_message(m.value)) is not None]
        if rows:
            if naive:
                try:
                    table.write_naive(rows)
                except Exception as e:
                    error = f"{type(e).__name__}: {str(e).strip().splitlines()[0][:300]}"
                    status.update("failed", message=error, rows_per_sec=0.0)
                    print(f"[{name}] FAILED: {error}")
                    print(f"[{name}] task dừng hẳn — warehouse {database} không nhận thêm dữ liệu nào nữa.")
                    sys.exit(1)
            else:
                gate.wait_until_open()
                table.write(rows)
            loaded += len(rows)
            window.append((time.monotonic(), len(rows)))
            tt = max((r["trade_time"] for r in rows if isinstance(r.get("trade_time"), datetime)), default=None)
            if tt:
                last_lag = (datetime.now(timezone.utc) - tt).total_seconds()
        if polled:
            consumer.commit()
        now = time.monotonic()
        while window and now - window[0][0] > RATE_WINDOW_SECONDS:
            window.popleft()
        status.update("running", rows_per_sec=round(sum(n for _, n in window) / RATE_WINDOW_SECONDS, 1),
                      lag_seconds=round(last_lag, 2) if last_lag is not None else None)
        if now - last_report >= 5:
            lag = f"{last_lag:.2f}s" if last_lag is not None else "-"
            print(f"[{name}] {loaded / (now - last_report):6.1f} row/s | e2e lag {lag}")
            loaded, last_report = 0, now


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[loader] stopped")
