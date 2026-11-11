import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.schema_evolution.engines.base import ChangeSeverity, ChangeType, ColumnSchema, SchemaChange
from src.schema_evolution.notification import _describe, _message


def _chg(t, col, old=None, new=None):
    return SchemaChange("trades", t, ChangeSeverity.BREAKING, column_name=col, old_value=old, new_value=new)


def test_describe_html_safe():
    add = _describe(_chg(ChangeType.ADD_COLUMN, "is_buyer_maker", new=ColumnSchema("is_buyer_maker", "boolean", True)))
    assert add == "Thêm cột <code>is_buyer_maker</code> · boolean, NULL", add
    assert "\\" not in add  # bản Markdown cũ hiện "is\_buyer\_maker"

    narrow = _describe(_chg(ChangeType.NARROW_TYPE, "symbol",
                            ColumnSchema("symbol", "varchar", False, max_length=20),
                            ColumnSchema("symbol", "varchar", False, max_length=10)))
    assert narrow == "Đổi kiểu <code>symbol</code> · varchar(20) → varchar(10)"

    widen = _describe(_chg(ChangeType.WIDEN_TYPE, "price",
                           ColumnSchema("price", "numeric", False, precision=18, scale=8),
                           ColumnSchema("price", "numeric", False, precision=24, scale=8)))
    assert widen.endswith("numeric(18,8) → numeric(24,8)")

    rename = _describe(_chg(ChangeType.RENAME_COLUMN, "qty", new=ColumnSchema("quantity", "numeric", False)))
    assert rename == "Đổi tên cột <code>qty</code> → <code>quantity</code>"

    evil = _describe(_chg(ChangeType.DROP_COLUMN, "a<b>&c", old=ColumnSchema("x", "text", True)))
    assert "<code>a&lt;b&gt;&amp;c</code>" in evil  # tên lạ không phá cú pháp HTML của Telegram
    print("[PASS] test_describe_html_safe")


def test_message_layout():
    m = _message("🔴", "Tiêu đề", "trades", "market_trades", ["• dòng 1"])
    lines = m.split("\n")
    assert lines[0] == "🔴 <b>Tiêu đề</b>" and lines[1] == "<code>market_trades / trades</code>"
    assert "• dòng 1" in lines and lines[-1].startswith("<i>")
    print("[PASS] test_message_layout")


if __name__ == "__main__":
    test_describe_html_safe()
    test_message_layout()
    print("\nALL NOTIFICATION TESTS PASSED!")
