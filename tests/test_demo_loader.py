import base64
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from demo.loader import decode_decimal, parse_message
from src.schema_evolution.engines.base import ColumnSchema
from src.schema_evolution.engines.clickhouse import ClickHouseEngine


def _b64(n: int) -> str:
    return base64.b64encode(n.to_bytes((n.bit_length() + 8) // 8 or 1, "big", signed=True)).decode()


def test_decode_decimal():
    assert decode_decimal("CNVU36hA", 8) == Decimal("97123.45000000")  # giá trị thật từ spike phase 0
    assert decode_decimal(_b64(-1234), 2) == Decimal("-12.34")
    assert decode_decimal(_b64(0), 8) == 0
    print("[PASS] test_decode_decimal")


def _debezium(op, after, extra_fields=()):
    fields = [
        {"field": "trade_id", "type": "int64"},
        {"field": "price", "type": "bytes", "name": "org.apache.kafka.connect.data.Decimal",
         "parameters": {"scale": "8", "connect.decimal.precision": "18"}},
        {"field": "trade_time", "type": "string", "name": "io.debezium.time.ZonedTimestamp"},
        *extra_fields,
    ]
    schema = {"fields": [{"field": "before"}, {"field": "after", "fields": fields}]}
    return json.dumps({"schema": schema, "payload": {"op": op, "before": None, "after": after}}).encode()


def test_parse_message():
    after = {"trade_id": 1, "price": "CNVU36hA", "trade_time": "2026-11-10T08:34:03.777380Z"}
    row = parse_message(_debezium("c", after))
    assert row == {
        "trade_id": 1,
        "price": Decimal("97123.45000000"),
        "trade_time": datetime(2026, 11, 10, 8, 34, 3, 777380, tzinfo=timezone.utc),
    }
    # Cột mới (sau ADD COLUMN) xuất hiện trong row, NULL được giữ nguyên.
    row = parse_message(_debezium("c", {**after, "is_buyer_maker": None},
                                  [{"field": "is_buyer_maker", "type": "boolean", "optional": True}]))
    assert row["is_buyer_maker"] is None and "is_buyer_maker" in row
    assert parse_message(_debezium("d", None)) is None
    assert parse_message(None) is None
    print("[PASS] test_parse_message")


def test_clickhouse_varchar_is_string():
    render = ClickHouseEngine({})._render_type
    assert render(ColumnSchema("s", "varchar", False, max_length=20)) == "String"
    assert render(ColumnSchema("s", "varchar", True, max_length=20)) == "Nullable(String)"
    assert render(ColumnSchema("c", "char", False, max_length=3)) == "FixedString(3)"
    print("[PASS] test_clickhouse_varchar_is_string")


if __name__ == "__main__":
    test_decode_decimal()
    test_parse_message()
    test_clickhouse_varchar_is_string()
    print("\nALL DEMO LOADER TESTS PASSED!")
