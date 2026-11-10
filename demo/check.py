"""
Đối chiếu nguồn và đích: số dòng, trade mới nhất, độ trễ.

    python -m demo.check            # 1 lần
    python -m demo.check --watch    # cập nhật mỗi 2s
"""
import argparse
import time
from datetime import datetime, timezone

import clickhouse_connect
import psycopg2

import demo  # noqa: F401  (UTF-8 console)
from demo import config as c


def snapshot(pg, ch) -> str:
    # Mốc đối chiếu = ingested_at mới nhất đã vào warehouse. Mỗi lô INSERT của ingestor có
    # cùng ingested_at, commit tuần tự, Debezium + loader giữ thứ tự commit => mọi dòng nguồn
    # có ingested_at < mốc PHẢI có mặt ở warehouse. Đếm 2 phía dưới mốc: bằng nhau = không mất
    # dòng nào, kể cả khi dữ liệu vẫn đang chảy.
    # FINAL: gộp bản ghi trùng (loader at-least-once) trước khi đếm.
    # Tính mốc ngay trong ClickHouse: truyền datetime qua tham số của clickhouse-connect làm lệch mốc.
    dst_total, mark, dst_n, dst_max_trade = ch.query(
        f"WITH (SELECT max(ingested_at) FROM {c.SOURCE_TABLE}) AS m "
        f"SELECT count(), m, countIf(ingested_at < m), max(trade_time) FROM {c.SOURCE_TABLE} FINAL"
    ).result_rows[0]
    now = datetime.now(timezone.utc)
    if not dst_total:
        return f"warehouse chưa có dữ liệu | {now:%H:%M:%S}"
    mark = mark.replace(tzinfo=timezone.utc)  # DateTime64(6,'UTC') trả về datetime naive theo UTC
    with pg.cursor() as cur:
        cur.execute(f"SELECT count(*), count(*) FILTER (WHERE ingested_at < %s) FROM {c.SOURCE_TABLE}", (mark,))
        src_total, src_n = cur.fetchone()
    pg.rollback()
    status = "KHỚP ✓" if src_n == dst_n else f"MẤT {src_n - dst_n} dòng ✗"
    lag = (now - dst_max_trade.replace(tzinfo=timezone.utc)).total_seconds()
    line = (f"{now:%H:%M:%S} | tới mốc {mark:%H:%M:%S.%f}: source {src_n:>7} / warehouse {dst_n:>7} {status} "
            f"| tổng source {src_total:>7}, warehouse {dst_total:>7} | độ trễ {lag:5.1f}s")
    naive_n, naive_max = ch.query(
        f"SELECT count(), max(trade_time) FROM {c.CH_NAIVE_DATABASE}.{c.SOURCE_TABLE} FINAL").result_rows[0]
    if naive_n:
        naive_lag = (now - naive_max.replace(tzinfo=timezone.utc)).total_seconds()
        line += f"\n         | đối chứng (không engine): warehouse {naive_n:>7}, thiếu {src_total - naive_n:>6} | độ trễ {naive_lag:5.1f}s"
    return line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true")
    args = ap.parse_args()
    pg = psycopg2.connect(**c.PG)
    ch = clickhouse_connect.get_client(**c.CH, database=c.CH_DATABASE)
    while True:
        print(snapshot(pg, ch), flush=True)
        if not args.watch:
            return
        time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
