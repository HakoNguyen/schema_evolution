# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware

import sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import threading
from src.schema_evolution.core import SchemaRegistry, approve_change_and_sync
from src.schema_evolution.notification import TelegramNotifier
from app.scheduler import main as scheduler_main
from src.schema_evolution.engines.postgres import PostgresEngine
from src.schema_evolution.engines.mysql import MySQLEngine
from src.schema_evolution.engines.mongo import MongoEngine
from src.schema_evolution.engines.clickhouse import ClickHouseEngine

ENGINE_REGISTRY = {
    "postgres": PostgresEngine,
    "mysql": MySQLEngine,
    "mongodb": MongoEngine,
    "clickhouse": ClickHouseEngine,
}

app = FastAPI(title="Schema Evolution API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/tables/{registry_key}/edit")
def edit_schema(registry_key: str, payload: dict):
    config = load_config()
    registry = get_registry(config)
    
    columns_data = payload.get("columns", [])
    if not columns_data:
        raise HTTPException(status_code=400, detail="Missing columns data")
        
    from api.schema_editor import apply_web_edit
    return apply_web_edit(registry_key, columns_data, registry)

@app.on_event("startup")
def start_scheduler():
    def run_scheduler():
        print("[API] Starting background scheduler...")
        scheduler_main("config/main.yaml")
    
    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()

@app.on_event("startup")
def start_kafka_consumer():
    def run_consumer():
        print("[API] Starting background Kafka Consumer...")
        from app.kafka_consumer import start_consumer
        try:
            start_consumer("config/main.yaml")
        except Exception as e:
            print(f"[API] Kafka Consumer error: {e}")
            
    thread = threading.Thread(target=run_consumer, daemon=True)
    thread.start()

