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
from src.schema_evolution.core import SchemaRegistry, run_evolution_check
from src.schema_evolution.notification import TelegramNotifier

ENGINE_REGISTRY: dict[str, type[BaseEngine]] = {
    "postgres": PostgresEngine,
    "mysql": MySQLEngine,
    "mongodb": MongoEngine,
    "clickhouse": ClickHouseEngine,
}

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
) -> None: 
    for item in pairs: 
        name = item["name"]
        source_engine = item["source_engine"]
        target_engine = item["target_engine"]
        tables = item["tables"]

        try: 
            ensure_connected(source_engine)
            if target_engine is not None:
                ensure_connected(target_engine)
        except Exception as e: 
            print(f"[scheduler] Không kết nối được '{name}': {e}")
            continue

        for table_name in tables: 
            try: 
                registry_key = f"{name}__{table_name}"
                result = run_evolution_check(
                    source_engine, target_engine, table_name, registry, notifier,
                    registry_key=registry_key,
                )
                print(f"[scheduler] {name}.{table_name}: {result['status']}")
            except Exception as e:
                print(f"[scheduler] Lỗi khi quét {name}.{table_name}: {e}")
        
def main(config_path: str = "config/main.yaml") -> None:
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    config = load_config(config_path)

    registry = SchemaRegistry(config["registry"]["dir"])
    notifier = TelegramNotifier(
        bot_token=config["telegram"]["bot_token"],
        chat_id=config["telegram"]["chat_id"],
    )
    pairs = build_pairs(config["pairs"])
    interval = config["scheduler"]["interval_seconds"]

    print(f"[scheduler] Bắt đầu vòng lặp, chu kỳ {interval}s. Ctrl+C để dừng.")
    try: 
        while True: 
            run_cycle(pairs, registry, notifier)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[scheduler] Nhận Ctrl+C, đang đóng kết nối...")
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
        print("[scheduler] Đã dừng.")

if __name__ == "__main__":
    main()