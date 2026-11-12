"""
Trạng thái chạy thật của scheduler / Kafka consumer (in-memory, dùng chung
giữa các thread trong tiến trình API) — để sơ đồ tô-pô hiển thị đúng hành
vi thực tế thay vì luôn báo "active".
"""
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

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


# Thành phần data plane (loader, Kafka Connect, Spark...) tự báo cáo qua Reporting API,
# hoặc do engine quan sát (app/components.py).
COMPONENT_STALE_SECONDS = 15
PERSIST_EVERY_SECONDS = 5  # ghi ra đĩa tối đa 1 lần / 5s; tắt đột ngột mất tối đa 5s báo cáo cuối
_components: dict[str, dict[str, dict]] = {}
_persist_path: Path | None = None
_persisted_at = 0.0
_write_lock = threading.Lock()


def persist_components_to(path) -> None:
    """Nạp báo cáo cũ (khởi động lại vẫn thấy trạng thái cuối, hiện 'stale') và ghi tiếp vào file này."""
    global _persist_path
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    with _lock:
        _persist_path = path
        for pipeline, comps in (data.items() if isinstance(data, dict) else []):
            if isinstance(comps, dict):
                _components.setdefault(pipeline, {}).update(
                    {n: c for n, c in comps.items() if isinstance(c, dict) and isinstance(c.get("reported_at"), (int, float))})


def _persist(now: float) -> None:
    global _persisted_at
    with _write_lock:
        if _persist_path is None or now - _persisted_at < PERSIST_EVERY_SECONDS:
            return
        _persisted_at = now
        with _lock:
            text = json.dumps(_components, ensure_ascii=False)
        tmp = _persist_path.with_name(_persist_path.name + ".tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, _persist_path)
        except OSError as e:  # Windows: file đang bị mở -> bỏ lượt này, lượt sau ghi lại
            print(f"[runtime_status] cannot save components: {e}")


def record_component(pipeline: str, name: str, report: dict) -> None:
    now = time.time()
    with _lock:
        _components.setdefault(pipeline, {})[name] = {**report, "name": name, "reported_at": now}
    _persist(now)


def get_components(pipeline: str, declared: list[dict] | None = None) -> list[dict]:
    """
    Báo cáo mới nhất của từng thành phần; im lặng quá lâu (trừ 'failed') -> 'stale'.
    declared = components: trong YAML pipeline; khai báo mà chưa từng báo cáo -> 'missing'.
    """
    now = time.time()
    with _lock:
        items = [dict(c) for c in _components.get(pipeline, {}).values()]
    for c in items:
        c["age_seconds"] = round(now - c["reported_at"], 1)
        if c["age_seconds"] > COMPONENT_STALE_SECONDS and c.get("state") != "failed":
            c["state"] = "stale"
    seen = {c["name"] for c in items}
    items += [{"name": d["name"], "role": d.get("role") or "", "state": "missing", "metrics": {},
               "message": "Declared in the pipeline YAML but has never reported", "age_seconds": None}
              for d in declared or [] if d["name"] not in seen]
    return sorted(items, key=lambda c: c["name"])
