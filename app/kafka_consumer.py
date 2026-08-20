import sys
import json
import time
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
    
    # Load and build database pairs
    try:
        pairs = build_pairs(config["pairs"])
    except Exception as e:
        print(f"[Kafka Consumer] Failed to build pairs: {e}")
        return

    # Debezium MySQL connector uses the pair name as the topic prefix
    # So we subscribe to topics corresponding to our monitored pair names
    topics = [p["name"] for p in pairs]
    print(f"[Kafka Consumer] Monitored Kafka topics: {topics}")

    # Connect to Kafka
    kafka_bootstrap = "localhost:19092"  # Connecting from host environment
    
    print(f"[Kafka Consumer] Connecting to Redpanda at {kafka_bootstrap}...")
    consumer = None
    retries = 10
    while retries > 0:
        try:
            consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=[kafka_bootstrap],
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='schema-evolution-group'
            )
            print("[Kafka Consumer] Connected to Redpanda successfully!")
            break
        except Exception as e:
            retries -= 1
            print(f"[Kafka Consumer] Connection failed: {e}. Retrying in 5s... ({retries} retries left)")
            time.sleep(5)
            
    if not consumer:
        print("[Kafka Consumer] Could not connect to Kafka. Exiting.")
        return

    try:
        for message in consumer:
            if message.value is None:
                continue
            
            print(f"[Kafka Consumer] Received event on topic: {message.topic}")
            try:
                data = json.loads(message.value.decode('utf-8'))
                payload = data.get("payload", data)
                
                # Check if it is a DDL change
                ddl = payload.get("ddl")
                
                # Check if it is a Data Payload message containing 'data' or 'after' or raw dict
                data_dict = payload.get("data") or payload.get("after") or (payload if isinstance(payload, dict) and "data" not in payload and "tableChanges" not in payload and "ddl" not in payload else None)
                
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
                    
                # Find matching pair
                matching_pair = None
                for p in pairs:
                    if p["name"] == message.topic:
                        matching_pair = p
                        break
                        
                if not matching_pair:
                    print(f"[Kafka Consumer] No matching pipeline config found for topic {message.topic}")
                    continue
                    
                if not table_name:
                    # Default to first monitored table in pair if unspecified
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
                    # Data payload: Extract keys and run dynamic schema check
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
        print("[Kafka Consumer] Stopping consumer...")
    finally:
        if consumer:
            consumer.close()
        for item in pairs:
            for engine_key in ("source_engine", "target_engine"):
                engine = item.get(engine_key)
                if engine:
                    try: 
                        engine.disconnect()
                    except: 
                        pass

if __name__ == "__main__":
    start_consumer()
