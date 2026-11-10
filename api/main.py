# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware

import os
import sys
import time
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import threading
from src.schema_evolution.core import SchemaRegistry, approve_change_and_sync
from src.schema_evolution.notification import TelegramNotifier
from app.scheduler import (
    DEFAULT_FALLBACK_INTERVAL, ENGINE_REGISTRY, PIPELINE_NAME_RE, check_with_secrets,
    load_config as _load_config_files, load_pipeline_specs, validate_main_config, validate_pipeline_spec,
)
from app.secret_store import load_env, mask, unmask
from app import runtime_status

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

_manager = None  # PipelineManager của engine chạy cùng API


@app.on_event("startup")
def start_engine():
    """Một PipelineManager duy nhất: tự nạp lại main.yaml + config/pipelines/*.yaml, mỗi pipeline một worker."""
    global _manager
    from app.pipeline_manager import PipelineManager
    _manager = PipelineManager("config/main.yaml")
    threading.Thread(target=_manager.run_forever, daemon=True, name="pipeline-manager").start()


def load_config(config_path: str = "config/main.yaml") -> dict:
    """Cấu hình engine ĐANG chạy (kể cả khi file vừa bị sửa hỏng), không đọc lại file."""
    return _manager.snapshot() if _manager is not None else _load_config_files(config_path)

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

# ==============================================================================
# INTEGRATION CONTRACT cho data plane (loader, Kafka Connect, Spark job...):
#   Gate API      — hỏi bảng có đang bị freeze không trước khi ghi
#   Reporting API — tự báo trạng thái + chỉ số tuỳ ý để hiển thị trên UI
# Engine không biết gì về bên trong các thành phần này.
# ==============================================================================

COMPONENT_NAME_RE = PIPELINE_NAME_RE


def _monitored_pipeline(pipeline: str) -> dict:
    pair = next((p for p in load_config().get("pairs", []) if p["name"] == pipeline), None)
    if pair is None:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline}' is not monitored")
    return pair


@app.get("/api/gate/{pipeline}/{table}")
def get_gate(pipeline: str, table: str):
    """open = được ghi; frozen = có thay đổi breaking chờ duyệt -> thành phần ghi dữ liệu phải dừng."""
    if table not in _monitored_pipeline(pipeline)["tables"]:
        raise HTTPException(status_code=404, detail=f"Table '{table}' is not monitored in '{pipeline}'")
    registry = get_registry(load_config())
    key = f"{pipeline}/{table}"
    frozen = registry.is_frozen(key)
    draft = registry.load_draft(key) if frozen else None
    return {
        "pipeline": pipeline,
        "table": table,
        "state": "frozen" if frozen else "open",
        "schema_version": registry.get_version(key),
        "pending_changes": [
            {"change_type": c.get("change_type"), "column": c.get("column_name") or c.get("constraint_name")}
            for c in (draft or {}).get("breaking_changes", [])
        ],
        # RENAME đã duyệt: message cũ còn trong hàng đợi mang tên cột cũ -> ghi vào cột mới.
        "column_renames": registry.column_renames(key),
    }


@app.post("/api/pipelines/{pipeline}/components/{component}")
def report_component(pipeline: str, component: str, payload: dict):
    """
    Body: {"state": "running", "role": "sink", "metrics": {"rows_per_sec": 120.5}, "message": "..."}
    state gợi ý: running | hold | paused | failed | stopped (hiển thị màu tương ứng trên UI).
    """
    _monitored_pipeline(pipeline)
    if not COMPONENT_NAME_RE.match(component):
        raise HTTPException(status_code=400, detail="Invalid component name (letters, digits, _ and - only)")
    state, metrics = payload.get("state"), payload.get("metrics") or {}
    errors = []
    if not isinstance(state, str) or not 0 < len(state) <= 32:
        errors.append("state: required string (max 32 chars)")
    if not isinstance(metrics, dict) or len(metrics) > 30 or not all(
            isinstance(k, str) and (v is None or isinstance(v, (int, float, str, bool))) for k, v in metrics.items()):
        errors.append("metrics: mapping of up to 30 scalar values")
    if errors:
        _reject(errors)
    runtime_status.record_component(pipeline, component, {
        "state": state,
        "role": str(payload.get("role") or "")[:64],
        "metrics": metrics,
        "message": str(payload.get("message") or "")[:500],
    })
    return {"status": "ok"}


