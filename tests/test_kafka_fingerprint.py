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


if __name__ == "__main__":
    test_shared_topic_prefix_routes_to_owning_pipeline()
    test_same_structure_same_fingerprint()
    test_ddl_changes_fingerprint()
    test_schemaless_falls_back_to_keys()
    print("\nALL FINGERPRINT TESTS PASSED!")
