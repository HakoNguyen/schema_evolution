import re
import sys
import json
import hashlib
import time
import threading
from pathlib import Path
from kafka import KafkaConsumer

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.schema_evolution.core import SchemaRegistry, run_evolution_check, make_registry_key
from app import runtime_status
from src.schema_evolution.notification import TelegramNotifier
try:
    from app.scheduler import load_config, build_pairs, ensure_connected, log_detected_change
except ModuleNotFoundError:
    from scheduler import load_config, build_pairs, ensure_connected, log_detected_change


def _topic_pattern(topics: list[str]) -> str:
    """Khớp cả topic cấu hình lẫn topic con Debezium "<topic>.<db>.<table>"."""
    return "^(" + "|".join(re.escape(t) for t in topics) + r")(\..+)?$"


def _topic_matches(topic: str, configured: str) -> bool:
    return topic == configured or topic.startswith(configured + ".")


def _pair_topic(p: dict) -> str:
    detection = p.get("detection") or {}
    return detection.get("kafka", {}).get("topic", p["name"])


def _resolve_tables(raw_name: str | None, pair: dict) -> list[str]:
    """
    Chuẩn hoá tên bảng từ event Kafka về ĐÚNG tên trong cấu hình pipeline
    (bỏ schema/db prefix, dấu nháy, so khớp không phân biệt hoa thường), để
    Kafka và scheduler cùng ghi vào 1 registry key. Bảng không nằm trong
    cấu hình -> bỏ qua (không tạo bản ghi registry lạ). Không xác định được
    bảng -> quét lại tất cả bảng của pipeline.
    """
    configured = pair.get("tables", [])
    if not raw_name:
        return list(configured)
    name = raw_name.split(".")[-1].strip().strip('"`[]').strip()
    for t in configured:
        if t.lower() == name.lower():
            return [t]
    return []


def _extract_raw_table(payload: dict, ddl) -> str | None:
    source = payload.get("source") or {}
    if ddl:
        table_changes = payload.get("tableChanges") or []
        if table_changes and table_changes[0].get("id"):
            return table_changes[0]["id"]
        return source.get("table")
    return (
        payload.get("table") or payload.get("table_name")
        or source.get("collection") or source.get("table")
    )


# registry_key -> fingerprint cấu trúc message gần nhất đã được kiểm tra.
_seen_fingerprints: dict[str, str] = {}


def _schema_fingerprint(data: dict, data_dict) -> str | None:
    """
    Dấu vân tay cấu trúc của 1 message dữ liệu. Debezium (schemas.enable=true): hash phần
    schema của "after" -> đổi khi ADD/DROP/RENAME cột và khi đổi kiểu/precision/độ dài
    (kèm column.propagate.source.type). Message không có schema (VD Mongo payload): hash tập key.
    """
    schema = data.get("schema") if isinstance(data.get("schema"), dict) else None
    after = next((f for f in (schema or {}).get("fields", []) if f.get("field") == "after"), None)
    basis = after if after is not None else (sorted(data_dict) if isinstance(data_dict, dict) else None)
    if basis is None:
        return None
    return hashlib.sha1(json.dumps(basis, sort_keys=True).encode()).hexdigest()


def _handle_message(message, event_driven_pairs: list[dict], registry: SchemaRegistry, notifier) -> None:
    data = json.loads(message.value.decode('utf-8'))
    payload = data.get("payload", data)
    if not isinstance(payload, dict):
        return

    ddl = payload.get("ddl")
    data_dict = payload.get("data") or payload.get("after") or (
        payload if "data" not in payload and "tableChanges" not in payload and "ddl" not in payload else None
    )
    if not ddl and not data_dict:
        return

    matching_pair = next(
        (p for p in event_driven_pairs
         if _topic_matches(message.topic, _pair_topic(p)) or _topic_matches(message.topic, p["name"])),
        None,
    )
    if not matching_pair:
        print(f"[Kafka Consumer] No matching pipeline config found for topic {message.topic}")
        return

    raw_table = _extract_raw_table(payload, ddl)
    if not raw_table and message.topic.count(".") >= 1:
        # Topic Debezium "<prefix>.<db>.<table>": phần cuối là tên bảng.
        raw_table = message.topic.rsplit(".", 1)[-1]
    tables = _resolve_tables(raw_table, matching_pair)
    if not tables:
        print(f"[Kafka Consumer] Bảng '{raw_table}' không thuộc pipeline '{matching_pair['name']}', bỏ qua.")
        return

    # Message dữ liệu mang cấu trúc y hệt lần trước -> schema nguồn không đổi, khỏi crawl.
    # (Trước đây mọi message đều crawl metadata nguồn: vài chục trade/s = vài chục query catalog/s.)
    fingerprint = None if ddl else _schema_fingerprint(data, data_dict)
    keys = [make_registry_key(matching_pair["name"], t) for t in tables]
    if fingerprint is not None and all(_seen_fingerprints.get(k) == fingerprint for k in keys):
        return

    source_engine = matching_pair["source_engine"]
    target_engine = matching_pair["target_engine"]
    ensure_connected(source_engine)
    if target_engine is not None:
        ensure_connected(target_engine)

    for table_name, registry_key in zip(tables, keys):
        print(f"[Kafka Consumer] {'DDL' if ddl else 'Schema fingerprint changed'} on '{registry_key}'. Running evolution check...")
        result = run_evolution_check(
            source_engine, target_engine, table_name, registry, notifier,
            registry_key=registry_key,
        )
        # Chỉ ghi nhớ sau khi kiểm tra thành công: lỗi giữa chừng -> message sau kiểm tra lại.
        if fingerprint is not None:
            _seen_fingerprints[registry_key] = fingerprint
        print(f"[Kafka Consumer] {registry_key}: {result.get('status', 'unknown')}")
        log_detected_change(matching_pair["name"], table_name, result, source="kafka")


