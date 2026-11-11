"""
Ingestor: trade thật từ Binance WebSocket -> Postgres (exchange.public.trades).

    python -m demo.ingestor                                   # live
    python -m demo.ingestor --record demo/recordings/x.jsonl  # live + ghi lại để replay
    python -m demo.ingestor --replay demo/recordings/x.jsonl  # phát lại (dự phòng mất mạng)

Đóng vai "ứng dụng sàn giao dịch": mỗi trade được map ra MỌI trường app biết (kể cả
trường của các phiên bản schema sau), nhưng INSERT chỉ ghi những cột đang có trong bảng.
=> ALTER TABLE ADD/RENAME COLUMN trên nguồn có hiệu lực ngay, không phải sửa/khởi động lại app.
"""
import argparse
import asyncio
import json
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg2
import psycopg2.errors
import websockets
from psycopg2.extras import execute_values

import demo  # noqa: F401  (UTF-8 console)
from demo import config as c

DEFAULT_SYMBOLS = "btcusdt,ethusdt,solusdt,bnbusdt,xrpusdt,dogeusdt"
DEFAULT_WS = "wss://data-stream.binance.vision"  # endpoint chỉ-dữ-liệu-thị-trường; dự phòng: wss://stream.binance.com:9443
COLUMN_REFRESH_SECONDS = 2


def to_row(d: dict) -> dict:
    """Binance trade event -> mọi cột app biết. Thứ tự key cố định để các lô cùng cấu trúc."""
    price, qty = Decimal(d["p"]), Decimal(d["q"])
    return {
        "trade_id": d["t"],
        "symbol": d["s"],
        "price": price,
        "qty": qty,
        "quantity": qty,              # tên mới nếu cột qty bị RENAME thành quantity
        "trade_time": datetime.fromtimestamp(d["T"] / 1000, tz=timezone.utc),
        "is_buyer_maker": d["m"],     # kịch bản ADD COLUMN
        "quote_qty": price * qty,     # kịch bản ADD COLUMN numeric
    }


def ticker_row(d: dict) -> dict:
    """Binance 24h miniTicker -> 1 dòng bảng tickers (pipeline 2, UPSERT theo symbol)."""
    return {
        "symbol": d["s"],
        "last_price": Decimal(d["c"]),
        "open_price": Decimal(d["o"]),
        "high_price": Decimal(d["h"]),
        "low_price": Decimal(d["l"]),
        "base_volume": Decimal(d["v"]),
        "quote_volume": Decimal(d["q"]),
        "event_time": datetime.fromtimestamp(d["E"] / 1000, tz=timezone.utc),
    }


class PostgresSink:
    def __init__(self, table: str, upsert_key: str | None = None):
        # upsert_key: None = chỉ INSERT (bỏ qua trùng); "symbol" = UPSERT giữ bản mới nhất.
        self.table, self.upsert_key = table, upsert_key
        self.conn = None
        self.columns: set[str] = set()
        self.refreshed_at = 0.0

    def _connect(self):
        self.conn = psycopg2.connect(**c.PG, connect_timeout=5)

    def _refresh_columns(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s",
                (self.table,),
            )
            self.columns = {r[0] for r in cur.fetchall()}
        self.conn.rollback()  # kết thúc transaction đọc, tránh giữ lock catalog khi có ALTER
        self.refreshed_at = time.monotonic()

    def write(self, rows: list[dict]) -> int:
        if self.conn is None or self.conn.closed:
            self._connect()
            self.refreshed_at = 0
        if time.monotonic() - self.refreshed_at > COLUMN_REFRESH_SECONDS:
            self._refresh_columns()
        if self.upsert_key:
            # 1 lệnh UPSERT không được chạm cùng 1 dòng 2 lần -> giữ bản mới nhất của mỗi khoá trong lô.
            rows = list({r[self.upsert_key]: r for r in rows}.values())
        for attempt in (1, 2):
            cols = [k for k in rows[0] if k in self.columns]
            if self.upsert_key:
                updates = ", ".join(f"{k} = EXCLUDED.{k}" for k in cols if k != self.upsert_key)
                conflict = f"ON CONFLICT ({self.upsert_key}) DO UPDATE SET {updates}"
            else:
                conflict = "ON CONFLICT DO NOTHING"
            sql = f"INSERT INTO {self.table} ({', '.join(cols)}) VALUES %s {conflict}"
            try:
                with self.conn.cursor() as cur:
                    execute_values(cur, sql, [tuple(r[k] for k in cols) for r in rows], page_size=1000)
                    inserted = cur.rowcount
                self.conn.commit()
                return inserted
            except (psycopg2.errors.UndefinedColumn, psycopg2.errors.UndefinedTable):
                # Cột vừa bị đổi tên/xóa giữa 2 lần refresh -> đọc lại schema rồi thử lại 1 lần.
                self.conn.rollback()
                self._refresh_columns()
                if attempt == 2:
                    raise
            except psycopg2.Error:
                self.conn.rollback()
                raise
        return 0


