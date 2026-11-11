import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.event_log import EventLog


def test_events_survive_restart():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "events.jsonl"
        before = EventLog(max_size=3)
        before.persist_to(f)
        for i in range(5):
            before.add_event("p", "t", f"ddl {i}", "changes_applied")

        after = EventLog(max_size=3)  # "khởi động lại"
        after.persist_to(f)
        assert [e["ddl"] for e in after.get_events()] == ["ddl 4", "ddl 3", "ddl 2"]
        assert after.add_event("p", "t", "next", "approved")["id"] == 6  # id không trùng lịch sử cũ

        with f.open("a", encoding="utf-8") as h:
            h.write("{half-written")  # tắt đột ngột giữa lúc ghi
        again = EventLog(max_size=3)
        again.persist_to(f)
        assert again.get_events()[0]["ddl"] == "next"
    print("[PASS] test_events_survive_restart")


if __name__ == "__main__":
    test_events_survive_restart()
    print("\nALL EVENT LOG TESTS PASSED!")
