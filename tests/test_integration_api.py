"""Gate API + Reporting API: hợp đồng giữa engine và mọi thành phần data plane."""
import os
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import HTTPException

import api.main as api
from app import runtime_status
from src.schema_evolution.core import SchemaRegistry
from src.schema_evolution.engines.base import ChangeSeverity, ChangeType, ColumnSchema, SchemaChange, TableSchema

PIPE = """
name: shop
source: {type: postgres, config: {host: localhost, dbname: shop}}
tables: [orders]
"""


def _status(fn, *args) -> int:
    try:
        fn(*args)
    except HTTPException as e:
        return e.status_code
    return 200


def test_gate_and_reporting():
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        try:
            Path("config/pipelines").mkdir(parents=True)
            # registry.dir tương đối được tính từ gốc project -> dùng đường dẫn tuyệt đối trong thư mục tạm
            Path("config/main.yaml").write_text(f"registry: {{dir: '{(Path(d) / 'reg').as_posix()}'}}\n", encoding="utf-8")
            Path("config/pipelines/shop.yaml").write_text(PIPE, encoding="utf-8")
            reg = SchemaRegistry(str(Path(d) / "reg"))
            schema = TableSchema("orders", [ColumnSchema("id", "bigint", False)])
            reg.save("shop/orders", schema)

            # Gate: open -> frozen (kèm thay đổi đang chờ) -> 404 cho thứ không được giám sát.
            g = api.get_gate("shop", "orders")
            assert g["state"] == "open" and g["schema_version"] == 1 and g["pending_changes"] == []
            reg.set_frozen("shop/orders", True)
            reg.save_draft("shop/orders", schema, [SchemaChange(
                "orders", ChangeType.DROP_COLUMN, ChangeSeverity.BREAKING, column_name="note")])
            g = api.get_gate("shop", "orders")
            assert g["state"] == "frozen" and g["pending_changes"] == [{"change_type": "drop_column", "column": "note"}]
            assert _status(api.get_gate, "nope", "orders") == 404
            assert _status(api.get_gate, "shop", "nope") == 404

            # RENAME đã duyệt: ánh xạ nối chuỗi (a->b rồi b->c => a->c, b->c) và giữ qua mọi lần save().
            reg.record_renames("shop/orders", {"qty": "quantity"})
            reg.record_renames("shop/orders", {"quantity": "amount"})
            reg.save("shop/orders", schema)
            assert api.get_gate("shop", "orders")["column_renames"] == {"qty": "amount", "quantity": "amount"}

            # Reporting: thành phần tự báo cáo, engine lưu nguyên chỉ số, không cần hiểu ý nghĩa.
            api.report_component("shop", "spark-job", {"state": "running", "role": "batch sink",
                                                       "metrics": {"rows_per_sec": 12.5, "lost_rows": 0}})
            comps = api.list_components("shop")
            assert comps[0]["name"] == "spark-job" and comps[0]["metrics"]["rows_per_sec"] == 12.5
            assert comps[0]["state"] == "running" and comps[0]["age_seconds"] < 5
            assert _status(api.report_component, "nope", "x", {"state": "running"}) == 404
            assert _status(api.report_component, "shop", "../x", {"state": "running"}) == 400
            assert _status(api.report_component, "shop", "x", {"metrics": {"a": [1]}}) == 422  # thiếu state, metric không phải scalar

            # Im lặng quá lâu -> stale (trừ failed).
            runtime_status._components["shop"]["spark-job"]["reported_at"] -= 60
            api.report_component("shop", "loader", {"state": "failed", "message": "boom"})
            runtime_status._components["shop"]["loader"]["reported_at"] -= 60
            states = {c["name"]: c["state"] for c in api.list_components("shop")}
            assert states == {"spark-job": "stale", "loader": "failed"}
        finally:
            os.chdir(cwd)
    print("[PASS] test_gate_and_reporting")


if __name__ == "__main__":
    test_gate_and_reporting()
    print("\nALL INTEGRATION API TESTS PASSED!")
