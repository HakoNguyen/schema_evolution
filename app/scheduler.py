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


# Tên bảng đi thẳng vào câu DDL -> chỉ cho ký tự an toàn (chặn khoảng trắng, ;, dấu nháy). Tối đa 1 dấu chấm: schema.table.
TABLE_NAME_RE = re.compile(r"^[A-Za-z0-9_$-]+(\.[A-Za-z0-9_$-]+)?$")
# Bảng đích đi vào ALTER TABLE không có nháy trên PG/MySQL/ClickHouse -> chỉ định danh SQL thường.
TARGET_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


def table_entries(tables: list) -> list[tuple]:
    """
    tables -> [(bảng nguồn, bảng đích)]. Ba dạng:
      "orders"                                  -> ("orders", "orders")
      "sales.orders"                            -> ("sales.orders", "orders")   schema khác public
      {source: sales.orders, target: orders_raw} -> ánh xạ tường minh
    """
    out = []
    for t in tables:
        src, dst = (t.get("source"), t.get("target")) if isinstance(t, dict) else (t, None)
        out.append((src, dst or (src.rsplit(".", 1)[-1] if isinstance(src, str) else None)))
    return out


def _table_errors(tables, has_target: bool) -> list[str]:
    if not isinstance(tables, list) or not tables:
        return ['tables: non-empty list ("orders", "schema.orders" or {source: ..., target: ...})']
    errors = []
    entries = table_entries(tables)
    for raw, (src, dst) in zip(tables, entries):
        extra = set(raw) - {"source", "target"} if isinstance(raw, dict) else set()
        if extra or not all(isinstance(n, str) and TABLE_NAME_RE.match(n) for n in (src, dst)):
            errors.append(f"tables: invalid entry {raw!r} (letters, digits, _ $ - and one optional schema dot)")
        elif has_target and not TARGET_NAME_RE.match(dst):
            errors.append(f"tables: target table '{dst}' goes into DDL unquoted — use letters, digits and _ "
                          f"(map it: {{source: {src}, target: {dst.replace('-', '_').replace('$', '_')}}})")
    for label, names in (("source", [s for s, _ in entries]), ("target", [d for _, d in entries] if has_target else [])):
        dupes = sorted({n for n in names if isinstance(n, str) and names.count(n) > 1})
        if dupes:
            errors.append(f"tables: {label} table listed twice: {', '.join(dupes)}")
    return errors


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


COMPONENT_KEYS = {"name", "role", "tables", "kafka_group", "kafka_connect"}


def _component_errors(components, tables) -> list[str]:
    """components: thành phần data plane khai báo trước. Key gõ sai phải báo lỗi: kafka_connect gõ sai
    = engine im lặng không pause sink khi freeze."""
    if components is None:
        return []
    if not isinstance(components, list):
        return ["components: must be a list"]
    sources = {s for s, _ in table_entries(tables)} if isinstance(tables, list) else set()
    errors, names, connectors = [], set(), set()
    for i, c in enumerate(components):
        where = f"components[{i}]"
        if not isinstance(c, dict):
            errors.append(f"{where}: must be a mapping")
            continue
        if set(c) - COMPONENT_KEYS:
            errors.append(f"{where}: unknown key(s) {sorted(set(c) - COMPONENT_KEYS)}, allowed {sorted(COMPONENT_KEYS)}")
        name = c.get("name")
        if not isinstance(name, str) or not PIPELINE_NAME_RE.match(name):
            errors.append(f"{where}.name: required, letters/digits/_/- only")
        elif name in names:
            errors.append(f"{where}.name: '{name}' listed twice")
        names.add(name)
        t = c.get("tables")
        if t is not None and not (isinstance(t, list) and t and all(isinstance(x, str) and x in sources for x in t)):
            errors.append(f"{where}.tables: non-empty list of this pipeline's source tables")
        for key in ("role", "kafka_group"):
            if c.get(key) is not None and not (isinstance(c[key], str) and c[key].strip()):
                errors.append(f"{where}.{key}: non-empty string")
        kc = c.get("kafka_connect")
        if kc is not None and not (isinstance(kc, dict) and set(kc) == {"url", "connector"}
                                   and isinstance(kc["url"], str) and kc["url"].startswith(("http://", "https://"))
                                   and isinstance(kc["connector"], str) and kc["connector"]):
            errors.append(f"{where}.kafka_connect: exactly {{url: http://host:8083, connector: <name>}}")
        elif kc is not None:
            if connector_key(kc) in connectors:
                errors.append(f"{where}.kafka_connect: connector '{kc['connector']}' declared twice "
                              "(merge into one component with all its tables)")
            connectors.add(connector_key(kc))
    return errors


def connector_key(kc: dict) -> tuple[str, str]:
    return kc["url"].rstrip("/"), kc["connector"]


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
    errors += _table_errors(spec.get("tables"), spec.get("target") is not None)
    errors += _component_errors(spec.get("components"), spec.get("tables"))
    detection = spec.get("detection") or {}
    if not isinstance(detection, dict) or detection.get("mode", "polling") not in ("polling", "event_driven"):
        errors.append("detection.mode: polling or event_driven")
    else:
        for key in ("interval_seconds", "fallback_polling_interval_seconds"):
            value = detection.get(key)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value <= 0):
                errors.append(f"detection.{key}: positive integer (seconds)")
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
    return errors + _auth_errors(cfg.get("auth"))


AUTH_ROLES = ("admin", "reporter")  # reporter: chỉ Reporting API (data plane); admin: mọi lệnh ghi


def _auth_errors(auth) -> list[str]:
    if auth is None:
        return []
    users = auth.get("users") if isinstance(auth, dict) else None
    if not isinstance(users, dict) or not users:
        return ["auth.users: mapping of name -> {role: admin|reporter, token: ${VAR}}"]
    errors = []
    for name, u in users.items():
        if not (isinstance(name, str) and PIPELINE_NAME_RE.match(name) and isinstance(u, dict)
                and set(u) == {"role", "token"} and u["role"] in AUTH_ROLES
                and isinstance(u["token"], str) and len(u["token"]) >= 16):
            errors.append(f"auth.users.{name}: {{role: admin|reporter, token: at least 16 characters}}")
    tokens = [u["token"] for u in users.values() if isinstance(u, dict) and isinstance(u.get("token"), str)]
    if len(set(tokens)) != len(tokens):
        errors.append("auth.users: each user needs a different token (the token identifies who approved)")
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
    specs, errors, owner, connector_owner = [], {}, {}, {}
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
        keys = [connector_key(c["kafka_connect"]) for c in spec.get("components") or [] if c.get("kafka_connect")] \
            if not problems else []
        if any(k in connector_owner for k in keys):
            # 2 pipeline cùng điều khiển 1 connector sẽ pause/resume ngược nhau liên tục -> dữ liệu lọt khi freeze.
            k = next(k for k in keys if k in connector_owner)
            problems = [f"components: Kafka Connect connector '{k[1]}' is already controlled by {connector_owner[k]} "
                        "— declare each connector in one pipeline only"]
        if problems:
            errors[f.name] = "; ".join(problems)
            continue
        owner[spec["name"]] = f.name
        connector_owner.update({k: f.name for k in keys})
        entries = table_entries(spec["tables"])
        # Phía sau chỉ dùng tên bảng nguồn (registry key, Gate API, Kafka); DDL trên đích dùng table_targets.
        specs.append({**spec, "tables": [s for s, _ in entries], "table_targets": dict(entries)})
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
            "table_targets": p.get("table_targets", {}),
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