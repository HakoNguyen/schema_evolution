"""Evolution Policy (mức tương thích backward/forward/full/none) và thay đổi quan hệ (khoá chính, khoá ngoại)."""
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.scheduler import validate_pipeline_spec
from src.schema_evolution.core import (
    SchemaRegistry, apply_compatibility_policy, approve_change_and_sync, change_compatibility,
    compare_schemas, run_evolution_check,
)
from src.schema_evolution.engines.base import (
    ChangeSeverity, ChangeType, ColumnSchema, ForeignKeySchema, TableSchema,
)
from src.schema_evolution.engines.clickhouse import ClickHouseEngine


class FakeSource:
    def __init__(self, schema):
        self.schema = schema

    def crawl_metadata(self, table_name):
        return self.schema


class RecordingClickHouse(ClickHouseEngine):  # sinh DDL thật, chỉ ghi lại thay vì chạy
    def __init__(self):
        super().__init__({})
        self.ddl = []

    def _current_type(self, table, column):
        return None

    def execute_ddl(self, ddl):
        self.ddl.append(ddl)


COLS = [
    ColumnSchema("trade_id", "bigint", False),
    ColumnSchema("symbol", "varchar", False, max_length=20),
    ColumnSchema("price", "numeric", False, precision=18, scale=8),
]
FK = ForeignKeySchema("fk_trades_symbol", "symbol", "tickers", "symbol", "NO ACTION", "NO ACTION")


def _t(cols=COLS, pk=("trade_id",), fks=()):
    return TableSchema("trades", list(cols), list(pk), list(fks))


def _types(old, new):
    return [c.change_type for c in compare_schemas(old, new)]


def test_relationship_changes_detected_as_breaking():
    cases = {
        ChangeType.ADD_FOREIGN_KEY: (_t(), _t(fks=[FK])),
        ChangeType.DROP_FOREIGN_KEY: (_t(fks=[FK]), _t()),
        ChangeType.CHANGE_FOREIGN_KEY_TARGET: (
            _t(fks=[FK]), _t(fks=[ForeignKeySchema("fk_trades_symbol", "symbol", "coins", "symbol", "NO ACTION", "NO ACTION")])),
        ChangeType.CHANGE_FOREIGN_KEY_ACTION: (
            _t(fks=[FK]), _t(fks=[ForeignKeySchema("fk_trades_symbol", "symbol", "tickers", "symbol", "CASCADE", "NO ACTION")])),
        ChangeType.ADD_PRIMARY_KEY: (_t(pk=()), _t()),
        ChangeType.DROP_PRIMARY_KEY: (_t(), _t(pk=())),
        ChangeType.CHANGE_PRIMARY_KEY: (_t(), _t(pk=("symbol", "trade_id"))),
    }
    for expected, (old, new) in cases.items():
        changes = compare_schemas(old, new)
        assert [c.change_type for c in changes] == [expected], (expected, changes)
        want = ChangeSeverity.NON_BREAKING if expected == ChangeType.DROP_FOREIGN_KEY else ChangeSeverity.BREAKING
        assert changes[0].severity == want, (expected, changes[0].severity)
    print("[PASS] test_relationship_changes_detected_as_breaking")


def test_compatibility_matrix():
    nullable_col = ColumnSchema("note", "text", True)
    required_col = ColumnSchema("fee", "numeric", False, precision=18, scale=8)
    expected = {
        "add nullable column": (_t(), _t(COLS + [nullable_col]), (True, True)),
        "add NOT NULL column": (_t(), _t(COLS + [required_col]), (False, True)),
        "drop nullable column": (_t(COLS + [nullable_col]), _t(), (True, True)),
        "drop NOT NULL column": (_t(COLS + [required_col]), _t(), (True, False)),
        "widen": (_t(), _t(COLS[:2] + [ColumnSchema("price", "numeric", False, precision=24, scale=8)]), (True, False)),
        "narrow": (_t(), _t([COLS[0], ColumnSchema("symbol", "varchar", False, max_length=10), COLS[2]]), (False, True)),
        "add FK": (_t(), _t(fks=[FK]), (False, True)),
        "change PK": (_t(), _t(pk=("symbol", "trade_id")), (False, False)),
    }
    for name, (old, new, flags) in expected.items():
        changes = compare_schemas(old, new)
        assert len(changes) == 1, (name, changes)
        assert change_compatibility(changes[0]) == flags, (name, change_compatibility(changes[0]))
    print("[PASS] test_compatibility_matrix")


