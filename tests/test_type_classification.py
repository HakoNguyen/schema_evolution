import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.schema_evolution.core import compare_schemas, _merge_schema
from src.schema_evolution.engines.base import TableSchema, ColumnSchema, ChangeType, ChangeSeverity


def _diff(old_col: ColumnSchema, new_col: ColumnSchema):
    changes = compare_schemas(TableSchema("t", [old_col]), TableSchema("t", [new_col]))
    return [(c.change_type, c.severity) for c in changes]


NARROW = [(ChangeType.NARROW_TYPE, ChangeSeverity.BREAKING)]
WIDEN = [(ChangeType.WIDEN_TYPE, ChangeSeverity.NON_BREAKING)]


def test_varchar_length():
    v = lambda n: ColumnSchema("s", "varchar", True, max_length=n)
    assert _diff(v(None), v(10)) == NARROW, "unbounded -> varchar(10) phải là breaking"
    assert _diff(v(10), v(None)) == WIDEN
    assert _diff(v(50), v(100)) == WIDEN
    assert _diff(v(100), v(50)) == NARROW
    print("[PASS] test_varchar_length")


def test_numeric_precision_scale():
    n = lambda p, s: ColumnSchema("p", "numeric", True, precision=p, scale=s)
    assert _diff(n(10, 2), n(5, 0)) == NARROW, "decimal(10,2)->decimal(5,0) trước đây không bị phát hiện"
    assert _diff(n(10, 2), n(12, 2)) == WIDEN
    assert _diff(n(10, 2), n(12, 4)) == WIDEN
    assert _diff(n(10, 2), n(10, 4)) == NARROW, "phần nguyên 8 -> 6 chữ số"
    assert _diff(n(10, 4), n(10, 2)) == NARROW, "mất chữ số thập phân"
    assert _diff(n(None, None), n(10, 2)) == NARROW
    assert _diff(n(10, 2), n(None, None)) == WIDEN
    assert _diff(n(10, 2), n(10, 2)) == []
    print("[PASS] test_numeric_precision_scale")


def test_merge_keeps_widened_precision():
    old = TableSchema("t", [ColumnSchema("p", "numeric", True, precision=10, scale=2)])
    new = TableSchema("t", [ColumnSchema("p", "numeric", True, precision=12, scale=2)])
    merged = _merge_schema(old, compare_schemas(old, new))
    assert (merged.columns[0].precision, merged.columns[0].scale) == (12, 2)
    print("[PASS] test_merge_keeps_widened_precision")


def test_target_types_are_lossless():
    from src.schema_evolution.engines.clickhouse import ClickHouseEngine
    from src.schema_evolution.engines.mysql import MySQLEngine
    ch, my = ClickHouseEngine({})._render_type, MySQLEngine({})._render_type
    assert ch(ColumnSchema("t", "timestamp", False)) == "DateTime64(6)"
    assert ch(ColumnSchema("t", "timestamptz", True)) == "Nullable(DateTime64(6, 'UTC'))"
    assert ch(ColumnSchema("n", "numeric", True)) == "Nullable(Decimal(76, 38))"   # trước đây Float64
    assert ch(ColumnSchema("n", "numeric", False, precision=18, scale=8)) == "Decimal(18,8)"
    assert my(ColumnSchema("t", "timestamptz", False)) == "DATETIME(6)"
    assert my(ColumnSchema("n", "numeric", False)) == "DECIMAL(65,30)"              # trước đây DECIMAL = (10,0)
    assert my(ColumnSchema("n", "numeric", False, precision=10, scale=2)) == "DECIMAL(10,2)"
    print("[PASS] test_target_types_are_lossless")


def test_source_quirks_found_on_live_dbs():
    from src.schema_evolution.engines.mysql import MySQLEngine
    from src.schema_evolution.engines.mongo import _merge_types
    from src.schema_evolution.engines.base import render_portable_default
    norm = MySQLEngine({})._normalize_type
    assert norm("int", "int unsigned") == "bigint"          # 4294967295 không còn thành -1
    assert norm("bigint", "bigint unsigned") == "numeric"
    assert norm("tinyint", "tinyint(1)") == "boolean" and norm("mediumint", "mediumint") == "int"
    assert norm("double", "double unsigned") == "double"    # không bị ép numeric(20,0) (cắt 19.99 -> 20)
    full = MySQLEngine({})._render_full_column_def
    assert full(ColumnSchema("t", "timestamp", False, default="now()")).endswith("DEFAULT CURRENT_TIMESTAMP(6)")  # MySQL lỗi 1067 nếu thiếu (6)
    assert render_portable_default("CURRENT_TIMESTAMP(6)", now_sql="now()") == "now()"
    assert _merge_types({"int", "bigint"}) == "bigint" and _merge_types({"int", "double"}) == "double"
    assert _merge_types({"int", "text"}) == "json"
    from src.schema_evolution.engines.clickhouse import ClickHouseEngine
    assert ClickHouseEngine({})._render_type(ColumnSchema("d", "date", False)) == "Date32"
    print("[PASS] test_source_quirks_found_on_live_dbs")


if __name__ == "__main__":
    test_source_quirks_found_on_live_dbs()
    test_target_types_are_lossless()
    test_varchar_length()
    test_numeric_precision_scale()
    test_merge_keeps_widened_precision()
    print("\nALL TYPE CLASSIFICATION TESTS PASSED!")
