import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.schema_evolution.core import compare_schemas, _merge_schema, _serialize_change
from src.schema_evolution.engines.base import TableSchema, ColumnSchema, ChangeType, ChangeSeverity
from src.schema_evolution.engines.postgres import PostgresEngine
from src.schema_evolution.engines.mysql import MySQLEngine
from src.schema_evolution.engines.clickhouse import ClickHouseEngine


def test_rename_column_heuristic_detection():
    old_schema = TableSchema(
        table_name="customers",
        columns=[
            ColumnSchema("id", "int", False),
            ColumnSchema("address", "varchar", True, max_length=255),
            ColumnSchema("created_at", "timestamp", True),
        ]
    )

    # Dev renamed 'address' to 'shipping_address' (same type & nullability)
    new_schema = TableSchema(
        table_name="customers",
        columns=[
            ColumnSchema("id", "int", False),
            ColumnSchema("shipping_address", "varchar", True, max_length=255),
            ColumnSchema("created_at", "timestamp", True),
        ]
    )

    changes = compare_schemas(old_schema, new_schema)
    assert len(changes) == 1, f"Expected 1 change, got {len(changes)}"
    change = changes[0]
    assert change.change_type == ChangeType.RENAME_COLUMN
    assert change.severity == ChangeSeverity.BREAKING
    assert change.column_name == "address"
    assert change.new_value.name == "shipping_address"
    print("[PASS] test_rename_column_heuristic_detection passed.")


def test_unmatched_drop_and_add():
    old_schema = TableSchema(
        table_name="users",
        columns=[
            ColumnSchema("id", "int", False),
            ColumnSchema("old_notes", "text", True),
        ]
    )

    # Dev deleted 'old_notes' (text) and added 'age' (int) -> types don't match
    new_schema = TableSchema(
        table_name="users",
        columns=[
            ColumnSchema("id", "int", False),
            ColumnSchema("age", "int", True),
        ]
    )

    changes = compare_schemas(old_schema, new_schema)
    assert len(changes) == 2, f"Expected 2 separate changes (DROP+ADD), got {len(changes)}"
    change_types = {c.change_type for c in changes}
    assert ChangeType.DROP_COLUMN in change_types
    assert ChangeType.ADD_COLUMN in change_types
    print("[PASS] test_unmatched_drop_and_add passed.")


def test_ddl_generation_for_rename():
    old_schema = TableSchema("orders", [ColumnSchema("status_code", "varchar", True)])
    new_schema = TableSchema("orders", [ColumnSchema("order_status", "varchar", True)])

    changes = compare_schemas(old_schema, new_schema)

    pg_engine = PostgresEngine({})
    mysql_engine = MySQLEngine({})
    ch_engine = ClickHouseEngine({"host": "lh", "port": 8123, "database": "db"})

    pg_ddl = pg_engine.generate_ddl(changes)
    mysql_ddl = mysql_engine.generate_ddl(changes)
    ch_ddl = ch_engine.generate_ddl(changes)

    expected_sql = "ALTER TABLE orders RENAME COLUMN status_code TO order_status"

    assert pg_ddl[0] == expected_sql, f"PG DDL mismatch: {pg_ddl[0]}"
    assert mysql_ddl[0] == expected_sql, f"MySQL DDL mismatch: {mysql_ddl[0]}"
    assert ch_ddl[0] == expected_sql, f"ClickHouse DDL mismatch: {ch_ddl[0]}"
    print("[PASS] test_ddl_generation_for_rename passed.")


def test_merge_schema_with_rename():
    old_schema = TableSchema("products", [
        ColumnSchema("id", "int", False),
        ColumnSchema("name", "varchar", True)
    ])
    new_schema = TableSchema("products", [
        ColumnSchema("id", "int", False),
        ColumnSchema("title", "varchar", True)
    ])

    changes = compare_schemas(old_schema, new_schema)
    merged = _merge_schema(old_schema, changes)

    col_names = [c.name for c in merged.columns]
    assert "title" in col_names
    assert "name" not in col_names
    print("[PASS] test_merge_schema_with_rename passed.")


def test_serialize_rename_change():
    old_schema = TableSchema("t", [ColumnSchema("col_a", "int", True)])
    new_schema = TableSchema("t", [ColumnSchema("col_b", "int", True)])

    changes = compare_schemas(old_schema, new_schema)
    serialized = _serialize_change(changes[0])

    assert serialized["change_type"] == "rename_column"
    assert serialized["severity"] == "breaking"
    assert serialized["column_name"] == "col_a"
    assert serialized["old_value"] == "col_a"
    assert serialized["new_value"] == "col_b"
    print("[PASS] test_serialize_rename_change passed.")


if __name__ == "__main__":
    test_rename_column_heuristic_detection()
    test_unmatched_drop_and_add()
    test_ddl_generation_for_rename()
    test_merge_schema_with_rename()
    test_serialize_rename_change()
    print("\nALL RENAME HEURISTIC TESTS PASSED SUCCESSFULLY!")
