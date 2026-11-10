"""
Đối chiếu nguồn và đích: số dòng, mất dòng, độ trễ.

    python -m demo.check                     # 1 lần
    python -m demo.check --watch             # cập nhật mỗi 2s
    python -m demo.check --watch --report    # + báo lên engine (Reporting API) để hiện trên UI
"""
import argparse
import time
from datetime import datetime, timezone

import clickhouse_connect
import psycopg2
import requests

import demo  # noqa: F401  (UTF-8 console)
from demo import config as c


def _utc(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=timezone.utc) if dt else None  # DateTime64(.., 'UTC') trả về naive UTC


def reconcile(pg, ch) -> dict | None:
    """
    Mốc đối chiếu = ingested_at mới nhất đã vào warehouse. Mỗi lô INSERT của ingestor có cùng
    ingested_at, commit tuần tự, Debezium + loader giữ thứ tự commit => mọi dòng nguồn có
    ingested_at < mốc PHẢI có mặt ở warehouse. Đếm 2 phía dưới mốc: bằng nhau = không mất dòng
    nào, kể cả khi dữ liệu vẫn đang chảy. FINAL: gộp bản ghi trùng (loader at-least-once).
    None nếu warehouse chưa có dữ liệu.
    """
    # Tính mốc ngay trong ClickHouse: truyền datetime qua tham số của clickhouse-connect làm lệch mốc.
    dst_total, mark, dst_n, dst_max_trade = ch.query(
        f"WITH (SELECT max(ingested_at) FROM {c.SOURCE_TABLE}) AS m "
        f"SELECT count(), m, countIf(ingested_at < m), max(trade_time) FROM {c.SOURCE_TABLE} FINAL"
    ).result_rows[0]
    if not dst_total:
        return None
    now = datetime.now(timezone.utc)
    mark = _utc(mark)
    with pg.cursor() as cur:
        cur.execute(f"SELECT count(*), count(*) FILTER (WHERE ingested_at < %s) FROM {c.SOURCE_TABLE}", (mark,))
        src_total, src_n = cur.fetchone()
    pg.rollback()

    # Đối chứng đo theo CÙNG mốc của pipeline chính: còn khỏe -> ~0 (chỉ chênh dữ liệu đang
    # trên đường); đã FAILED -> số dòng dưới mốc đứng yên trong khi nguồn tăng -> chênh lệch tăng dần.
    naive_n, naive_upto, naive_max = ch.query(
        f"WITH (SELECT max(ingested_at) FROM {c.CH_DATABASE}.{c.SOURCE_TABLE}) AS m "
        f"SELECT count(), countIf(ingested_at < m), max(trade_time) "
        f"FROM {c.CH_NAIVE_DATABASE}.{c.SOURCE_TABLE} FINAL").result_rows[0]
    return {
        "now": now.isoformat(),
        "mark": mark.isoformat(),
        "source_total": src_total,
        "warehouse_total": dst_total,
        "source_upto_mark": src_n,
        "warehouse_upto_mark": dst_n,
        "lost_rows": src_n - dst_n,
        "lag_seconds": (now - _utc(dst_max_trade)).total_seconds(),
        "naive": {
            "warehouse_total": naive_n,
            "missing_rows": max(0, src_n - naive_upto),
            "lag_seconds": (now - _utc(naive_max)).total_seconds(),
        } if naive_n else None,
    }


def report(r: dict | None) -> None:
    """Báo kết quả đối chiếu lên engine như một thành phần ("reconciler") qua Reporting API."""
    if r is None:
        return
    metrics = {
        "source_rows": r["source_total"],
        "warehouse_rows": r["warehouse_total"],
        "lost_rows": r["lost_rows"],
        "lag_seconds": round(r["lag_seconds"], 2),
    }
    if r["naive"]:
        metrics["baseline_rows_not_delivered"] = r["naive"]["missing_rows"]
    mark = datetime.fromisoformat(r["mark"])
    try:
        requests.post(f"{c.ENGINE_API}/api/pipelines/{c.PIPELINE_NAME}/components/reconciler", timeout=2, json={
            "state": "ok" if r["lost_rows"] == 0 else "error",
            "role": "source vs warehouse reconciliation",
            "metrics": metrics,
            "message": f"verified up to {mark:%H:%M:%S}: {r['source_upto_mark']:,} source = "
                       f"{r['warehouse_upto_mark']:,} warehouse rows",
        })
    except requests.RequestException:
        pass  # engine tạm không liên lạc được: vẫn in ra console


def format_line(r: dict | None) -> str:
    now = datetime.now(timezone.utc)
    if r is None:
        return f"warehouse chưa có dữ liệu | {now:%H:%M:%S}"
    mark = datetime.fromisoformat(r["mark"])
    status = "KHỚP ✓" if r["lost_rows"] == 0 else f"MẤT {r['lost_rows']} dòng ✗"
    line = (f"{now:%H:%M:%S} | tới mốc {mark:%H:%M:%S.%f}: source {r['source_upto_mark']:>7} / "
            f"warehouse {r['warehouse_upto_mark']:>7} {status} | tổng source {r['source_total']:>7}, "
            f"warehouse {r['warehouse_total']:>7} | độ trễ {r['lag_seconds']:5.1f}s")
    if r["naive"]:
        n = r["naive"]
        line += (f"\n         | đối chứng (không engine): warehouse {n['warehouse_total']:>7}, "
                 f"thiếu {n['missing_rows']:>6} | độ trễ {n['lag_seconds']:5.1f}s")
    return line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--report", action="store_true", help="báo kết quả lên engine qua Reporting API")
    args = ap.parse_args()
    pg = psycopg2.connect(**c.PG)
    ch = clickhouse_connect.get_client(**c.CH, database=c.CH_DATABASE)
    while True:
        r = reconcile(pg, ch)
        print(format_line(r), flush=True)
        if args.report:
            report(r)
        if not args.watch:
            return
        time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
