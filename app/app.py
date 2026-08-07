"""
app.py — Streamlit UI cho Schema Evolution Core.

Chỉ đọc/ghi vào Registry (file JSON dưới registry/) — không cần kết nối
DB thật, vì mọi trạng thái (frozen, draft, version history) đã được
scheduler.py ghi lại sẵn trong lúc quét. UI chỉ hiển thị + xử lý
approve/reject, không tự crawl hay chạy DDL gì cả.

Chạy: streamlit run app.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
import streamlit as st

from src.schema_evolution.core import SchemaRegistry, approve_change_and_sync
from src.schema_evolution.notification import TelegramNotifier
from src.schema_evolution.engines.base import TableSchema, ColumnSchema
from src.schema_evolution.engines.postgres import PostgresEngine
from src.schema_evolution.engines.mysql import MySQLEngine
from src.schema_evolution.engines.mongo import MongoEngine
from src.schema_evolution.engines.clickhouse import ClickHouseEngine

ENGINE_REGISTRY = {
    "postgres": PostgresEngine,
    "mysql": MySQLEngine,
    "mongodb": MongoEngine,
    "clickhouse": ClickHouseEngine,
}

st.set_page_config(page_title="Schema Evolution Monitor", layout="wide")

# Custom Redpanda-inspired styles with light blue accent and high contrast
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

/* Main Body typography and background */
html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    background-color: #f8fafc !important;
}

/* Sidebar: Dark Navy/Slate like Redpanda */
[data-testid="stSidebar"] {
    background-color: #0f172a !important;
    border-right: 1px solid #1e293b;
    padding-top: 1.5rem;
}

/* Force light text color inside the sidebar for all labels, markdown, widgets */
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] caption,
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #f1f5f9 !important;
}

/* Radio button option labels in sidebar */
[data-testid="stSidebar"] div[role="radiogroup"] label p {
    color: #cbd5e1 !important;
    font-weight: 500;
}

/* Style active items in sidebar */
[data-testid="stSidebar"] div[role="radiogroup"] label {
    font-size: 0.9rem;
    padding: 8px 12px;
    border-radius: 6px;
    margin-bottom: 4px;
    background-color: transparent;
    transition: all 0.2s ease;
    cursor: pointer;
    border-left: 3px solid transparent;
}
[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
    background-color: rgba(255, 255, 255, 0.06);
}
[data-testid="stSidebar"] div[role="radiogroup"] label:hover p {
    color: #ffffff !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] [data-checked="true"] {
    background-color: #1e293b !important;
    border-radius: 6px;
}
[data-testid="stSidebar"] div[role="radiogroup"] [data-checked="true"] label {
    border-left: 3px solid #0ea5e9;
}
[data-testid="stSidebar"] div[role="radiogroup"] [data-checked="true"] label p {
    color: #ffffff !important;
    font-weight: 600 !important;
}

/* Sidebar Radio Circle Hiding (Making it look like a list) */
[data-testid="stSidebar"] div[role="radiogroup"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.9rem;
}

/* Headings */
h1 {
    font-size: 1.75rem !important;
    font-weight: 700 !important;
    color: #0f172a !important;
    margin-bottom: 1.25rem !important;
    letter-spacing: -0.02em;
}

h2, h3 {
    font-size: 1.2rem !important;
    font-weight: 600 !important;
    color: #1e293b !important;
    margin-top: 1.5rem !important;
    margin-bottom: 0.75rem !important;
}

/* Metric Cards style (clean borders, white BG) */
div[data-testid="stMetric"] {
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
    padding: 16px 20px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02), 0 1px 2px rgba(0, 0, 0, 0.04) !important;
}
div[data-testid="stMetricLabel"] > div {
    color: #64748b !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}
div[data-testid="stMetricValue"] > div {
    color: #0f172a !important;
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    margin-top: 4px;
}

/* Custom Warning card */
.alert-card {
    background-color: #fef2f2;
    border: 1px solid #fee2e2;
    border-left: 4px solid #ef4444;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 16px 0;
}
.alert-card-title {
    color: #991b1b;
    font-weight: 600;
    font-size: 0.95rem;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.alert-card-item {
    color: #7f1d1d;
    font-size: 0.9rem;
    margin: 4px 0;
    padding-left: 12px;
}

/* Primary Button (Approve) */
div.stButton > button[kind="primary"] {
    background: #0ea5e9 !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    padding: 8px 24px !important;
    box-shadow: 0 1px 2px rgba(14, 165, 233, 0.2) !important;
    transition: all 0.2s ease !important;
    width: 100%;
}
div.stButton > button[kind="primary"]:hover {
    background: #0284c7 !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 6px rgba(14, 165, 233, 0.3) !important;
}

/* Secondary Button (Reject) */
div.stButton > button[kind="secondary"] {
    background: #ffffff !important;
    color: #475569 !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    padding: 8px 24px !important;
    transition: all 0.2s ease !important;
    width: 100%;
}
div.stButton > button[kind="secondary"]:hover {
    color: #1e293b !important;
    border-color: #94a3b8 !important;
    background-color: #f8fafc !important;
}

/* DataFrame Customization */
.stDataFrame {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
}

/* High Contrast Dropdowns / Selectbox Style for Main Page */
div[data-testid="stSelectbox"] div {
    background-color: #ffffff !important;
    color: #0f172a !important;
}
div[data-testid="stSelectbox"] p {
    color: #0f172a !important;
}
div[data-testid="stSelectbox"] svg {
    fill: #475569 !important;
}

/* Styled option dropdown listbox */
div[role="listbox"] {
    background-color: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 6px !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
}
div[role="listbox"] li {
    color: #0f172a !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}
div[role="listbox"] li:hover {
    background-color: #f1f5f9 !important;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_monitored_tables(config: dict) -> list[dict]:
    """
    Danh sách bảng đang theo dõi, suy ra từ config.yaml (không đọc DB
    thật). Mỗi item gắn với 1 registry_key duy nhất, kèm pair_config gốc
    để lúc Approve có đủ thông tin build target engine.
    """
    items = []
    for pair in config.get("pairs", []):
        pair_name = pair["name"]
        mode = "Đồng bộ nguồn → đích" if "target" in pair else "Chỉ phát hiện"
        for table_name in pair.get("tables", []):
            items.append({
                "pair_name": pair_name,
                "table_name": table_name,
                "registry_key": f"{pair_name}__{table_name}",
                "mode": mode,
                "pair_config": pair,
            })
    return items


def build_target_engine(pair_config: dict):
    """Build + connect target_engine từ pair_config. Trả về None nếu
    pair không có target (chế độ detection-only)."""
    target_spec = pair_config.get("target")
    if not target_spec:
        return None
    engine_cls = ENGINE_REGISTRY[target_spec["type"]]
    engine = engine_cls(target_spec["config"])
    engine.connect()
    return engine


def render_columns(columns: list[ColumnSchema]) -> None:
    if not columns:
        st.caption("Không có cột nào.")
        return
    rows = [
        {
            "Cột": c.name,
            "Kiểu dữ liệu": c.data_type + (f"({c.max_length})" if c.max_length else ""),
            "NULL": "✔" if c.nullable else "✘",
            "Default": c.default if c.default is not None else "—",
        }
        for c in columns
    ]
    st.dataframe(rows, width="stretch", hide_index=True)


def render_schema_details(schema: TableSchema) -> None:
    render_columns(schema.columns)
    caption_parts = []
    if schema.primary_key:
        caption_parts.append(f"Primary key: {', '.join(schema.primary_key)}")
    if caption_parts:
        st.caption(" · ".join(caption_parts))
    for fk in schema.foreign_keys:
        st.caption(
            f"FK `{fk.column_name}` → `{fk.ref_table}.{fk.ref_column}` "
            f"(ON DELETE {fk.on_delete or '—'})"
        )


def main() -> None:
    config = load_config()
    registry = SchemaRegistry(config["registry"]["dir"])
    notifier = TelegramNotifier(
        bot_token=config["telegram"]["bot_token"],
        chat_id=config["telegram"]["chat_id"],
    )
    tables = list_monitored_tables(config)

    st.markdown("<h1>Schema Evolution Monitor</h1>", unsafe_allow_html=True)

    if not tables:
        st.warning("config.yaml chưa khai báo pair nào trong mục `pairs`.")
        return

    # --- Sidebar: chọn bảng ---
    st.sidebar.header("Bảng đang theo dõi")
    labels = [f"{t['pair_name']} / {t['table_name']}" for t in tables]
    frozen_flags = [registry.is_frozen(t["registry_key"]) for t in tables]
    display_labels = [
        f"🔴 {label}" if frozen else f"🟢 {label}"
        for label, frozen in zip(labels, frozen_flags)
    ]
    selected_idx = st.sidebar.radio(
        "Chọn bảng", range(len(labels)), format_func=lambda i: display_labels[i]
    )
    selected = tables[selected_idx]
    key = selected["registry_key"]
    st.sidebar.markdown(f"<div style='margin-top: 15px; font-size: 0.85rem; color: #94a3b8;'>Chế độ: {selected['mode']}</div>", unsafe_allow_html=True)

    # --- Thông tin tổng quan ---
    is_frozen = registry.is_frozen(key)
    version = registry.get_version(key)
    schema = registry.load(key)

    col1, col2, col3 = st.columns(3)
    col1.metric("Bảng", selected["table_name"])
    col2.metric("Version", str(version) if version else "—")
    col3.metric("Trạng thái", "Chờ phê duyệt" if is_frozen else "Bình thường")

    st.divider()

    if schema is None:
        st.info("Chưa có dữ liệu cho bảng này — scheduler chưa quét lần nào.")
        return

    # --- Breaking change đang chờ duyệt ---
    if is_frozen:
        st.subheader("Thay đổi đang chờ phê duyệt")
        draft = registry.load_draft(key)
        if draft is None:
            st.warning("Bảng đang bị khoá nhưng không tìm thấy draft.")
        else:
            detected_time = draft.get('detected_at', '—')
            breaking_html = f"""
            <div class="alert-card">
                <div class="alert-card-title">⚠️ Breaking Changes Pending Approval (Phát hiện lúc: {detected_time})</div>
            """
            for change in draft.get("breaking_changes", []):
                target = change.get("column_name") or change.get("constraint_name") or "?"
                breaking_html += f'<div class="alert-card-item"><strong>{change["change_type"]}</strong> tại <code>{target}</code></div>'
            breaking_html += "</div>"
            st.markdown(breaking_html, unsafe_allow_html=True)

            approve_col, reject_col = st.columns(2)
            if approve_col.button("Approve", type="primary"):
                target_engine = None
                try:
                    target_engine = build_target_engine(selected["pair_config"])
                except Exception as e:
                    st.warning(f"Không kết nối được target ({e}) — chỉ cập nhật Registry, không đồng bộ target.")

                result = approve_change_and_sync(target_engine, key, registry, registry_key=key)

                if target_engine is not None:
                    target_engine.disconnect()

                if result.get("failed_on_target"):
                    st.error(
                        f"Có {len(result['failed_on_target'])} thay đổi KHÔNG áp dụng "
                        f"được lên target — xem log console."
                    )
                if result.get("applied_to_target"):
                    st.success(f"Đã đồng bộ {len(result['applied_to_target'])} thay đổi lên target.")

                notifier.notify_change_reviewed(
                    selected["table_name"], approved=True, pair_name=selected["pair_name"]
                )
                st.rerun()
            if reject_col.button("Reject", type="secondary"):
                registry.reject_change(key)
                notifier.notify_change_reviewed(
                    selected["table_name"], approved=False, pair_name=selected["pair_name"]
                )
                st.rerun()
        st.divider()

    # --- Cấu trúc hiện tại ---
    st.subheader("Cấu trúc hiện tại")
    render_schema_details(schema)

    st.divider()

    # --- Lịch sử version ---
    st.subheader("Lịch sử phiên bản")
    versions = registry.list_versions(key)
    if not versions:
        st.caption("Chưa có lịch sử.")
    else:
        versions_sorted = sorted(versions, reverse=True)

        def _format_version_label(v: int) -> str:
            ts_raw = registry.get_version_timestamp(key, v)
            if ts_raw:
                try:
                    ts = datetime.fromisoformat(ts_raw).strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    ts = ts_raw
            else:
                ts = "—"
            return f"V{v}  —  {ts}"

        selected_version = st.selectbox(
            "Xem lại phiên bản", versions_sorted, format_func=_format_version_label
        )
        if selected_version is not None:
            v_schema = registry.load_version(key, selected_version)
            if v_schema is not None:
                render_schema_details(v_schema)


if __name__ == "__main__":
    main()