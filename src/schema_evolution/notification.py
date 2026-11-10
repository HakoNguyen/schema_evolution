import os
from datetime import datetime
from html import escape

from src.schema_evolution.engines.base import SchemaChange, ChangeType
import requests

# Định dạng HTML của Telegram: chỉ cần escape < > &; tên có dấu _ hiển thị đúng
# (Markdown legacy trước đây làm hiện "is\_buyer\_maker" bên trong khối code).


def _code(text) -> str:
    return f"<code>{escape(str(text))}</code>"


def _type(col) -> str:
    if col is None:
        return "?"
    if col.precision:
        return f"{col.data_type}({col.precision},{col.scale or 0})"
    return col.data_type + (f"({col.max_length})" if col.max_length else "")


def _describe(change: SchemaChange) -> str:
    """Một dòng mô tả thay đổi, không icon."""
    t = change.change_type
    name = _code(change.column_name or change.constraint_name or "?")
    old, new = change.old_value, change.new_value

    if t == ChangeType.ADD_COLUMN:
        return f"Thêm cột {name} · {escape(_type(new))}, {'NULL' if new and new.nullable else 'NOT NULL'}"
    if t == ChangeType.DROP_COLUMN:
        return f"Xoá cột {name} · trước đó {escape(_type(old))}"
    if t == ChangeType.RENAME_COLUMN:
        return f"Đổi tên cột {name} → {_code(getattr(new, 'name', new))}"
    if t in (ChangeType.WIDEN_TYPE, ChangeType.NARROW_TYPE, ChangeType.CHANGE_TYPE_INCOMPATIBLE):
        return f"Đổi kiểu {name} · {escape(_type(old))} → {escape(_type(new))}"
    if t == ChangeType.NOT_NULL_TO_NULLABLE:
        return f"Cột {name} cho phép NULL"
    if t == ChangeType.NULLABLE_TO_NOT_NULL:
        return f"Cột {name} bắt buộc NOT NULL"
    if t in (ChangeType.ADD_PRIMARY_KEY, ChangeType.DROP_PRIMARY_KEY, ChangeType.CHANGE_PRIMARY_KEY):
        return f"Đổi primary key · {escape(str(old or '∅'))} → {escape(str(new or '∅'))}"
    if t == ChangeType.ADD_FOREIGN_KEY:
        return f"Thêm khoá ngoại {name}"
    if t == ChangeType.DROP_FOREIGN_KEY:
        return f"Xoá khoá ngoại {name}"
    return f"{escape(t.value)} tại {name}"


def _message(dot: str, title: str, table_name: str, pair_name: str | None, body: list[str]) -> str:
    where = f"{pair_name} / {table_name}" if pair_name else table_name
    return "\n".join([
        f"{dot} <b>{escape(title)}</b>",
        _code(where),
        "",
        *body,
        "",
        f"<i>{datetime.now():%Y-%m-%d %H:%M:%S}</i>",
    ])


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, max_retries: int = 2):
        # Biến môi trường ưu tiên hơn config — không commit token vào YAML.
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or bot_token
        chat_id = os.environ.get("TELEGRAM_CHAT_ID") or chat_id
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.max_retries = max_retries
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, text: str) -> bool:
        if not self.bot_token or not self.chat_id:
            return False  # chưa cấu hình Telegram: không gọi API (3 lần 404 chặn luồng xử lý vài giây)
        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}

        for attempt in range(1, self.max_retries + 2):
            try:
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    return True
                print(f"[TelegramNotifier] Lần thử {attempt}: HTTP {resp.status_code} - {resp.text}")
            except requests.RequestException as e:
                print(f"[TelegramNotifier] Lần thử {attempt}: lỗi mạng - {e}")

        print(f"[TelegramNotifier] Gửi thất bại sau {self.max_retries + 1} lần thử.")
        return False

    def notify_breaking_changes(self, table_name: str, changes: list[SchemaChange], pair_name: str | None = None) -> bool:
        return self.send_message(_message(
            "🔴", "Thay đổi breaking — đang chờ duyệt", table_name, pair_name,
            [*(f"• {_describe(c)}" for c in changes),
             "",
             "Bảng đã bị đóng băng, loader tạm dừng, dữ liệu được giữ trong Kafka.",
             "Duyệt, từ chối, hoặc rollback ở nguồn trên Web UI."],
        ))

    def notify_auto_sync_applied(self, table_name: str, changes: list[SchemaChange], pair_name: str | None = None) -> bool:
        if not changes:
            return True
        return self.send_message(_message(
            "🟢", "Đã tự đồng bộ sang warehouse", table_name, pair_name,
            [f"• {_describe(c)}" for c in changes],
        ))

    def notify_change_reviewed(self, table_name: str, approved: bool, pair_name: str | None = None) -> bool:
        """Gửi khi kỹ sư bấm Approve/Reject (Web UI hoặc unfreeze_cli.py)."""
        if approved:
            return self.send_message(_message(
                "🟢", "Đã duyệt", table_name, pair_name,
                ["Thay đổi đã được áp dụng lên warehouse và ghi thành baseline mới. Bảng được mở lại."],
            ))
        return self.send_message(_message(
            "⚪", "Đã từ chối", table_name, pair_name,
            ["Baseline giữ nguyên. Cần rollback thay đổi ở nguồn, nếu không bảng sẽ bị đóng băng lại ở lần quét sau."],
        ))

    def notify_resolved_at_source(self, table_name: str, pair_name: str | None = None) -> bool:
        return self.send_message(_message(
            "🟢", "Đã xử lý từ nguồn", table_name, pair_name,
            ["Schema nguồn đã quay về baseline. Bảng được mở lại, loader chạy tiếp."],
        ))
