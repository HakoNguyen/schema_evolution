"""
Các bước kịch bản demo: chạy DDL trên nguồn (vai dev) và đo thời gian engine phản ứng.

    python -m demo.scenario add_column    # non-breaking -> tự đồng bộ
    python -m demo.scenario widen         # non-breaking -> tự đồng bộ
    python -m demo.scenario rename        # breaking     -> freeze, chờ duyệt
    python -m demo.scenario narrow        # breaking     -> freeze, chờ duyệt
    python -m demo.scenario rollback      # dev hoàn tác narrow -> engine tự gỡ freeze

Thời gian đo = từ lúc ALTER commit trên Postgres đến lúc warehouse có schema mới
(non-breaking) hoặc registry chuyển sang frozen (breaking).
"""
import argparse
import time

import clickhouse_connect
import psycopg2

import demo  # noqa: F401  (UTF-8 console)
from demo import config as c
from src.schema_evolution.core import SchemaRegistry

STEPS = {
    "add_column": dict(
        sql="ALTER TABLE trades ADD COLUMN is_buyer_maker BOOLEAN",
        expect="target", column="is_buyer_maker",
        story="Team phân tích cần biết bên mua hay bán chủ động -> thêm cột is_buyer_maker",
    ),
    "widen": dict(
        sql="ALTER TABLE trades ALTER COLUMN price TYPE NUMERIC(24,8)",
        expect="target", column="price", type_contains="Decimal(24, 8)",
        story="Giá token mới vượt NUMERIC(18,8) -> nới rộng price lên NUMERIC(24,8)",
    ),
    "rename": dict(
        sql="ALTER TABLE trades RENAME COLUMN qty TO quantity",
        expect="frozen",
        story="Refactor đặt lại tên qty -> quantity: các dashboard/query cũ sẽ vỡ nếu tự áp dụng",
    ),
    "narrow": dict(
        sql="ALTER TABLE trades ALTER COLUMN symbol TYPE VARCHAR(10)",
        expect="frozen",
        story="Ai đó thu hẹp symbol VARCHAR(20) -> VARCHAR(10): nguy cơ cắt cụt dữ liệu ở warehouse",
    ),
    # Thay đổi bị từ chối thì nguồn phải quay về schema cũ (Reject một mình không đủ: lần quét kế
    # tiếp sẽ phát hiện lại và freeze lần nữa). Khi nguồn khớp baseline, engine tự gỡ freeze.
    "rollback": dict(
        sql="ALTER TABLE trades ALTER COLUMN symbol TYPE VARCHAR(20)",
        expect="clear",
        story="Dev rollback thay đổi nguy hiểm trên nguồn -> engine thấy nguồn khớp baseline, tự gỡ freeze",
    ),
}


def _target_type(ch, column: str) -> str | None:
    rows = ch.query(
        "SELECT type FROM system.columns WHERE database = %(d)s AND table = %(t)s AND name = %(n)s",
        parameters={"d": c.CH_DATABASE, "t": c.SOURCE_TABLE, "n": column},
    ).result_rows
    return rows[0][0] if rows else None


def run(step: str, timeout: float) -> float | None:
    return run_step(step, STEPS[step], timeout)


def run_step(step: str, s: dict, timeout: float) -> float | None:
    """Chạy SQL của bước trên nguồn, trả về số giây tới khi engine phản ứng (None = quá timeout)."""
    print(f"\n▶ {step}: {s['story']}\n  SQL: {s['sql']}")
    ch = clickhouse_connect.get_client(**c.CH)
    registry = SchemaRegistry(c.REGISTRY_DIR)

    pg = psycopg2.connect(**c.PG)
    pg.autocommit = True
    with pg.cursor() as cur:
        cur.execute("SET lock_timeout = '5s'")
        cur.execute(s["sql"])
    t0 = time.monotonic()
    pg.close()

    while time.monotonic() - t0 < timeout:
        if s["expect"] == "clear":
            try:
                frozen = registry.is_frozen(c.REGISTRY_KEY)
            except ValueError:
                frozen = True  # registry đang được ghi dở -> đọc lại
            if not frozen:
                dt = time.monotonic() - t0
                print(f"  ✓ nguồn đã khớp baseline, engine gỡ freeze sau {dt:.2f}s, loader chạy tiếp")
                return dt
        elif s["expect"] == "target":
            typ = _target_type(ch, s["column"])
            if typ and s.get("type_contains", "") in typ:
                dt = time.monotonic() - t0
                print(f"  ✓ NON-BREAKING: warehouse tự đồng bộ ({s['column']} {typ}) sau {dt:.2f}s, luồng dữ liệu không dừng")
                return dt
        else:
            try:
                frozen = registry.is_frozen(c.REGISTRY_KEY)
            except ValueError:
                frozen = False  # registry đang được ghi dở
            if frozen:
                dt = time.monotonic() - t0
                draft = registry.load_draft(c.REGISTRY_KEY) or {}
                changes = ", ".join(f"{x['change_type']}({x.get('column_name')})" for x in draft.get("breaking_changes", []))
                print(f"  ⛔ BREAKING: bảng bị freeze sau {dt:.2f}s [{changes}] -> loader tạm dừng, chờ duyệt trên UI")
                return dt
        time.sleep(0.1)
    print(f"  ✗ engine chưa phản ứng sau {timeout:.0f}s (backend có đang chạy không?)")
    return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=list(STEPS))
    ap.add_argument("--timeout", type=float, default=90)
    args = ap.parse_args()
    run(args.step, args.timeout)