def load_config(config_path: str = "config/main.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    config["pairs"] = []
    pipelines_dir = Path(config_path).parent / "pipelines"
    if pipelines_dir.exists() and pipelines_dir.is_dir():
        for p_file in pipelines_dir.glob("*.yaml"):
            with open(p_file, "r", encoding="utf-8") as pf:
                pair_config = yaml.safe_load(pf)
                if pair_config:
                    config["pairs"].append(pair_config)
    return config

def get_registry(config: dict) -> SchemaRegistry:
    return SchemaRegistry(config["registry"]["dir"])

def get_notifier(config: dict) -> TelegramNotifier:
    return TelegramNotifier(
        bot_token=config["telegram"]["bot_token"],
        chat_id=config["telegram"]["chat_id"],
    )

def build_target_engine(pair_config: dict):
    target_spec = pair_config.get("target")
    if not target_spec:
        return None
    engine_cls = ENGINE_REGISTRY[target_spec["type"]]
    engine = engine_cls(target_spec["config"])
    engine.connect()
    return engine

@app.get("/api/events")
def get_cdc_events():
    from app.event_log import event_logger
    return event_logger.get_events()

@app.get("/api/topology")
def get_pipeline_topology():
    config = load_config()
    registry = get_registry(config)
    pipelines = []
    
    for pair in config.get("pairs", []):
        pair_name = pair["name"]
        source_type = pair.get("source", {}).get("type", "unknown")
        target_type = pair.get("target", {}).get("type", "none")
        
        tables = []
        for t_name in pair.get("tables", []):
            key = f"{pair_name}/{t_name}"
            is_frozen = registry.is_frozen(key)
            version = registry.get_version(key)
            tables.append({
                "name": t_name,
                "registry_key": key,
                "is_frozen": is_frozen,
                "version": version
            })
            
        pipelines.append({
            "name": pair_name,
            "source": {
                "type": source_type,
                "host": pair.get("source", {}).get("config", {}).get("host", "localhost")
            },
            "broker": {
                "type": "Redpanda (Kafka CDC)",
                "status": "active",
                "topic": pair_name
            },
            "gatekeeper": {
                "status": "healthy" if not any(t["is_frozen"] for t in tables) else "attention_required"
            },
            "target": {
                "type": target_type,
                "configured": target_type != "none"
            },
            "tables": tables
        })
    return pipelines

@app.get("/")
def read_root():
    return {"message": "Schema Evolution API is running! Please access the frontend Web App at http://localhost:5173"}

@app.get("/api/tables")
def get_tables():
    config = load_config()
    registry = get_registry(config)
    items = []
    
    for pair in config.get("pairs", []):
        pair_name = pair["name"]
        source_type = pair.get("source", {}).get("type", "unknown")
        target_type = pair.get("target", {}).get("type", "none")
        mode = f"Đồng bộ {source_type} → {target_type}" if "target" in pair else "Chỉ phát hiện"
        
        for table_name in pair.get("tables", []):
            registry_key = f"{pair_name}/{table_name}"
            is_frozen = registry.is_frozen(registry_key)
            version = registry.get_version(registry_key)
            updated_at = "—"
            if version:
                ts_raw = registry.get_version_timestamp(registry_key, version)
                if ts_raw:
                    updated_at = ts_raw
            
            items.append({
                "pair_name": pair_name,
                "table_name": table_name,
                "registry_key": registry_key,
                "mode": mode,
                "source_type": source_type,
                "target_type": target_type,
                "is_frozen": is_frozen,
                "version": version,
                "updated_at": updated_at
            })
    return items

@app.get("/api/tables/{registry_key:path}/draft")
def get_table_draft(registry_key: str):
    config = load_config()
    registry = get_registry(config)
    draft = registry.load_draft(registry_key)
    if not draft:
        return {"exists": False}
    return {"exists": True, "draft": draft}

@app.get("/api/tables/{registry_key:path}/versions")
def get_table_versions(registry_key: str):
    config = load_config()
    registry = get_registry(config)
    versions = registry.list_versions(registry_key)
    
    res = []
    for v in sorted(versions, reverse=True):
        ts = registry.get_version_timestamp(registry_key, v)
        res.append({"version": v, "timestamp": ts})
        
    return res

@app.get("/api/tables/{registry_key:path}/versions/{version}")
def get_table_version_detail(registry_key: str, version: int):
    config = load_config()
    registry = get_registry(config)
    schema = registry.load_version(registry_key, version)
    if not schema:
        return {"exists": False}
        
    return {
        "exists": True,
        "schema": {
            "table_name": schema.table_name,
            "columns": [{"name": c.name, "data_type": c.data_type, "nullable": c.nullable, "default": c.default, "max_length": c.max_length} for c in schema.columns],
            "primary_key": schema.primary_key,
            "foreign_keys": [{"column_name": fk.column_name, "ref_table": fk.ref_table, "ref_column": fk.ref_column, "on_delete": fk.on_delete} for fk in schema.foreign_keys]
        }
    }

@app.get("/api/tables/{registry_key:path}")
def get_table_details(registry_key: str):
    config = load_config()
    registry = get_registry(config)
    
    schema = registry.load(registry_key)
    if not schema:
        return {"exists": False}
        
    version = registry.get_version(registry_key)
    return {
        "exists": True,
        "version": version,
        "schema": {
            "table_name": schema.table_name,
            "columns": [{"name": c.name, "data_type": c.data_type, "nullable": c.nullable, "default": c.default, "max_length": c.max_length} for c in schema.columns],
            "primary_key": schema.primary_key,
            "foreign_keys": [{"column_name": fk.column_name, "ref_table": fk.ref_table, "ref_column": fk.ref_column, "on_delete": fk.on_delete} for fk in schema.foreign_keys]
        }
    }

@app.post("/api/tables/{registry_key:path}/approve")
def approve_changes(registry_key: str):
    config = load_config()
    registry = get_registry(config)
    notifier = get_notifier(config)
    
    clean_key = registry_key.replace("__", "/")
    pair_name, table_name = clean_key.split("/", 1) if "/" in clean_key else (clean_key, clean_key)
    
    pair_config = None
    for pair in config.get("pairs", []):
        if pair["name"] == pair_name:
            pair_config = pair
            break
            
    if not pair_config:
        raise HTTPException(status_code=404, detail="Pair config not found")
        
    target_engine = None
    try:
        target_engine = build_target_engine(pair_config)
    except Exception as e:
        print(f"Không kết nối được target ({e})")
        
    result = approve_change_and_sync(target_engine, registry_key, registry, registry_key=registry_key)
    
    if target_engine is not None:
        target_engine.disconnect()
        
    notifier.notify_change_reviewed(
        table_name, approved=True, pair_name=pair_name
    )
    
    return {"status": "success", "result": result}

@app.post("/api/tables/{registry_key:path}/reject")
def reject_changes(registry_key: str):
    config = load_config()
    registry = get_registry(config)
    notifier = get_notifier(config)
    
    clean_key = registry_key.replace("__", "/")
    pair_name, table_name = clean_key.split("/", 1) if "/" in clean_key else (clean_key, clean_key)
    
    registry.reject_change(registry_key)
    notifier.notify_change_reviewed(
        table_name, approved=False, pair_name=pair_name
    )
    
    return {"status": "success"}

@app.post("/api/tables/{registry_key:path}/test_sandbox")
def test_sandbox(registry_key: str):
    config = load_config()
    registry = get_registry(config)
    
    clean_key = registry_key.replace("__", "/")
    pair_name, table_name = clean_key.split("/", 1) if "/" in clean_key else (clean_key, clean_key)
    
    pair_config = None
    for pair in config.get("pairs", []):
        if pair["name"] == pair_name:
            pair_config = pair
            break
            
    if not pair_config:
        raise HTTPException(status_code=404, detail="Pair config not found")
        
    target_engine = None
    try:
        target_engine = build_target_engine(pair_config)
    except Exception as e:
        return {"status": "error", "message": f"Cannot connect to target database: {str(e)}"}
        
    from api.sandbox import run_sandbox_test
    result = run_sandbox_test(target_engine, registry_key, registry)
    return result

@app.post("/api/tables/{registry_key:path}/edit")
def edit_schema(registry_key: str, payload: dict):
    config = load_config()
    registry = get_registry(config)
    
    columns_data = payload.get("columns", [])
    if not columns_data:
        raise HTTPException(status_code=400, detail="Missing columns data")
        
    from api.schema_editor import apply_web_edit
    return apply_web_edit(registry_key, columns_data, registry)

