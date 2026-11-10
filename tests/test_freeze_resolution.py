import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.schema_evolution.core import SchemaRegistry, run_evolution_check
from src.schema_evolution.engines.base import ColumnSchema, TableSchema


class FakeSource:
    def __init__(self, schema):
        self.schema = schema

    def crawl_metadata(self, table_name):
        return self.schema


def _schema(symbol_len):
    return TableSchema("trades", [
        ColumnSchema("trade_id", "bigint", False),
        ColumnSchema("symbol", "varchar", False, max_length=symbol_len),
    ], primary_key=["trade_id"])


def test_freeze_then_rollback_at_source_unfreezes():
    with tempfile.TemporaryDirectory() as d:
        reg = SchemaRegistry(d)
        key = "p/trades"
        src = FakeSource(_schema(20))
        assert run_evolution_check(src, None, "trades", reg, registry_key=key)["status"] == "initialized"

        src.schema = _schema(10)  # thu hẹp -> breaking
        assert run_evolution_check(src, None, "trades", reg, registry_key=key)["status"] == "breaking_detected"
        assert reg.is_frozen(key) and reg.load_draft(key) is not None

        # Vẫn lệch baseline -> giữ freeze.
        assert run_evolution_check(src, None, "trades", reg, registry_key=key)["status"] == "frozen"

        src.schema = _schema(20)  # dev rollback
        assert run_evolution_check(src, None, "trades", reg, registry_key=key)["status"] == "resolved_at_source"
        assert not reg.is_frozen(key) and reg.load_draft(key) is None
        assert run_evolution_check(src, None, "trades", reg, registry_key=key)["status"] == "no_change"
    print("[PASS] test_freeze_then_rollback_at_source_unfreezes")


if __name__ == "__main__":
    test_freeze_then_rollback_at_source_unfreezes()
    print("\nALL FREEZE RESOLUTION TESTS PASSED!")
