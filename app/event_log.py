import json
import threading
from collections import deque
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from app.secret_store import atomic_write

class EventLog:
    def __init__(self, max_size: int = 50):
        self._events = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._counter = 0
        self._path: Path | None = None

    def persist_to(self, path) -> None:
        """Ghi mọi sự kiện ra file JSONL và nạp lại lịch sử gần nhất (khởi động lại không mất timeline)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._path = path
            lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
            events = []
            for line in lines:
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue  # dòng ghi dở khi tiến trình bị tắt đột ngột
            self._events.clear()
            self._events.extendleft(events[-self._events.maxlen:])  # mới nhất đứng đầu, như appendleft
            self._counter = max((e.get("id", 0) for e in events), default=0)
            if len(lines) > 20000:
                # shortcut: chỉ giữ 2000 sự kiện gần nhất trong file; cần lưu lâu hơn thì đẩy sang DB/log hệ thống.
                path.write_text("".join(json.dumps(e) + "\n" for e in events[-2000:]), encoding="utf-8")

    def add_event(self, pipeline_name: str, table_name: str, ddl: str, status: str, severity: str = "non_breaking",
                  changes: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        with self._lock:
            self._counter += 1
            event = {
                "id": self._counter,
                "timestamp": datetime.now().isoformat(),
                "pipeline": pipeline_name,
                "pipeline_name": pipeline_name,
                "table": table_name,
                "table_name": table_name,
                "detail": ddl,
                "ddl": ddl,
                "status": status,
                "type": severity,
                "severity": severity,
                "changes": changes or [],
            }
            self._events.appendleft(event)
            if self._path is not None:
                try:
                    with self._path.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(event) + "\n")
                except OSError as e:
                    print(f"[EventLog] cannot persist event to {self._path}: {e}")  # không làm hỏng engine
            return event

    def get_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._events)[:limit]

    def delete(self, event_id: int) -> bool:
        """Xoá 1 sự kiện khỏi lịch sử (chỉ là nhật ký: không đổi freeze/baseline). False nếu không thấy."""
        with self._lock:
            kept = [e for e in self._events if e.get("id") != event_id]
            if len(kept) == len(self._events):
                return False
            self._events = deque(kept, maxlen=self._events.maxlen)
            self._rewrite_file(lambda e: e.get("id") != event_id)
            return True

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._rewrite_file(lambda e: False)

    def _rewrite_file(self, keep) -> None:
        """Gọi khi đang giữ lock. File chỉ nối thêm khi ghi, nên xoá = ghi lại phần còn giữ."""
        if self._path is None or not self._path.is_file():
            return
        kept = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            try:
                if keep(json.loads(line)):
                    kept.append(line + "\n")
            except ValueError:
                continue  # dòng ghi dở: bỏ luôn
        atomic_write(self._path, "".join(kept))

# Global singleton instance. 2000 = số sự kiện file JSONL giữ lại sau khi tỉa: dashboard thống kê trên toàn bộ.
event_logger = EventLog(max_size=2000)