async def live_source(queue: asyncio.Queue, symbols: list[str], ws_base: str, record_path: str | None):
    streams = [f"{s}@trade" for s in symbols] + [f"{s}@miniTicker" for s in symbols]
    url = f"{ws_base}/stream?streams=" + "/".join(streams)
    rec = open(record_path, "a", encoding="utf-8", buffering=1) if record_path else None
    try:
        # websockets.connect dùng như async iterator = tự kết nối lại khi rớt mạng.
        async for ws in websockets.connect(url, ping_interval=20, open_timeout=10):
            print(f"[ingestor] connected {url}")
            try:
                async for msg in ws:
                    d = json.loads(msg)["data"]
                    queue.put_nowait(d)
                    if rec and d.get("e") == "trade":  # file replay chỉ chứa trade
                        rec.write(json.dumps(d) + "\n")
            except websockets.ConnectionClosed as e:
                print(f"[ingestor] websocket closed ({e}), reconnecting...")
    finally:
        if rec:
            rec.close()


async def replay_source(queue: asyncio.Queue, path: str, speed: float):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    events = [json.loads(l) for l in lines if l.strip()]
    if not events:
        raise SystemExit(f"{path} rỗng")
    t0 = events[0]["T"]
    # Dời trade_time về "bây giờ" để độ trễ/thời gian trên dashboard trông như dữ liệu live.
    shift_ms = int(time.time() * 1000) - t0
    start = time.monotonic()
    print(f"[ingestor] replay {len(events)} trades từ {path} (x{speed})")
    for d in events:
        delay = (d["T"] - t0) / 1000 / speed - (time.monotonic() - start)
        if delay > 0:
            await asyncio.sleep(delay)
        queue.put_nowait({**d, "T": d["T"] + shift_ms})
    print("[ingestor] replay xong")


async def _write_tickers(sink: PostgresSink, rows: list[dict], stats: Counter):
    try:
        stats["tickers"] += await asyncio.to_thread(sink.write, rows)
    except psycopg2.Error as e:
        stats["ticker_failed"] += len(rows)
        print(f"[ingestor] UPSERT tickers lỗi, bỏ {len(rows)} dòng: {type(e).__name__}: {str(e).strip()[:200]}")
        if sink.conn is not None and sink.conn.closed:
            sink.conn = None


async def writer(queue: asyncio.Queue, sink: PostgresSink, ticker_sink: PostgresSink):
    stats = Counter()
    last_price: dict[str, Decimal] = {}
    last_report = time.monotonic()
    while True:
        await asyncio.sleep(0.25)
        batch, tickers = [], []
        while not queue.empty() and len(batch) < 2000:
            d = queue.get_nowait()
            if d.get("e") == "24hrMiniTicker":
                tickers.append(ticker_row(d))
            else:
                batch.append(to_row(d))
        if tickers:
            await _write_tickers(ticker_sink, tickers, stats)
        if batch:
            stats["received"] += len(batch)
            try:
                stats["inserted"] += await asyncio.to_thread(sink.write, batch)
            except psycopg2.Error as e:
                # Ví dụ: cột NOT NULL mới không có default -> app "phiên bản cũ" không ghi được.
                stats["failed"] += len(batch)
                print(f"[ingestor] INSERT lỗi, bỏ {len(batch)} trade: {type(e).__name__}: {str(e).strip()[:200]}")
                if sink.conn is not None and sink.conn.closed:
                    sink.conn = None
            for r in batch:
                last_price[r["symbol"]] = r["price"]
        now = time.monotonic()
        if now - last_report >= 5:
            rate = stats["inserted"] / (now - last_report)
            prices = "  ".join(f"{s} {p.normalize():f}" for s, p in sorted(last_price.items()))
            print(f"[ingestor] {rate:6.1f} trade/s | inserted {stats['inserted']} "
                  f"(failed {stats['failed']}) | ticker upserts {stats['tickers']} | {prices}")
            stats.clear()
            last_report = now


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=DEFAULT_SYMBOLS)
    ap.add_argument("--ws", default=DEFAULT_WS, help="WebSocket base URL của Binance")
    ap.add_argument("--record", help="ghi trade live ra file JSONL để replay sau")
    ap.add_argument("--replay", help="phát lại file JSONL thay vì kết nối Binance")
    ap.add_argument("--speed", type=float, default=1.0, help="tốc độ replay (1 = như thật)")
    args = ap.parse_args()

    queue: asyncio.Queue = asyncio.Queue()
    sink = PostgresSink(c.SOURCE_TABLE)
    ticker_sink = PostgresSink("tickers", upsert_key="symbol")
    if args.replay:
        source = replay_source(queue, args.replay, args.speed)
    else:
        if args.record:
            Path(args.record).parent.mkdir(parents=True, exist_ok=True)
        source = live_source(queue, args.symbols.lower().split(","), args.ws.rstrip("/"), args.record)
    await asyncio.gather(source, writer(queue, sink, ticker_sink))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[ingestor] stopped")
