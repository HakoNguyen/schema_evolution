import sys
import json
import time
import threading
from pathlib import Path
from kafka import KafkaConsumer

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.schema_evolution.core import SchemaRegistry, run_evolution_check
from src.schema_evolution.notification import TelegramNotifier
try:
    from app.scheduler import load_config, build_pairs, ensure_connected
except ModuleNotFoundError:
    from scheduler import load_config, build_pairs, ensure_connected


def run_consumer_for_cluster(cluster_kafka_config: dict, cluster_pairs: list[dict], registry: SchemaRegistry, notifier: TelegramNotifier) -> None:
    topics = [p["name"] for p in cluster_pairs]
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

    print(f"[Kafka Consumer] Connecting to Kafka cluster at {kafka_bootstrap} (Topics: {topics})...")
    consumer = None
    retries = 10
    while retries > 0:
        try:
            consumer = KafkaConsumer(*topics, **consumer_kwargs)
            print(f"[Kafka Consumer] Connected successfully to Kafka cluster at {kafka_bootstrap}!")
            break
        except Exception as e:
            retries -= 1
            print(f"[Kafka Consumer] Connection to {kafka_bootstrap} failed: {e}. Retrying in 5s... ({retries} left)")
            time.sleep(5)

    if not consumer:
        print(f"[Kafka Consumer] Could not connect to Kafka cluster {kafka_bootstrap}. Thread exiting.")
        return

    try:
        for message in consumer:
            if message.value is None:
                continue

            print(f"[Kafka Consumer - {kafka_bootstrap}] Received event on topic: {message.topic}")
            try:
                data = json.loads(message.value.decode('utf-8'))
                payload = data.get("payload", data)

                # Check if it is a DDL change
                ddl = payload.get("ddl")

                # Check if it is a Data Payload message
                data_dict = payload.get("data") or payload.get("after") or (
                    payload if isinstance(payload, dict) and "data" not in payload and "tableChanges" not in payload and "ddl" not in payload else None
                )

                if not ddl and not data_dict:
                    continue

                table_name = None
                if ddl:
                    table_changes = payload.get("tableChanges", [])
                    if table_changes:
                        raw_id = table_changes[0].get("id", "")
                        if raw_id:
                            table_name = raw_id.split(".")[-1].replace('"', '').strip()
                    if not table_name:
                        source = payload.get("source", {})
                        table_name = source.get("table")
                else:
                    table_name = payload.get("table") or payload.get("table_name")

                # Find matching pair within this cluster's pairs
                matching_pair = None
                for p in cluster_pairs:
                    if p["name"] == message.topic:
                        matching_pair = p
                        break

                if not matching_pair:
                    print(f"[Kafka Consumer] No matching pipeline config found for topic {message.topic}")
                    continue

                if not table_name:
                    table_name = matching_pair["tables"][0] if matching_pair.get("tables") else None

                if not table_name:
                    print("[Kafka Consumer] Could not parse table name from Kafka event.")
                    continue

                source_engine = matching_pair["source_engine"]
                target_engine = matching_pair["target_engine"]

                ensure_connected(source_engine)
                if target_engine is not None:
                    ensure_connected(target_engine)

                registry_key = f"{matching_pair['name']}/{table_name}"

                if ddl:
                    print(f"[Kafka Consumer] Detected DDL on table '{table_name}': {ddl}")
                    result = run_evolution_check(
                        source_engine, target_engine, table_name, registry, notifier,
                        registry_key=registry_key,
                    )
                    status = result.get('status', 'unknown')
                    print(f"[Kafka Consumer] DDL Event check result: {status}")
                else:
                    from app.payload_extractor import extract_schema_from_data_dict
                    extracted_schema = extract_schema_from_data_dict(table_name, data_dict)
                    keys = [c.name for c in extracted_schema.columns]
                    ddl = f"CDC Data Payload (Extracted {len(keys)} attributes: {', '.join(keys[:5])}...)"
                    print(f"[Kafka Consumer] Detected Data Payload on '{table_name}'. Running evolution check...")
                    result = run_evolution_check(
                        source_engine, target_engine, table_name, registry, notifier,
                        registry_key=registry_key,
                    )
                    status = result.get('status', 'unknown')
                    print(f"[Kafka Consumer] Payload Event check result: {status}")

                try:
                    from app.event_log import event_logger
                    severity = "breaking" if status in ("frozen", "breaking_detected") else "non_breaking"
                    event_logger.add_event(
                        pipeline_name=matching_pair["name"],
                        table_name=table_name,
                        ddl=ddl,
                        status=status,
                        severity=severity
                    )
                except Exception as ex:
                    print(f"[Kafka Consumer] Could not log event: {ex}")

            except Exception as e:
                print(f"[Kafka Consumer] Error processing message: {e}")

    except KeyboardInterrupt:
        print(f"[Kafka Consumer] Stopping consumer for cluster {kafka_bootstrap}...")
    finally:
        if consumer:
            consumer.close()


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
        pipeline_kafka_cfg = p.get("raw_config", {}).get("kafka") or p.get("kafka") or global_kafka_config
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
