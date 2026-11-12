"""
Kafka consumer của engine: MỘT consumer cho mỗi Kafka cluster, chỉ đọc message và chuyển
cho worker của pipeline tương ứng (app/pipeline_manager.py). Việc kiểm tra schema chạy trong
worker -> pipeline chậm/lỗi không làm chậm pipeline khác dùng chung cluster.
"""
import re
import sys
import json
import hashlib
import threading
from pathlib import Path
from kafka import KafkaConsumer

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import runtime_status


def _topic_pattern(topics: list[str]) -> str:
    """Khớp cả topic cấu hình lẫn topic con Debezium "<topic>.<db>.<table>"."""
    return "^(" + "|".join(re.escape(t) for t in topics) + r")(\..+)?$"


def _topic_matches(topic: str, configured: str) -> bool:
    return topic == configured or topic.startswith(configured + ".")


def _resolve_tables(raw_name: str | None, pair: dict) -> list[str]:
    """
    Chuẩn hoá tên bảng từ event Kafka về ĐÚNG tên trong cấu hình pipeline
    (bỏ schema/db prefix, dấu nháy, so khớp không phân biệt hoa thường), để
    Kafka và polling cùng ghi vào 1 registry key. Bảng không nằm trong
    cấu hình -> bỏ qua (không tạo bản ghi registry lạ). Không xác định được
    bảng -> quét lại tất cả bảng của pipeline.
    """
    configured = pair.get("tables", [])
    if not raw_name:
        return list(configured)
    parts = [p.strip().strip('"`[]').strip() for p in raw_name.split(".")]
    name, qualified = parts[-1].lower(), ".".join(parts[-2:]).lower()
    for t in configured:
        # "sales.orders" trong config phải khớp cả schema; tên trơn chỉ so phần tên bảng.
        if t.lower() == (qualified if "." in t else name):
            return [t]
    return []


def _extract_raw_table(payload: dict, ddl) -> str | None:
    source = payload.get("source") or {}
    if ddl:
        table_changes = payload.get("tableChanges") or []
        if table_changes and table_changes[0].get("id"):
            return table_changes[0]["id"]
        return source.get("table")
    if source.get("schema") and source.get("table"):
        return f"{source['schema']}.{source['table']}"  # Debezium Postgres: giữ schema để phân biệt sales.orders
    return (
        payload.get("table") or payload.get("table_name")
        or source.get("collection") or source.get("table")
    )


def _schema_fingerprint(data: dict, data_dict) -> str | None:
    """
    Dấu vân tay cấu trúc của 1 message dữ liệu. Debezium (schemas.enable=true): hash phần
    schema của "after" -> đổi khi ADD/DROP/RENAME cột và khi đổi kiểu/precision/độ dài
    (kèm column.propagate.source.type). Bản ghi đã unwrap kèm schema phẳng (VD Mongo qua
    ExtractNewDocumentState): hash cả schema -> bắt được field đổi kiểu (số -> chuỗi), không chỉ tập key.
    Message không có schema: hash tập key.
    """
    schema = data.get("schema") if isinstance(data.get("schema"), dict) else None
    after = next((f for f in (schema or {}).get("fields", []) if f.get("field") == "after"), None)
    if after is None and schema is not None:
        after = schema
    basis = after if after is not None else (sorted(data_dict) if isinstance(data_dict, dict) else None)
    if basis is None:
        return None
    return hashlib.sha1(json.dumps(basis, sort_keys=True).encode()).hexdigest()


_unreadable_topics: set[str] = set()


def _warn_unreadable(message) -> None:
    """Báo 1 lần mỗi topic (không spam log mỗi message): engine chỉ đọc được JSON."""
    if message.topic in _unreadable_topics:
        return
    _unreadable_topics.add(message.topic)
    # Byte đầu 0x00 = wire format của Confluent Schema Registry (Avro/Protobuf/JSON Schema).
    kind = "Schema Registry (Avro/Protobuf)" if message.value[:1] == b"\x00" else "not JSON"
    print(f"[Kafka Consumer] {message.topic}: message format {kind} is not supported -> "
          f"set value.converter=org.apache.kafka.connect.json.JsonConverter on the connector. "
          f"Until then this topic's schema changes are caught only by fallback polling.")


