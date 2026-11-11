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


def test_ddl_targets_mapped_table_name():
    from src.schema_evolution.core import approve_change_and_sync
    from src.schema_evolution.engines.clickhouse import ClickHouseEngine

    class FakeTarget(ClickHouseEngine):  # sinh DDL thật, chỉ ghi lại thay vì chạy
        def __init__(self):
            super().__init__({})
            self.ddl = []

        def execute_ddl(self, ddl):
            self.ddl.append(ddl)

    with tempfile.TemporaryDirectory() as d:
        reg, tgt, key = SchemaRegistry(d), FakeTarget(), "p/sales.trades"
        base = _schema(20)
        src = FakeSource(base)
        run_evolution_check(src, tgt, "sales.trades", reg, registry_key=key, target_table="trades_raw")
        src.schema = TableSchema("sales.trades", base.columns + [ColumnSchema("note", "text", True)], ["trade_id"])
        assert run_evolution_check(src, tgt, "sales.trades", reg, registry_key=key,
                                   target_table="trades_raw")["status"] == "changes_applied"
        assert tgt.ddl == ["ALTER TABLE trades_raw ADD COLUMN `note` Nullable(String)"], tgt.ddl

        src.schema = TableSchema("sales.trades", [c for c in src.schema.columns if c.name != "note"], ["trade_id"])
        run_evolution_check(src, tgt, "sales.trades", reg, registry_key=key, target_table="trades_raw")
        assert reg.is_frozen(key)  # DROP = breaking
        assert approve_change_and_sync(tgt, "sales.trades", reg, registry_key=key,
                                       target_table="trades_raw")["status"] == "approved"
        assert tgt.ddl[-1] == "ALTER TABLE trades_raw DROP COLUMN `note`", tgt.ddl
    print("[PASS] test_ddl_targets_mapped_table_name")


def test_failed_auto_ddl_freezes_instead_of_reporting_success():
    class BrokenTarget:
        def generate_ddl(self, changes):
            return ["ALTER bad syntax"] * len(changes)

        def execute_ddl(self, ddl):
            raise RuntimeError("Syntax error")

    with tempfile.TemporaryDirectory() as d:
        reg, key = SchemaRegistry(d), "p/trades"
        src = FakeSource(_schema(20))
        run_evolution_check(src, BrokenTarget(), "trades", reg, registry_key=key)
        src.schema = TableSchema("trades", _schema(20).columns + [ColumnSchema("unit-price", "text", True)], ["trade_id"])
        r = run_evolution_check(src, BrokenTarget(), "trades", reg, registry_key=key)
        assert r["status"] == "breaking_detected" and reg.is_frozen(key), r  # trước đây: changes_applied, version tăng mãi
        assert reg.get_version(key) == 1
    print("[PASS] test_failed_auto_ddl_freezes_instead_of_reporting_success")


def test_schemaless_missing_field_is_not_a_drop():
    class MongoLike(FakeSource):
        schemaless = True

    with tempfile.TemporaryDirectory() as d:
        reg, key = SchemaRegistry(d), "p/events"
        cols = [ColumnSchema("_id", "text", False), ColumnSchema("coupon", "text", True)]
        src = MongoLike(TableSchema("events", list(cols), ["_id"]))
        run_evolution_check(src, None, "events", reg, registry_key=key)
        src.schema = TableSchema("events", [cols[0], ColumnSchema("promo", "text", True)], ["_id"])  # mẫu mới thiếu coupon
        r = run_evolution_check(src, None, "events", reg, registry_key=key)
        assert r["status"] == "changes_applied" and not reg.is_frozen(key), r  # chỉ ADD promo, không DROP/RENAME giả
        assert {c.name for c in reg.load(key).columns} == {"_id", "coupon", "promo"}

        src.schema = TableSchema("events", [cols[0], ColumnSchema("views", "bigint", True)], ["_id"])
        run_evolution_check(src, None, "events", reg, registry_key=key)          # views lớn dần -> bigint
        src.schema = TableSchema("events", [cols[0], ColumnSchema("views", "int", True)], ["_id"])
        r = run_evolution_check(src, None, "events", reg, registry_key=key)      # mẫu mới toàn số nhỏ
        assert r["status"] == "no_change" and not reg.is_frozen(key), r         # không phải "thu hẹp"
    print("[PASS] test_schemaless_missing_field_is_not_a_drop")


if __name__ == "__main__":
    test_failed_auto_ddl_freezes_instead_of_reporting_success()
    test_schemaless_missing_field_is_not_a_drop()
    test_ddl_targets_mapped_table_name()
    test_freeze_then_rollback_at_source_unfreezes()
    print("\nALL FREEZE RESOLUTION TESTS PASSED!")