@app.get("/api/pipelines/{pipeline}/components")
def list_components(pipeline: str):
    _monitored_pipeline(pipeline)
    return runtime_status.get_components(pipeline)


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
            
        detection = pair.get("detection", {})
        mode = detection.get("mode", "polling")
        scan = runtime_status.get_pipeline(pair_name)
        # Chưa quét lần nào -> "pending"; lần quét gần nhất lỗi -> "error".
        scan_status = "pending" if not scan else ("active" if scan.get("last_scan_ok") else "error")
        scan_info = {
            "last_scan_at": scan.get("last_scan_at"),
            "last_error": scan.get("last_error"),
        }

        if mode == "event_driven":
            # Cùng nguồn giá trị với kafka_consumer.start_consumer / scheduler.run_cycle.
            kafka_cfg = {**config.get("kafka", {}), **detection.get("kafka", {})}
            topic = kafka_cfg.get("topic", pair_name)
            bootstrap = kafka_cfg.get("bootstrap_servers", "localhost:19092")
            consumer = runtime_status.get_consumer(bootstrap)
            consumer_state = consumer.get("state", "disconnected")
            fallback_interval = detection.get("fallback_polling_interval_seconds", DEFAULT_FALLBACK_INTERVAL)
            transport = {
                "kind": "broker",
                "type": "Redpanda (Kafka CDC)",
                "topic": topic,
                "bootstrap_servers": bootstrap,
                "mode": "event_driven",
                "status": "active" if consumer_state == "connected" else consumer_state,
                "error": consumer.get("error"),
                "fallback": {
                    "kind": "scheduler",
                    "interval": fallback_interval,
                    "status": scan_status,
                    **scan_info,
                }
            }
        else:
            interval = config.get("scheduler", {}).get("interval_seconds", 60)
            transport = {
                "kind": "scheduler",
                "type": "Polling Scheduler",
                "interval": interval,
                "mode": "polling",
                "status": scan_status,
                **scan_info,
            }

        pipelines.append({
            "name": pair_name,
            "source": {
                "type": source_type,
                "host": pair.get("source", {}).get("config", {}).get("host", "localhost")
            },
            "transport": transport,
            "broker": transport, # Backward compatibility alias
            "gatekeeper": {
                "status": "healthy" if not any(t["is_frozen"] for t in tables) else "attention_required"
            },
            "target": {
                "type": target_type,
                "configured": target_type != "none"
            },
            "tables": tables,
            "components": runtime_status.get_components(pair_name),
        })
    # File cấu hình lỗi: engine không giám sát nhưng vẫn hiện trên UI kèm lý do.
    for file_name, error in config.get("pipeline_errors", {}).items():
        pipelines.append({"name": Path(file_name).stem, "file": file_name, "config_error": error, "tables": []})
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
        is_sync = "target" in pair and target_type not in (None, "none")
        mode = f"{source_type.upper()} → {target_type.upper()}" if is_sync else f"{source_type.upper()} (source only)"


        
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

    has_target = bool(pair_config.get("target"))
    if has_target and not registry.sandbox_passed(registry_key):
        return {"status": "error", "message": "Run a successful sandbox test for this draft first."}

    target_engine = None
    try:
        target_engine = build_target_engine(pair_config)
    except Exception as e:
        # Pair có target mà không kết nối được: không approve, giữ frozen,
        # tránh để Registry lệch so với target thật.
        return {"status": "error", "message": f"Cannot connect to target database: {e}"}

    try:
        result = approve_change_and_sync(target_engine, table_name, registry, registry_key=registry_key)
    finally:
        if target_engine is not None:
            target_engine.disconnect()

    if result["status"] != "approved":
        message = {
            "failed": "Applying DDL on target failed: " + "; ".join(result.get("errors", [])),
            "not_frozen": "Table is not pending approval.",
            "no_draft": "Draft not found.",
        }.get(result["status"], result["status"])
        return {"status": "error", "message": message, "result": _summarize_result(result)}

    notifier.notify_change_reviewed(
        table_name, approved=True, pair_name=pair_name
    )
    applied = ", ".join(_summarize_result(result)["applied_to_target"]) or "registry only"
    _log_review(pair_name, table_name, "approved", f"Approved: {applied} applied to target")

    return {"status": "success", "result": _summarize_result(result)}


