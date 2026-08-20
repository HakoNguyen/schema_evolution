import threading
from collections import deque
from datetime import datetime
from typing import Dict, Any, List

class EventLog:
    def __init__(self, max_size: int = 50):
        self._events = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._counter = 0

    def add_event(self, pipeline_name: str, table_name: str, ddl: str, status: str, severity: str = "non_breaking") -> Dict[str, Any]:
        with self._lock:
            self._counter += 1
            event = {
                "id": self._counter,
                "timestamp": datetime.now().isoformat(),
                "pipeline_name": pipeline_name,
                "table_name": table_name,
                "ddl": ddl,
                "status": status,
                "severity": severity,
            }
            self._events.appendleft(event)
            return event

    def get_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._events)[:limit]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

# Global singleton instance
event_logger = EventLog()
