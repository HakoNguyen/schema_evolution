"""
Trạng thái chạy thật của scheduler / Kafka consumer (in-memory, dùng chung
giữa các thread trong tiến trình API) — để sơ đồ tô-pô hiển thị đúng hành
vi thực tế thay vì luôn báo "active".
"""
import threading
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
