import re
import sys
from pathlib import Path

# Thư mục gốc project (cha của app/) — thêm vào sys.path để import "src.*"
# hoạt động đúng dù ông chạy lệnh từ đâu (từ app/ hay từ gốc project).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from app.secret_store import load_env, missing_error, resolve

from src.schema_evolution.engines.base import BaseEngine
from src.schema_evolution.engines.postgres import PostgresEngine 
from src.schema_evolution.engines.mysql import MySQLEngine
from src.schema_evolution.engines.mongo import MongoEngine
from src.schema_evolution.engines.clickhouse import ClickHouseEngine

ENGINE_REGISTRY: dict[str, type[BaseEngine]] = {
    "postgres": PostgresEngine,
    "mysql": MySQLEngine,
    "mongodb": MongoEngine,
    "clickhouse": ClickHouseEngine,
}

DEFAULT_FALLBACK_INTERVAL = 600


PIPELINE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")  # dùng trong registry key "pipeline/table" và tên file


DB_NAME_KEY = {"postgres": "dbname", "mysql": "database", "mongodb": "database", "clickhouse": "database"}


def _connection_errors(role: str, engine_type: str, cfg: dict) -> list[str]:
    errors = []
    if not cfg.get("host"):
        errors.append(f"{role}.config.host: required")
    db_key = DB_NAME_KEY[engine_type]
    if engine_type == "postgres" and "dbname" in cfg and "database" in cfg:
        errors.append(f"{role}.config: use only 'dbname' for postgres (both dbname and database given)")
    elif not (cfg.get(db_key) or (engine_type == "postgres" and cfg.get("database"))):
        errors.append(f"{role}.config.{db_key}: required for {engine_type}")
    port = cfg.get("port")
    if port is None and engine_type in ("mongodb", "clickhouse"):
        errors.append(f"{role}.config.port: required for {engine_type}")
    elif port is not None and not str(port).isdigit():
        errors.append(f"{role}.config.port: must be a number")
    return errors


def validate_pipeline_spec(spec) -> list[str]:
    """Lỗi cấu hình của 1 pipeline (rỗng = hợp lệ). Chỉ kiểm tra cấu trúc, không kết nối DB."""
    if not isinstance(spec, dict):
        return ["file must contain a YAML mapping"]
    errors = []
    if not isinstance(spec.get("name"), str) or not PIPELINE_NAME_RE.match(spec["name"]):
        errors.append("name: required, letters/digits/_/- only")
    for role, required in (("source", True), ("target", False)):
        part = spec.get(role)
        if part is None:
            if required:
                errors.append(f"{role}: required")
        elif not isinstance(part, dict) or part.get("type") not in ENGINE_REGISTRY:
            errors.append(f"{role}.type: must be one of {sorted(ENGINE_REGISTRY)}")
        elif not isinstance(part.get("config"), dict):
            errors.append(f"{role}.config: required mapping")
        else:
            errors += _connection_errors(role, part["type"], part["config"])
    tables = spec.get("tables")
    if not isinstance(tables, list) or not tables or not all(isinstance(t, str) and t for t in tables):
        errors.append("tables: non-empty list of table names")
    detection = spec.get("detection") or {}
    if not isinstance(detection, dict) or detection.get("mode", "polling") not in ("polling", "event_driven"):
        errors.append("detection.mode: polling or event_driven")
    return errors


def validate_main_config(cfg) -> list[str]:
    """Lỗi của config/main.yaml (rỗng = hợp lệ)."""
    if not isinstance(cfg, dict):
        return ["file must contain a YAML mapping"]
    errors = []
    if not isinstance((cfg.get("registry") or {}).get("dir"), str):
        errors.append("registry.dir: required")
    for section in ("kafka", "telegram", "scheduler"):
        if cfg.get(section) is not None and not isinstance(cfg[section], dict):
            errors.append(f"{section}: must be a mapping")
    interval = (cfg.get("scheduler") or {}).get("interval_seconds", 60) if isinstance(cfg.get("scheduler"), dict) else 60
    if not isinstance(interval, int) or interval <= 0:
        errors.append("scheduler.interval_seconds: positive integer")
    return errors


def check_with_secrets(raw, env: dict, validate) -> tuple[object, list[str]]:
    """Thay ${VAR} bằng giá trị thật rồi kiểm tra. Trả về (bản đã thay, lỗi)."""
    missing: set[str] = set()
    resolved = resolve(raw, env, missing)
    problems = validate(resolved)
    if missing:
        problems.insert(0, missing_error(missing))
    return resolved, problems


def load_pipeline_specs(pipelines_dir: Path, env: dict | None = None) -> tuple[list[dict], dict[str, str]]:
    """
    Đọc mọi config/pipelines/*.yaml, thay ${VAR} bằng bí mật thật (config/secrets.env + env).
    File lỗi (YAML hỏng, thiếu trường, thiếu bí mật, trùng tên) chỉ bị ghi vào
    errors[tên file] — các pipeline khác vẫn được nạp bình thường.
    """
    env = load_env(pipelines_dir.parent) if env is None else env
    specs, errors, owner = [], {}, {}
    for f in sorted(pipelines_dir.glob("*.yaml")) if pipelines_dir.is_dir() else []:
        try:
            raw = yaml.safe_load(f.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as e:
            errors[f.name] = f"invalid YAML: {e}"
            continue
        if raw is None:
            continue  # file rỗng
        spec, problems = check_with_secrets(raw, env, validate_pipeline_spec)
        if not problems and spec["name"] in owner:
            problems = [f"name '{spec['name']}' already used by {owner[spec['name']]}"]
        if problems:
            errors[f.name] = "; ".join(problems)
            continue
        owner[spec["name"]] = f.name
        specs.append(spec)
    return specs, errors


def load_config(config_path: str = "config/main.yaml") -> dict:
    """Cấu hình đã thay bí mật (cho CLI/công cụ chạy rời; engine dùng PipelineManager)."""
    config_dir = Path(config_path).parent
    env = load_env(config_dir)
    with open(config_path, "r", encoding="utf-8") as f:
        config = resolve(yaml.safe_load(f), env, set())
    config["pairs"], config["pipeline_errors"] = load_pipeline_specs(config_dir / "pipelines", env)
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


def log_detected_change(pipeline: str, table_name: str, result: dict, source: str) -> None:
    """Ghi Live Event CHỈ khi có thay đổi thật — "frozen"/"no_change" lặp lại
    mỗi chu kỳ không phải sự kiện mới."""
    status = result.get("status")
    if status not in ("changes_applied", "breaking_detected", "resolved_at_source"):
        return
    from app.event_log import event_logger
    if status == "resolved_at_source":
        event_logger.add_event(
            pipeline_name=pipeline, table_name=table_name,
            ddl=f"[{source}] Resolved at source: schema reverted to baseline, table unfrozen",
            status=status, severity="non_breaking",
        )
        return

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
    """Chạy engine độc lập (không kèm API): python app/scheduler.py [config/main.yaml]."""
    from app.pipeline_manager import PipelineManager
    PipelineManager(config_path).run_forever()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "config/main.yaml")