def _log_review(pair_name: str, table_name: str, status: str, text: str) -> None:
    """Ghi quyết định duyệt vào Live Event, để timeline có cả "chờ duyệt" lẫn kết quả."""
    from app.event_log import event_logger
    event_logger.add_event(pipeline_name=pair_name, table_name=table_name,
                           ddl=f"[review] {text}", status=status, severity="review")


def _summarize_result(result: dict) -> dict:
    """SchemaChange không serialize JSON được — chỉ trả về tên change."""
    def names(changes):
        return [f"{c.change_type.value}:{c.column_name or c.constraint_name or ''}" for c in changes]
    return {
        "status": result["status"],
        "applied_to_target": names(result.get("applied_to_target", [])),
        "failed_on_target": names(result.get("failed_on_target", [])),
    }

@app.post("/api/tables/{registry_key:path}/reject")
def reject_changes(registry_key: str):
    config = load_config()
    registry = get_registry(config)
    notifier = get_notifier(config)
    
    clean_key = registry_key.replace("__", "/")
    pair_name, table_name = clean_key.split("/", 1) if "/" in clean_key else (clean_key, clean_key)
    
    with registry.lock(registry_key):
        rejected = registry.reject_change(registry_key)
    if not rejected:
        return {"status": "error", "message": "No draft to reject."}
    notifier.notify_change_reviewed(
        table_name, approved=False, pair_name=pair_name
    )
    _log_review(pair_name, table_name, "rejected", "Rejected: draft discarded, source must be rolled back")

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
    try:
        result = run_sandbox_test(target_engine, registry_key, registry)
    finally:
        if target_engine is not None:
            target_engine.disconnect()
    registry.mark_sandbox_result(registry_key, result["status"] == "success", result.get("message", ""))
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

# ==============================================================================
# PIPELINE & SYSTEM CONFIGURATION APIs (READ/WRITE YAML FILES ON DISK)
# ==============================================================================

@app.get("/api/config/system")
def get_system_config():
    config_path = Path("config/main.yaml")
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="config/main.yaml not found")
    try:
        return mask(yaml.safe_load(config_path.read_text(encoding="utf-8")) or {})
    except yaml.YAMLError as e:  # file đang hỏng: engine vẫn chạy bằng cấu hình cũ, UI báo lỗi để sửa
        return {"_error": f"invalid YAML: {e}"}

PIPELINES_DIR = Path("config/pipelines")
MAIN_CONFIG = Path("config/main.yaml")