def test_policy_only_tightens():
    widen = compare_schemas(_t(), _t(COLS[:2] + [ColumnSchema("price", "numeric", False, precision=24, scale=8)]))
    add = compare_schemas(_t(), _t(COLS + [ColumnSchema("note", "text", True)]))
    drop = compare_schemas(_t(COLS + [ColumnSchema("note", "text", True)]), _t())

    sev = lambda changes, mode: apply_compatibility_policy(changes, mode)[0].severity
    # backward (mặc định) = hành vi cũ: nới kiểu tự đồng bộ
    assert sev(widen, "backward") == ChangeSeverity.NON_BREAKING
    assert sev(widen, "none") == ChangeSeverity.NON_BREAKING
    # forward/full: consumer cũ không đọc được giá trị lớn hơn -> chờ duyệt
    assert sev(widen, "forward") == ChangeSeverity.BREAKING
    assert sev(widen, "full") == ChangeSeverity.BREAKING
    # thêm cột nullable tương thích cả hai chiều -> mọi mức đều tự đồng bộ
    for mode in ("backward", "forward", "full", "none"):
        assert sev(add, mode) == ChangeSeverity.NON_BREAKING, mode
    # DROP tương thích backward, nhưng engine KHÔNG BAO GIỜ tự xoá cột ở đích, ở mức nào cũng vậy
    for mode in ("backward", "forward", "full", "none"):
        assert sev(drop, mode) == ChangeSeverity.BREAKING, mode
    print("[PASS] test_policy_only_tightens")


def test_forward_pipeline_freezes_widen_end_to_end():
    with tempfile.TemporaryDirectory() as d:
        wide = _t(COLS[:2] + [ColumnSchema("price", "numeric", False, precision=24, scale=8)])
        for mode, status in (("backward", "changes_applied"), ("forward", "breaking_detected")):
            reg, key, src = SchemaRegistry(f"{d}/{mode}"), f"{mode}/trades", FakeSource(_t())
            run_evolution_check(src, None, "trades", reg, registry_key=key, compatibility=mode)
            src.schema = wide
            r = run_evolution_check(src, None, "trades", reg, registry_key=key, compatibility=mode)
            assert r["status"] == status, (mode, r)
            if mode == "forward":
                pending = reg.load_draft(key)["breaking_changes"][0]
                assert pending["change_type"] == "widen_type"
                assert (pending["backward_compatible"], pending["forward_compatible"]) == (True, False)
    print("[PASS] test_forward_pipeline_freezes_widen_end_to_end")


def test_add_fk_freezes_then_approves_on_clickhouse():
    with tempfile.TemporaryDirectory() as d:
        reg, key, tgt = SchemaRegistry(d), "p/trades", RecordingClickHouse()
        src = FakeSource(_t())
        run_evolution_check(src, tgt, "trades", reg, registry_key=key)
        src.schema = _t(fks=[FK])
        assert run_evolution_check(src, tgt, "trades", reg, registry_key=key)["status"] == "breaking_detected"
        assert reg.is_frozen(key)
        # Trước đây ClickHouse raise ValueError -> Approve thất bại mãi, bảng frozen vĩnh viễn.
        assert approve_change_and_sync(tgt, "trades", reg, registry_key=key)["status"] == "approved"
        assert not reg.is_frozen(key) and reg.load(key).foreign_keys == [FK]
        assert all(s.startswith("--") for s in tgt.ddl), tgt.ddl
    print("[PASS] test_add_fk_freezes_then_approves_on_clickhouse")


def test_config_validates_compatibility():
    spec = {"name": "p", "source": {"type": "postgres", "config": {"host": "h", "port": 1, "dbname": "d"}},
            "tables": ["trades"]}
    assert validate_pipeline_spec(spec) == []
    assert validate_pipeline_spec({**spec, "compatibility": "full"}) == []
    assert any(e.startswith("compatibility") for e in validate_pipeline_spec({**spec, "compatibility": "strict"}))
    print("[PASS] test_config_validates_compatibility")


if __name__ == "__main__":
    test_relationship_changes_detected_as_breaking()
    test_compatibility_matrix()
    test_policy_only_tightens()
    test_forward_pipeline_freezes_widen_end_to_end()
    test_add_fk_freezes_then_approves_on_clickhouse()
    test_config_validates_compatibility()
    print("\nALL COMPATIBILITY TESTS PASSED!")
