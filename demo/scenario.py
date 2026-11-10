"""
Các bước kịch bản demo: chạy DDL trên nguồn (vai dev) và đo thời gian engine phản ứng.

    python -m demo.scenario add_column    # non-breaking -> tự đồng bộ
    python -m demo.scenario widen         # non-breaking -> tự đồng bộ
    python -m demo.scenario rename        # breaking     -> freeze, chờ duyệt
    python -m demo.scenario narrow        # breaking     -> freeze, chờ duyệt
    python -m demo.scenario rollback      # dev hoàn tác narrow -> engine tự gỡ freeze
    python -m demo.scenario tickers_drop     # pipeline 2: breaking -> CHỈ market_tickers bị freeze
    python -m demo.scenario tickers_restore  # dev thêm lại cột -> engine tự gỡ freeze market_tickers

Thời gian đo = từ lúc ALTER commit trên Postgres đến lúc warehouse có schema mới
(non-breaking) hoặc registry chuyển sang frozen (breaking).
"""
import argparse
import time

import clickhouse_connect
import psycopg2
import requests

import demo  # noqa: F401  (UTF-8 console)
from demo import config as c

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
    # Pipeline 2 chạy song song: freeze market_tickers không được làm dừng market_trades.
    "tickers_drop": dict(
        sql="ALTER TABLE tickers DROP COLUMN low_price",
        expect="frozen", pipeline=c.TICKERS_PIPELINE, table=c.TICKERS_TABLE,
        story="Pipeline 2: ai đó xóa cột low_price của tickers -> chỉ market_tickers bị freeze, trades vẫn chạy",
    ),
    "tickers_restore": dict(
        sql="ALTER TABLE tickers ADD COLUMN low_price NUMERIC(24,8)",
        expect="clear", pipeline=c.TICKERS_PIPELINE, table=c.TICKERS_TABLE,
        story="Dev thêm lại low_price -> nguồn khớp baseline, engine tự gỡ freeze market_tickers",
    ),
}


def _target_type(ch, table: str, column: str) -> str | None:
    rows = ch.query(
        "SELECT type FROM system.columns WHERE database = %(d)s AND table = %(t)s AND name = %(n)s",
        parameters={"d": c.CH_DATABASE, "t": table, "n": column},
    ).result_rows
    return rows[0][0] if rows else None


def run(step: str, timeout: float) -> float | None:
    return run_step(step, STEPS[step], timeout)


def _gate(session: requests.Session, pipeline: str, table: str) -> dict | None:
    """Trạng thái bảng qua Gate API của engine (None nếu engine tạm không trả lời)."""
    try:
        resp = session.get(f"{c.ENGINE_API}/api/gate/{pipeline}/{table}", timeout=2)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


def run_step(step: str, s: dict, timeout: float) -> float | None:
    """Chạy SQL của bước trên nguồn, trả về số giây tới khi engine phản ứng (None = quá timeout)."""
    print(f"\n▶ {step}: {s['story']}\n  SQL: {s['sql']}")
    ch = clickhouse_connect.get_client(**c.CH)
    session = requests.Session()
    pipeline, table = s.get("pipeline", c.PIPELINE_NAME), s.get("table", c.SOURCE_TABLE)

    pg = psycopg2.connect(**c.PG)
    pg.autocommit = True
    with pg.cursor() as cur:
        cur.execute("SET lock_timeout = '5s'")
        cur.execute(s["sql"])
    t0 = time.monotonic()
    pg.close()

    while time.monotonic() - t0 < timeout:
        if s["expect"] == "target":
            typ = _target_type(ch, table, s["column"])
            if typ and s.get("type_contains", "") in typ:
                dt = time.monotonic() - t0
                print(f"  ✓ NON-BREAKING: warehouse tự đồng bộ ({s['column']} {typ}) sau {dt:.2f}s, luồng dữ liệu không dừng")
                return dt
        elif (gate := _gate(session, pipeline, table)) is not None:
            if s["expect"] == "clear" and gate["state"] == "open":
                dt = time.monotonic() - t0
                print(f"  ✓ nguồn đã khớp baseline, engine gỡ freeze sau {dt:.2f}s, loader chạy tiếp")
                return dt
            if s["expect"] == "frozen" and gate["state"] == "frozen":
                dt = time.monotonic() - t0
                changes = ", ".join(f"{x['change_type']}({x['column']})" for x in gate["pending_changes"])
                print(f"  ⛔ BREAKING: {pipeline}/{table} bị freeze sau {dt:.2f}s [{changes}] -> loader tạm dừng, chờ duyệt trên UI")
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
