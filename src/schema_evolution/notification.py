from datetime import datetime

from src.schema_evolution.engines.base import SchemaChange, ChangeType
import requests


def _escape_markdown(text: str) -> str:
    # Telegram Markdown (bản legacy) coi _ * ` [ là ký tự định dạng —
    # repr() của ColumnSchema/list chứa rất nhiều dấu _ (data_type,
    # max_length...) khiến Telegram không khớp được cặp mở/đóng và trả
    # lỗi "can't parse entities". Escape trước khi nhét vào message.
    for ch in ("\\", "_", "*", "`", "["):
        text = text.replace(ch, "\\" + ch)
    return text


def _format_col_type(col) -> str:
    if col is None:
        return "?"
    type_str = col.data_type + (f"({col.max_length})" if col.max_length else "")
    return _escape_markdown(type_str)


# Icon riêng theo từng loại thay đổi — giúp lướt nhanh trên điện thoại
# mà không cần đọc hết chữ.
CHANGE_TYPE_ICONS = {
    "add_column": "➕",
    "drop_column": "➖",
    "rename_column": "✏️",
    "widen_type": "📏",
    "narrow_type": "📏",
    "change_type_incompatible": "🔁",
    "nullable_to_not_null": "🔒",
    "not_null_to_nullable": "🔓",
    "add_primary_key": "🔑",
    "drop_primary_key": "🔑",
    "change_primary_key": "🔑",
    "add_foreign_key": "🔗",
    "drop_foreign_key": "🔗",
    "change_fk_target": "🔗",
    "change_fk_action": "🔗",
}


def _format_change_detail(change: SchemaChange) -> str:
    """1 dòng mô tả thay đổi, kèm icon + chi tiết kiểu dữ liệu nếu có,
    dùng chung cho cả breaking lẫn auto-sync để nhất quán."""
    icon = CHANGE_TYPE_ICONS.get(change.change_type.value, "•")
    target = _escape_markdown(change.column_name or change.constraint_name or "?")

    if change.change_type == ChangeType.ADD_COLUMN:
        col = change.new_value
        null_str = "NULL" if (col and col.nullable) else "NOT NULL"
        return f"{icon} Thêm cột `{target}` — {_format_col_type(col)}, {null_str}"

    if change.change_type == ChangeType.DROP_COLUMN:
        return f"{icon} Xoá cột `{target}` (kiểu cũ: {_format_col_type(change.old_value)})"

    if change.change_type in (ChangeType.WIDEN_TYPE, ChangeType.NARROW_TYPE, ChangeType.CHANGE_TYPE_INCOMPATIBLE):
        return f"{icon} Đổi kiểu `{target}`: {_format_col_type(change.old_value)} → {_format_col_type(change.new_value)}"

    if change.change_type == ChangeType.NOT_NULL_TO_NULLABLE:
        return f"{icon} Cho phép NULL ở cột `{target}`"

    if change.change_type == ChangeType.NULLABLE_TO_NOT_NULL:
        return f"{icon} Bắt buộc NOT NULL ở cột `{target}`"

    if change.change_type == ChangeType.DROP_FOREIGN_KEY:
        return f"{icon} Xoá khoá ngoại `{target}`"

    if change.change_type == ChangeType.ADD_FOREIGN_KEY:
        return f"{icon} Thêm khoá ngoại mới tại `{target}`"

    if change.change_type in (ChangeType.ADD_PRIMARY_KEY, ChangeType.DROP_PRIMARY_KEY, ChangeType.CHANGE_PRIMARY_KEY):
        old_str = _escape_markdown(str(change.old_value))
        new_str = _escape_markdown(str(change.new_value))
        return f"{icon} Đổi Primary Key: {old_str} → {new_str}"

    # Fallback cho các loại chưa liệt kê riêng ở trên
    return f"{icon} `{change.change_type.value}` tại `{target}`"


def _build_header(icon: str, title: str, table_name: str, pair_name: str | None, severity_label: str) -> list[str]:
    """Khối thông tin đầu message — dùng chung cho breaking lẫn auto-sync."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"{icon} *{title}*", ""]
    if pair_name:
        lines.append(f"📦 Pair: `{pair_name}`")
    lines.append(f"📋 Bảng: `{table_name}`")
    lines.append(f"⚙️ Mức độ: *{severity_label}*")
    lines.append(f"🕒 Thời gian: `{now}`")
    return lines


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, max_retries: int = 2):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.max_retries = max_retries
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, text: str) -> bool:
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id, 
            "text": text, 
            "parse_mode": "Markdown",
        }
        
        for attempt in range(1, self.max_retries + 2):
            try: 
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200: 
                    return True
                print(
                    f"[TelegramNotifier] Lần thử {attempt}: "
                    f"HTTP {resp.status_code} - {resp.text}"
                )
            except requests.RequestException as e: 
                 print(f"[TelegramNotifier] Lần thử {attempt}: lỗi mạng - {e}")
 
        print(f"[TelegramNotifier] Gửi thất bại sau {self.max_retries + 1} lần thử.")
        return False

    def notify_breaking_changes(
        self,
        table_name: str,
        changes: list[SchemaChange],
        pair_name: str | None = None,
    ) -> bool:
        count = len(changes)
        lines = _build_header("🔴", "SCHEMA DRIFT", table_name, pair_name, "BREAKING")
        lines.append("")
        lines.append(f"Luồng đồng bộ đã *tạm dừng*, chờ phê duyệt ({count} thay đổi):")
        lines.append("")
        for change in changes:
            lines.append(_format_change_detail(change))
        lines.append("")
        lines.append("👉 Vào Streamlit UI để xem chi tiết và phê duyệt.")
        return self.send_message("\n".join(lines))

    def notify_auto_sync_applied(
        self,
        table_name: str,
        changes: list[SchemaChange],
        pair_name: str | None = None,
    ) -> bool:
        if not changes:
            return True
        count = len(changes)
        lines = _build_header("🟢", "AUTO-SYNC", table_name, pair_name, "NON-BREAKING")
        lines.append("")
        lines.append(f"Đã tự động đồng bộ {count} thay đổi:")
        lines.append("")
        for change in changes:
            lines.append(_format_change_detail(change))
        return self.send_message("\n".join(lines))

    def notify_change_reviewed(
        self,
        table_name: str,
        approved: bool,
        pair_name: str | None = None,
    ) -> bool:
        """Gửi khi kỹ sư bấm Approve/Reject (qua Streamlit UI hoặc unfreeze_cli.py)."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        icon = "✅" if approved else "❌"
        title = "ĐÃ PHÊ DUYỆT" if approved else "ĐÃ TỪ CHỐI"

        lines = [f"{icon} *{title}*", ""]
        if pair_name:
            lines.append(f"📦 Pair: `{pair_name}`")
        lines.append(f"📋 Bảng: `{table_name}`")
        lines.append(f"🕒 Thời gian: `{now}`")
        lines.append("")
        if approved:
            lines.append("Thay đổi đã được *chấp nhận* — Registry đã cập nhật baseline mới.")
        else:
            lines.append("Thay đổi đã bị *từ chối* — Registry giữ nguyên baseline cũ, hệ thống tiếp tục giám sát.")
        return self.send_message("\n".join(lines))