import sys
import time
from pathlib import Path

# Thư mục gốc project (cha của app/) — thêm vào sys.path để import "src.*"
# hoạt động đúng dù ông chạy lệnh từ đâu (từ app/ hay từ gốc project).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from src.schema_evolution.engines.base import BaseEngine
from src.schema_evolution.engines.postgres import PostgresEngine 
from src.schema_evolution.engines.mysql import MySQLEngine
from src.schema_evolution.engines.mongo import MongoEngine
from src.schema_evolution.engines.clickhouse import ClickHouseEngine
from src.schema_evolution.core import SchemaRegistry, run_evolution_check, make_registry_key
from src.schema_evolution.notification import TelegramNotifier
from app import runtime_status

ENGINE_REGISTRY: dict[str, type[BaseEngine]] = {
    "postgres": PostgresEngine,
    "mysql": MySQLEngine,
    "mongodb": MongoEngine,
    "clickhouse": ClickHouseEngine,
}

DEFAULT_FALLBACK_INTERVAL = 600


def load_config(config_path: str) -> dict:
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

def build_pairs(pairs_config: list[dict]) -> list[dict]:
    def _build_engine(spec: dict, pair_name: str, role: str) -> BaseEngine:
        engine_type = spec["type"]
        if engine_type not in ENGINE_REGISTRY:
            raise ValueError(
                f"Không hỗ trợ {role} type='{engine_type}' (pair '{pair_name}'). "
                f"Các type hợp lệ: {list(ENGINE_REGISTRY.keys())}"
            )
        return ENGINE_REGISTRY[engine_type](spec["config"])

    pairs = []
    for p in pairs_config:
        name = p["name"]
        target_spec = p.get("target")
        pairs.append({
            "name": name,
            "source_engine": _build_engine(p["source"], name, "source"),
            "target_engine": _build_engine(target_spec, name, "target") if target_spec else None,
            "tables": p["tables"],
            "detection": p.get("detection", {}),
            "last_run": 0
        })
    return pairs

def ensure_connected(engine: BaseEngine) -> None:
    try: 
        if engine.connection is not None and engine.health_check():
            return
    except Exception:
        pass
    engine.connect()


def run_cycle(
    pairs: list[dict],
    registry: SchemaRegistry, 
    notifier: TelegramNotifier,
    default_interval: int = 60,
    force_all: bool = False
) -> None: 
    now = time.time()
    for item in pairs: 
        name = item["name"]
        source_engine = item["source_engine"]
        target_engine = item["target_engine"]
        tables = item["tables"]
        detection = item.get("detection", {})
        mode = detection.get("mode", "polling")

        if mode == "event_driven":
            pair_interval = detection.get("fallback_polling_interval_seconds", DEFAULT_FALLBACK_INTERVAL)
        else:
            pair_interval = default_interval

        if not force_all and (now - item.get("last_run", 0) < pair_interval):
            continue

        item["last_run"] = now

        try:
            ensure_connected(source_engine)
            if target_engine is not None:
                ensure_connected(target_engine)
        except Exception as e:
            print(f"[scheduler] Khong ket noi duoc '{name}': {e}")
            runtime_status.record_scan(name, ok=False, error=f"Mất kết nối: {e}")
            continue

        mode_label = f"event_driven fallback ({pair_interval}s)" if mode == "event_driven" else f"polling ({pair_interval}s)"
        print(f"[scheduler] Executing scan for '{name}' [{mode_label}]...")

        errors = []
        for table_name in tables:
            try:
                registry_key = make_registry_key(name, table_name)
                result = run_evolution_check(
                    source_engine, target_engine, table_name, registry, notifier,
                    registry_key=registry_key,
                )
                print(f"[scheduler] {name}.{table_name}: {result['status']}")
                log_detected_change(name, table_name, result, source="polling")
            except Exception as e:
                errors.append(f"{table_name}: {e}")
                print(f"[scheduler] Loi khi quet {name}.{table_name}: {e}")
        runtime_status.record_scan(name, ok=not errors, error="; ".join(errors) or None)


def log_detected_change(pipeline: str, table_name: str, result: dict, source: str) -> None:
    """Ghi Live Event CHỈ khi có thay đổi thật — "frozen"/"no_change" lặp lại
    mỗi chu kỳ không phải sự kiện mới."""
    status = result.get("status")
    if status not in ("changes_applied", "breaking_detected"):
        return
    from app.event_log import event_logger

    def describe(changes):
        return ", ".join(
            f"{c.change_type.value} {c.column_name or c.constraint_name or ''}".strip() for c in changes
        )

    applied = result.get("non_breaking_applied") or []
    pending = result.get("breaking_pending") or []
    parts = []
    if applied:
        parts.append(f"Auto-synced: {describe(applied)}")
    if pending:
        parts.append(f"Pending approval: {describe(pending)}")
    event_logger.add_event(
        pipeline_name=pipeline,
        table_name=table_name,
        ddl=f"[{source}] " + " | ".join(parts),
        status=status,
        severity="breaking" if status == "breaking_detected" else "non_breaking",
    )
        
def main(config_path: str = "config/main.yaml") -> None:
    if __name__ == "__main__" and len(sys.argv) > 1:
        config_path = sys.argv[1]
    config = load_config(config_path)

    registry = SchemaRegistry(config["registry"]["dir"])
    notifier = TelegramNotifier(
        bot_token=config["telegram"]["bot_token"],
        chat_id=config["telegram"]["chat_id"],
    )
    pairs = build_pairs(config["pairs"])
    default_interval = config["scheduler"]["interval_seconds"]
    print(f"[scheduler] Starting loop, default interval {default_interval}s. Ctrl+C to stop.")
    
    try:
        while True:
            try:
                run_cycle(pairs, registry, notifier, default_interval=default_interval)
            except Exception as e:
                # Không để 1 lỗi bất ngờ làm chết cả vòng lặp scheduler.
                print(f"[scheduler] Loi khong mong doi trong chu ky: {e}")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n[scheduler] Nhan Ctrl+C, dang dong ket noi...")
    finally:
        for item in pairs:
            for engine_key in ("source_engine", "target_engine"):
                engine = item.get(engine_key)
                if engine is None:
                    continue
                try:
                    engine.disconnect()
                except Exception:
                    pass
        print("[scheduler] Da dung.")

if __name__ == "__main__":
    main()