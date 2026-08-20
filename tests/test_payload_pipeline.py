import json
import time
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pymongo
import clickhouse_connect
from datetime import datetime
from kafka import KafkaProducer

KAFKA_BOOTSTRAP = "localhost:19092"
TOPIC = "mongo_to_clickhouse"

def run_test():
    print("=========================================================")
    print("Testing Dynamic CDC Payload Extractor & Auto-Flattening")
    print("=========================================================")

    # 1. Prepare new CDC Data Message with BRAND NEW ATTRIBUTES
    cdc_message = {
        "id": "cdc_evt_999",
        "data": {
            "name": "Sarah Jenkins",
            "email": "sarah@cybertech.org",
            "age": 29,
            "special_bonus_points": 9500,        # NEW ATTRIBUTE (INT)
            "is_enterprise_client": True,       # NEW ATTRIBUTE (BOOL)
            "membership_tier": "Diamond"        # NEW ATTRIBUTE (VARCHAR)
        },
        "ts_ms": int(time.time() * 1000),
        "op": "c"
    }

    # 2. Insert corresponding document in Mongo source
    db = pymongo.MongoClient('mongodb://localhost:27017')['sample_db']
    db.users.insert_one(cdc_message["data"])
    print("1. Inserted document with new attributes (special_bonus_points, is_enterprise_client, membership_tier) into Mongo.")

    # 3. Publish CDC message to Kafka topic
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
    )
    producer.send(TOPIC, cdc_message)
    producer.flush()
    print(f"2. Published CDC Data Payload message to Kafka topic '{TOPIC}'.")

    # 4. Trigger Schema Evolution Check
    from app.scheduler import load_config, build_pairs, ensure_connected
    from src.schema_evolution.core import SchemaRegistry, run_evolution_check
    from src.schema_evolution.notification import TelegramNotifier

    cfg = load_config('config/main.yaml')
    pairs = build_pairs(cfg['pairs'])
    pair = [p for p in pairs if p['name'] == 'mongo_to_clickhouse'][0]
    reg = SchemaRegistry('data/registry')

    ensure_connected(pair['source_engine'])
    ensure_connected(pair['target_engine'])

    print("3. Executing Schema Evolution Engine check...")
    res = run_evolution_check(
        pair['source_engine'], pair['target_engine'], 'users', reg,
        TelegramNotifier('', ''), registry_key='mongo_to_clickhouse/users'
    )
    print(f"4. Schema Evolution Check Result: {res}")

    # 5. Verify ClickHouse Schema expansion
    ch = clickhouse_connect.get_client(
        host='localhost', port=8123, username='default', password='clickhouse123', database='default'
    )
    desc = ch.query('DESCRIBE TABLE users').result_rows
    col_names = [row[0] for row in desc]

    print("\n=========================================================")
    print("Verified ClickHouse Table Columns:")
    for row in desc:
        print(f"  Column: {row[0]:<25} Type: {row[1]}")
    print("=========================================================")

    assert "special_bonus_points" in col_names, "special_bonus_points missing in ClickHouse!"
    assert "is_enterprise_client" in col_names, "is_enterprise_client missing in ClickHouse!"
    assert "membership_tier" in col_names, "membership_tier missing in ClickHouse!"

    print("\nSUCCESS! All new payload attributes were automatically extracted and created on ClickHouse Warehouse!")

if __name__ == "__main__":
    run_test()