def run_consumer_for_cluster(cluster_kafka_config: dict, cluster_pairs: list[dict], registry: SchemaRegistry, notifier: TelegramNotifier) -> None:
    event_driven_pairs = [p for p in cluster_pairs if (p.get("detection") or {}).get("mode") == "event_driven"]
    if not event_driven_pairs:
        print(f"[Kafka Consumer] Không có pipeline nào bật chế độ event-driven trong cluster {cluster_kafka_config.get('bootstrap_servers', 'localhost:19092')}. Bỏ qua.")
        return

    topics = [_pair_topic(p) for p in event_driven_pairs]
    kafka_bootstrap = cluster_kafka_config.get("bootstrap_servers", "localhost:19092")
    group_id = cluster_kafka_config.get("group_id", "schema-evolution-group")

    consumer_kwargs = {
        "bootstrap_servers": [s.strip() for s in kafka_bootstrap.split(",")],
        "auto_offset_reset": "latest",
        "enable_auto_commit": True,
        "group_id": group_id,
    }
    for key in ("security_protocol", "sasl_mechanism", "sasl_plain_username", "sasl_plain_password"):
        if key in cluster_kafka_config and cluster_kafka_config[key]:
            consumer_kwargs[key] = cluster_kafka_config[key]

    # Vòng ngoài không bao giờ thoát: broker chết -> đánh dấu disconnected,
    # chờ rồi kết nối lại (backoff tối đa 60s). Trong lúc đó polling dự
    # phòng của scheduler vẫn quét các bảng event-driven.
    backoff = 5
    while True:
        consumer = None
        runtime_status.record_consumer(kafka_bootstrap, "connecting")
        try:
            print(f"[Kafka Consumer] Connecting to Kafka cluster at {kafka_bootstrap} (Topics: {topics})...")
            # Debezium publish theo "<topic.prefix>.<db>.<table>" (VD
            # mongo_to_clickhouse.sample_db.users) chứ không phải đúng tên
            # topic cấu hình -> subscribe theo pattern để nhận cả 2 dạng.
            consumer = KafkaConsumer(**consumer_kwargs)
            consumer.subscribe(pattern=_topic_pattern(topics))
            runtime_status.record_consumer(kafka_bootstrap, "connected")
            print(f"[Kafka Consumer] Connected successfully to Kafka cluster at {kafka_bootstrap}!")
            backoff = 5

            for message in consumer:
                if message.value is None:
                    continue
                try:
                    _handle_message(message, event_driven_pairs, registry, notifier)
                except Exception as e:
                    print(f"[Kafka Consumer] Error processing message: {e}")
        except KeyboardInterrupt:
            print(f"[Kafka Consumer] Stopping consumer for cluster {kafka_bootstrap}...")
            return
        except Exception as e:
            runtime_status.record_consumer(kafka_bootstrap, "disconnected", error=str(e))
            print(f"[Kafka Consumer] Connection to {kafka_bootstrap} lost/failed: {e}. Retrying in {backoff}s...")
        finally:
            if consumer:
                try:
                    consumer.close()
                except Exception:
                    pass
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)


def start_consumer(config_path: str = "config/main.yaml") -> None:
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"[Kafka Consumer] Failed to load config: {e}")
        return

    registry = SchemaRegistry(config["registry"]["dir"])
    notifier = TelegramNotifier(
        bot_token=config["telegram"]["bot_token"],
        chat_id=config["telegram"]["chat_id"],
    )

    try:
        pairs = build_pairs(config["pairs"])
    except Exception as e:
        print(f"[Kafka Consumer] Failed to build pairs: {e}")
        return

    global_kafka_config = config.get("kafka", {})

    # Group database pairs by their target Kafka cluster
    clusters: dict[str, tuple[dict, list[dict]]] = {}
    for p in pairs:
        # Check if pipeline YAML overrides Kafka config, otherwise fallback to global main.yaml kafka config
        pipeline_kafka_cfg = {**global_kafka_config, **((p.get("detection") or {}).get("kafka") or {})}
        bootstrap = pipeline_kafka_cfg.get("bootstrap_servers", "localhost:19092")
        
        if bootstrap not in clusters:
            clusters[bootstrap] = (pipeline_kafka_cfg, [])
        clusters[bootstrap][1].append(p)

    print(f"[Kafka Consumer] Detected {len(clusters)} distinct Kafka Cluster(s) across pipelines.")

    threads = []
    for bootstrap, (k_cfg, c_pairs) in clusters.items():
        t = threading.Thread(
            target=run_consumer_for_cluster,
            args=(k_cfg, c_pairs, registry, notifier),
            name=f"KafkaConsumerThread-{bootstrap}",
            daemon=True
        )
        t.start()
        threads.append(t)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[Kafka Consumer] Stopping all Kafka cluster consumer threads...")


if __name__ == "__main__":
    start_consumer()
