"""
Trạng thái chạy thật của scheduler / Kafka consumer (in-memory, dùng chung
giữa các thread trong tiến trình API) — để sơ đồ tô-pô hiển thị đúng hành
vi thực tế thay vì luôn báo "active".
"""
import threading
import time
from datetime import datetime

_lock = threading.Lock()
_pipelines: dict[str, dict] = {}
_consumers: dict[str, dict] = {}


def _now() -> str:
    return datetime.now().isoformat()


def record_scan(pipeline: str, ok: bool, error: str | None = None) -> None:
    with _lock:
        st = _pipelines.setdefault(pipeline, {})
        st["last_scan_at"] = _now()
        st["last_scan_ok"] = ok
        st["last_error"] = error


def forget(pipeline: str) -> None:
    """Pipeline bị xoá/nạp lại: bỏ trạng thái quét cũ để UI không hiển thị số liệu cũ."""
    with _lock:
        _pipelines.pop(pipeline, None)


def record_consumer(bootstrap: str, state: str, error: str | None = None) -> None:
    """state: connecting | connected | disconnected"""
    with _lock:
        _consumers[bootstrap] = {"state": state, "error": error, "updated_at": _now()}


def get_pipeline(pipeline: str) -> dict:
    with _lock:
        return dict(_pipelines.get(pipeline, {}))


def get_consumer(bootstrap: str) -> dict:
    with _lock:
        return dict(_consumers.get(bootstrap, {}))


# Thành phần data plane (loader, Kafka Connect, Spark...) tự báo cáo qua Reporting API.
COMPONENT_STALE_SECONDS = 15
_components: dict[str, dict[str, dict]] = {}


def record_component(pipeline: str, name: str, report: dict) -> None:
    with _lock:
        _components.setdefault(pipeline, {})[name] = {**report, "name": name, "reported_at": time.time()}


def get_components(pipeline: str) -> list[dict]:
    """Báo cáo mới nhất của từng thành phần; im lặng quá lâu (trừ 'failed') -> 'stale'."""
    now = time.time()
    with _lock:
        items = [dict(c) for c in _components.get(pipeline, {}).values()]
    for c in items:
        c["age_seconds"] = round(now - c["reported_at"], 1)
        if c["age_seconds"] > COMPONENT_STALE_SECONDS and c.get("state") != "failed":
            c["state"] = "stale"
    return sorted(items, key=lambda c: c["name"])