def _write_yaml(path: Path, data: dict) -> None:
    """Ghi nguyên tử (file tạm rồi đổi tên): engine quét mỗi 3s không bao giờ đọc phải file ghi dở."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    for _ in range(10):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # Windows: engine đang mở file để đọc -> thử lại
            time.sleep(0.1)
    os.replace(tmp, path)


def _reject(errors: list[str]):
    raise HTTPException(status_code=422, detail={"message": "Invalid configuration", "errors": errors})


def _read_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, yaml.YAMLError):
        return {}


def _clean(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if not k.startswith("_")}  # bỏ trường chỉ dùng cho UI


def _pipeline_file(name: str) -> Path:
    # Tên đi thẳng vào đường dẫn file: chặn "../" và ký tự lạ.
    if not PIPELINE_NAME_RE.match(name or ""):
        raise HTTPException(status_code=400, detail="Invalid pipeline name (letters, digits, _ and - only)")
    return PIPELINES_DIR / f"{name}.yaml"


@app.put("/api/config/system")
def update_system_config(payload: dict):
    cfg = unmask(_clean(payload), _read_yaml(MAIN_CONFIG))
    resolved, errors = check_with_secrets(cfg, load_env(MAIN_CONFIG.parent), validate_main_config)
    if errors:
        _reject(errors)
    _write_yaml(MAIN_CONFIG, cfg)  # ghi bản có ${VAR}, không bao giờ ghi giá trị bí mật đã thay
    message = "Saved config/main.yaml — applied by the engine within ~3s"
    if _manager is not None and resolved["registry"]["dir"] != _manager.global_cfg["registry"]["dir"]:
        message += ". registry.dir change takes effect only after restarting the backend"
    return {"status": "success", "message": message}

@app.get("/api/config/pipelines")
def get_pipelines_config():
    pipelines_dir = Path("config/pipelines")
    if not pipelines_dir.exists():
        return []
    _, errors = load_pipeline_specs(pipelines_dir)
    res = []
    for p_file in sorted(pipelines_dir.glob("*.yaml")):
        try:
            cfg = yaml.safe_load(p_file.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            cfg = None  # YAML hỏng: vẫn liệt kê để người dùng thấy lỗi và sửa
        if cfg is None and p_file.name not in errors:
            continue  # file rỗng
        cfg = mask(cfg) if isinstance(cfg, dict) else {"name": p_file.stem}
        cfg["_filename"] = p_file.name
        if p_file.name in errors:
            cfg["_error"] = errors[p_file.name]
        res.append(cfg)
    return res

@app.post("/api/config/pipelines")
def create_pipeline_config(payload: dict):
    spec = _clean(payload)
    _, errors = check_with_secrets(spec, load_env(PIPELINES_DIR.parent), validate_pipeline_spec)
    if errors:
        _reject(errors)
    target_file = _pipeline_file(spec["name"])
    specs, _ = load_pipeline_specs(PIPELINES_DIR)
    if target_file.exists() or any(s["name"] == spec["name"] for s in specs):
        raise HTTPException(status_code=409, detail=f"Pipeline '{spec['name']}' already exists")
    PIPELINES_DIR.mkdir(parents=True, exist_ok=True)
    _write_yaml(target_file, spec)
    return {"status": "success", "filename": target_file.name,
            "message": f"Saved {target_file.name} — the engine starts monitoring within ~3s"}

@app.put("/api/config/pipelines/{name}")
def update_pipeline_config(name: str, payload: dict):
    target_file = _pipeline_file(name)
    if not target_file.exists():
        raise HTTPException(status_code=404, detail=f"{name}.yaml not found")
    spec = unmask(_clean(payload), _read_yaml(target_file))  # "********" = giữ bí mật cũ trong file
    if spec.get("name") != name:
        # Registry/lịch sử schema gắn với tên pipeline: đổi tên = mồ côi toàn bộ trạng thái cũ.
        _reject(["name: cannot be changed (schema history is keyed by it); create a new pipeline instead"])
    _, errors = check_with_secrets(spec, load_env(PIPELINES_DIR.parent), validate_pipeline_spec)
    if errors:
        _reject(errors)
    _write_yaml(target_file, spec)
    return {"status": "success", "filename": target_file.name,
            "message": f"Updated {target_file.name} — the engine reloads it within ~3s"}

@app.delete("/api/config/pipelines/{name}")
def delete_pipeline_config(name: str):
    target_file = _pipeline_file(name)
    if not target_file.exists():
        raise HTTPException(status_code=404, detail=f"{name}.yaml not found")
    target_file.unlink()
    return {"status": "success", "message": f"Deleted {name}.yaml — the engine stops monitoring within ~3s"}


