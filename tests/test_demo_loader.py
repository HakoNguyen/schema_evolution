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


def test_parse_unwrapped_mongo_document():
    # Debezium Mongo + ExtractNewDocumentState: payload là document, schema phẳng, ngày là Timestamp (ms).
    schema = {"type": "struct", "fields": [
        {"field": "_id", "type": "string"},
        {"field": "amount", "type": "double", "optional": True},
        {"field": "created_at", "type": "int64", "name": "org.apache.kafka.connect.data.Timestamp", "optional": True},
    ]}
    payload = {"_id": "ord-1", "amount": 12.5, "created_at": 1762850043777}
    row = parse_message(json.dumps({"schema": schema, "payload": payload}).encode())
    assert row == {"_id": "ord-1", "amount": 12.5,
                   "created_at": datetime(2025, 11, 11, 8, 34, 3, 777000, tzinfo=timezone.utc)}
    print("[PASS] test_parse_unwrapped_mongo_document")


def test_coerce():
    from demo.loader import coerce
    assert coerce("12.50", "Nullable(Float64)") == 12.5            # app Mongo lỗi ghi số thành chuỗi
    assert coerce("12.50", "Decimal(18, 8)") == Decimal("12.50")
    assert coerce("7", "Nullable(Int64)") == 7
    assert coerce(12.5, "Nullable(String)") == "12.5"              # sau khi duyệt đổi cột sang String
    assert coerce({"a": 1}, "String") == '{"a": 1}'
    assert coerce("BTCUSDT", "String") == "BTCUSDT"                # dữ liệu Postgres: không đổi gì
    assert coerce(Decimal("1.5"), "Decimal(18, 8)") == Decimal("1.5")
    assert coerce(None, "Nullable(Float64)") is None
    print("[PASS] test_coerce")


def test_clickhouse_varchar_is_string():
    render = ClickHouseEngine({})._render_type
    assert render(ColumnSchema("s", "varchar", False, max_length=20)) == "String"
    assert render(ColumnSchema("s", "varchar", True, max_length=20)) == "Nullable(String)"
    assert render(ColumnSchema("c", "char", False, max_length=3)) == "String"  # FixedString đếm byte, không đếm ký tự
    print("[PASS] test_clickhouse_varchar_is_string")


def test_bench_percentile():
    from demo.bench import pct, summarize
    v = [0.9, 1.1, 1.0, 1.3, 5.0, 1.2, 1.0, 0.8, 1.1, 1.0]
    assert pct(v, 50) == 1.0 and pct(v, 95) == 5.0 and pct(v, 100) == 5.0
    assert pct([2.0], 95) == 2.0
    assert summarize([])["n"] == 0
    print("[PASS] test_bench_percentile")


def test_apply_renames():
    from demo.loader import apply_renames
    row = {"trade_id": 1, "qty": 2}
    # Đích đã đổi qty -> quantity: message cũ ghi vào cột mới.
    assert apply_renames(row, {"qty": "quantity"}, {"trade_id", "quantity"}) == {"trade_id": 1, "quantity": 2}
    # Đích vẫn còn cột cũ (chưa áp dụng rename): giữ nguyên.
    assert apply_renames(row, {"qty": "quantity"}, {"trade_id", "qty"}) == row
    assert apply_renames(row, {}, {"trade_id"}) is row
    print("[PASS] test_apply_renames")


if __name__ == "__main__":
    test_apply_renames()
    test_decode_decimal()
    test_parse_message()
    test_parse_unwrapped_mongo_document()
    test_coerce()
    test_clickhouse_varchar_is_string()
    test_bench_percentile()
    print("\nALL DEMO LOADER TESTS PASSED!")