def route_message(message, workers: list) -> None:
    """Xác định pipeline + bảng của message rồi báo cho worker (không chạy kiểm tra ở đây)."""
    # Nhiều pipeline có thể dùng chung 1 topic prefix (1 Debezium connector/DB, mỗi pipeline vài bảng):
    # xét MỌI pipeline khớp topic, mỗi pipeline chỉ nhận bảng thuộc cấu hình của nó.
    candidates = [w for w in workers if w.matches(message.topic)]
    if not candidates:
        return
    try:
        data = json.loads(message.value.decode("utf-8"))
    except ValueError:  # gồm UnicodeDecodeError: Avro/Protobuf nhị phân
        _warn_unreadable(message)
        return
    if not isinstance(data, dict):
        _warn_unreadable(message)
        return
    payload = data.get("payload", data)
    if not isinstance(payload, dict):
        return

    ddl = payload.get("ddl")
    data_dict = payload.get("data") or payload.get("after") or (
        payload if "data" not in payload and "tableChanges" not in payload and "ddl" not in payload else None
    )
    if not ddl and not data_dict:
        return

    raw_table = _extract_raw_table(payload, ddl)
    if not raw_table and message.topic.count(".") >= 1:
        # Topic Debezium "<prefix>.<db>.<table>": phần cuối là tên bảng.
        raw_table = message.topic.rsplit(".", 1)[-1]
    # DDL event luôn buộc kiểm tra (fingerprint None); message dữ liệu chỉ khi cấu trúc đổi.
    fingerprint = None if ddl else _schema_fingerprint(data, data_dict)
    for worker in candidates:
        for table in _resolve_tables(raw_table, worker.spec):
            worker.notify(table, fingerprint)


def _consumer_kwargs(bootstrap: str, kafka_cfg: dict) -> dict:
    kwargs = {
        "bootstrap_servers": [s.strip() for s in bootstrap.split(",")],
        "auto_offset_reset": "latest",
        "enable_auto_commit": True,
        "group_id": kafka_cfg.get("group_id", "schema-evolution-group"),
    }
    for key in ("security_protocol", "sasl_mechanism", "sasl_plain_username", "sasl_plain_password"):
        if kafka_cfg.get(key):
            kwargs[key] = kafka_cfg[key]
    return kwargs


def run_cluster_consumer(bootstrap: str, manager, stop: threading.Event) -> None:
    """
    Consumer cho 1 cluster. Đăng ký lại pattern topic mỗi khi danh sách pipeline đổi
    (manager.version), tự thoát khi cluster không còn pipeline event_driven nào.
    Broker chết -> đánh dấu disconnected, thử lại (backoff tối đa 60s); trong lúc đó
    worker vẫn quét định kỳ dự phòng.
    """
    backoff = 5
    while not stop.is_set():
        workers = manager.event_workers(bootstrap)
        if not workers:
            break
        consumer = None
        runtime_status.record_consumer(bootstrap, "connecting")
        try:
            consumer = KafkaConsumer(**_consumer_kwargs(bootstrap, workers[0].kafka_cfg))
            runtime_status.record_consumer(bootstrap, "connected")
            print(f"[Kafka Consumer] Connected to {bootstrap}")
            backoff = 5
            version, pattern = None, None
            while not stop.is_set():
                if manager.version != version:
                    version = manager.version
                    workers = manager.event_workers(bootstrap)
                    if not workers:
                        return
                    new_pattern = _topic_pattern(sorted({w.topic for w in workers}))
                    if new_pattern != pattern:
                        # Debezium publish "<topic.prefix>.<db>.<table>" -> subscribe theo pattern.
                        consumer.subscribe(pattern=new_pattern)
                        pattern = new_pattern
                        print(f"[Kafka Consumer] {bootstrap}: topics {sorted({w.topic for w in workers})}")
                for msgs in consumer.poll(timeout_ms=1000).values():
                    for m in msgs:
                        if m.value is None:
                            continue
                        try:
                            route_message(m, workers)
                        except Exception as e:
                            print(f"[Kafka Consumer] Error processing message on {m.topic}: {e}")
        except Exception as e:
            runtime_status.record_consumer(bootstrap, "disconnected", error=str(e))
            print(f"[Kafka Consumer] {bootstrap} lost/failed: {e}. Retrying in {backoff}s...")
        finally:
            if consumer:
                try:
                    consumer.close()
                except Exception:
                    pass
        if stop.wait(backoff):
            break
        backoff = min(backoff * 2, 60)
    runtime_status.record_consumer(bootstrap, "stopped")


if __name__ == "__main__":
    from app.scheduler import main
    main()
