import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.kafka_consumer import _schema_fingerprint


def _msg(after_fields, after):
    schema = {"fields": [{"field": "before"}, {"field": "after", "fields": after_fields}, {"field": "source"}]}
    return {"schema": schema, "payload": {"op": "c", "after": after}}


PRICE_18 = {"field": "price", "type": "bytes", "name": "org.apache.kafka.connect.data.Decimal",
            "parameters": {"scale": "8", "connect.decimal.precision": "18"}}
PRICE_24 = {**PRICE_18, "parameters": {"scale": "8", "connect.decimal.precision": "24"}}
ID = {"field": "trade_id", "type": "int64"}


def fp(msg):
    return _schema_fingerprint(msg, msg["payload"]["after"])


def test_same_structure_same_fingerprint():
    # Giá trị khác nhau, cấu trúc như nhau -> không crawl lại.
    assert fp(_msg([ID, PRICE_18], {"trade_id": 1, "price": "AQ=="})) == fp(_msg([ID, PRICE_18], {"trade_id": 2, "price": "Ag=="}))
    print("[PASS] test_same_structure_same_fingerprint")


def test_ddl_changes_fingerprint():
    base = fp(_msg([ID, PRICE_18], {}))
    added = fp(_msg([ID, PRICE_18, {"field": "is_buyer_maker", "type": "boolean", "optional": True}], {}))
    widened = fp(_msg([ID, PRICE_24], {}))
    assert len({base, added, widened}) == 3
    print("[PASS] test_ddl_changes_fingerprint")


def test_schemaless_falls_back_to_keys():
    a = {"payload": {"after": {"x": 1, "y": 2}}}
    b = {"payload": {"after": {"y": 9, "x": 8}}}
    c = {"payload": {"after": {"x": 1, "y": 2, "z": 3}}}
    assert _schema_fingerprint(a, a["payload"]["after"]) == _schema_fingerprint(b, b["payload"]["after"])
    assert _schema_fingerprint(a, a["payload"]["after"]) != _schema_fingerprint(c, c["payload"]["after"])
    assert _schema_fingerprint({}, None) is None
    print("[PASS] test_schemaless_falls_back_to_keys")


def test_shared_topic_prefix_routes_to_owning_pipeline():
    import json
    from types import SimpleNamespace
    from app.kafka_consumer import _topic_matches, route_message

    class Worker:
        def __init__(self, name, tables):
            self.spec, self.topic, self.notified = {"name": name, "tables": tables}, "market", []

        def matches(self, topic):
            return _topic_matches(topic, self.topic)

        def notify(self, table, fp):
            self.notified.append(table)

    trades, tickers = Worker("market_trades", ["trades"]), Worker("market_tickers", ["tickers"])
    msg = lambda table: SimpleNamespace(topic=f"market.public.{table}", value=json.dumps(
        {"payload": {"op": "c", "after": {"id": 1}, "source": {"table": table}}}).encode())
    route_message(msg("tickers"), [trades, tickers])   # trước đây: chỉ worker khớp đầu tiên (trades) nhận -> bỏ qua
    route_message(msg("trades"), [trades, tickers])
    assert trades.notified == ["trades"] and tickers.notified == ["tickers"]
    print("[PASS] test_shared_topic_prefix_routes_to_owning_pipeline")


def test_schema_qualified_tables():
    from app.kafka_consumer import _resolve_tables, _extract_raw_table
    spec = {"tables": ["trades", "sales.orders"]}
    raw = _extract_raw_table({"after": {}, "source": {"schema": "sales", "table": "orders"}}, None)
    assert raw == "sales.orders" and _resolve_tables(raw, spec) == ["sales.orders"]
    assert _resolve_tables("public.orders", spec) == []            # cùng tên, khác schema -> không phải bảng này
    assert _resolve_tables("public.trades", spec) == ["trades"]     # tên trơn = mọi schema (mặc định public)
    assert _resolve_tables('"sales"."orders"', spec) == ["sales.orders"]  # id trong DDL event
    print("[PASS] test_schema_qualified_tables")


def test_non_json_message_warns_once():
    import io
    from contextlib import redirect_stdout
    from types import SimpleNamespace
    from app.kafka_consumer import route_message

    class Worker:
        spec = {"tables": ["orders"]}
        def matches(self, topic): return True
        def notify(self, table, fp): raise AssertionError("must not notify on unreadable message")

    avro = SimpleNamespace(topic="shop.public.orders", value=bytes([0, 0, 0, 0, 7, 2, 4]))
    out = io.StringIO()
    with redirect_stdout(out):
        for _ in range(100):
            route_message(avro, [Worker()])  # không ném lỗi, không spam
        route_message(SimpleNamespace(topic="shop.public.orders", value=b'"just a string"'), [Worker()])
    assert out.getvalue().count("not supported") == 1 and "Schema Registry" in out.getvalue()
    print("[PASS] test_non_json_message_warns_once")


if __name__ == "__main__":
    test_non_json_message_warns_once()
    test_schema_qualified_tables()
    test_shared_topic_prefix_routes_to_owning_pipeline()
    test_same_structure_same_fingerprint()
    test_ddl_changes_fingerprint()
    test_schemaless_falls_back_to_keys()
    print("\nALL FINGERPRINT TESTS PASSED!")
