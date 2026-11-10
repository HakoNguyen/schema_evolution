"""
Đo đạc cho báo cáo (phase 4). Chạy khi toàn bộ demo đang chạy (ingestor, loader, backend).

    python -m demo.bench schema --runs 10   # độ trễ phản ứng của engine với thay đổi schema, lặp N lần
    python -m demo.bench soak --minutes 30  # chạy liên tục: độ trễ end-to-end, mất dòng, thông lượng

In bảng kết quả và ghi demo/results/<loại>-<thời điểm>.json.
`schema` để lại các cột bench_* trên nguồn và warehouse: chạy `python -m demo.setup --reset` sau đó.
"""
import argparse
import json
import math
import time
from datetime import datetime, timezone

import clickhouse_connect
import psycopg2

import demo  # noqa: F401  (UTF-8 console)
from demo import config as c
from demo.check import loader_status, reconcile
from demo.scenario import STEPS, run_step

RESULTS_DIR = c.ROOT / "demo" / "results"


def pct(values: list[float], p: float) -> float:
    """Phân vị theo nearest-rank (đủ chính xác và dễ giải thích với mẫu nhỏ)."""
    s = sorted(values)
    return s[max(0, math.ceil(p / 100 * len(s)) - 1)]


def summarize(values: list[float]) -> dict:
    return {"n": len(values), "p50": pct(values, 50), "p95": pct(values, 95),
            "max": max(values), "mean": sum(values) / len(values)} if values else {"n": 0}


def _clients():
    return psycopg2.connect(**c.PG), clickhouse_connect.get_client(**c.CH, database=c.CH_DATABASE)


def _save(kind: str, payload: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{kind}-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nĐã lưu {path.relative_to(c.ROOT)}")


def bench_schema(runs: int, timeout: float) -> None:
    tag = format(int(time.time()) % 46656, "x")  # tên cột riêng cho mỗi lần chạy bench
    timings: dict[str, list[float]] = {"add_column": [], "widen": [], "breaking_freeze": [], "rollback_unfreeze": []}
    failures = []
    for i in range(runs):
        col = f"bench_{tag}_{i}"
        steps = {
            "add_column": dict(sql=f"ALTER TABLE trades ADD COLUMN {col} NUMERIC(10,2)", expect="target",
                               column=col, story=f"[{i + 1}/{runs}] thêm cột {col}"),
            "widen": dict(sql=f"ALTER TABLE trades ALTER COLUMN {col} TYPE NUMERIC(12,2)", expect="target",
                          column=col, type_contains="Decimal(12, 2)", story=f"[{i + 1}/{runs}] nới {col}"),
            "breaking_freeze": {**STEPS["narrow"], "story": f"[{i + 1}/{runs}] thu hẹp symbol"},
            "rollback_unfreeze": {**STEPS["rollback"], "story": f"[{i + 1}/{runs}] rollback symbol"},
        }
        for name, s in steps.items():
            dt = run_step(name, s, timeout)
            if dt is None:
                failures.append(f"run {i + 1}: {name}")
                if name == "breaking_freeze":
                    run_step("rollback_unfreeze", steps["rollback_unfreeze"], timeout)  # đừng để nguồn bị thu hẹp
                break
            timings[name].append(dt)
            time.sleep(1)  # để vài message mang schema mới đi qua trước bước kế tiếp

    time.sleep(5)  # cho loader ghi nốt phần tồn trước khi đối chiếu
    pg, ch = _clients()
    rec = reconcile(pg, ch)
    stats = {k: summarize(v) for k, v in timings.items()}

    print("\n| Thay đổi | n | p50 | p95 | max | trung bình |\n|---|---|---|---|---|---|")
    for k, st in stats.items():
        if st["n"]:
            print(f"| {k} | {st['n']} | {st['p50']:.2f}s | {st['p95']:.2f}s | {st['max']:.2f}s | {st['mean']:.2f}s |")
    print(f"\nĐối chiếu sau bench: mất {rec['lost_rows']} dòng ({rec['source_upto_mark']} = {rec['warehouse_upto_mark']})"
          if rec else "\nWarehouse chưa có dữ liệu")
    if failures:
        print("Không phản ứng kịp:", ", ".join(failures))
    _save("schema", {"runs": runs, "timeout": timeout, "stats": stats, "timings": timings,
                     "failures": failures, "reconcile_after": rec})


def bench_soak(minutes: float, interval: float) -> None:
    pg, ch = _clients()
    samples = []
    start = time.monotonic()
    first = None
    next_report = start + 60
    while time.monotonic() - start < minutes * 60:
        try:
            rec = reconcile(pg, ch)
        except Exception as e:  # DB chập chờn trong lúc soak cũng là kết quả đáng ghi lại
            samples.append({"t": time.monotonic() - start, "error": str(e)})
            pg, ch = _clients()
            time.sleep(interval)
            continue
        if rec:
            first = first or rec
            state = loader_status().get("loader", {}).get("state", "?")
            samples.append({"t": round(time.monotonic() - start, 1), "lag": rec["lag_seconds"],
                            "lost": rec["lost_rows"], "warehouse_total": rec["warehouse_total"], "loader": state})
        if time.monotonic() >= next_report and samples:
            s = samples[-1]
            print(f"[soak] {s['t'] / 60:5.1f} phút | lag {s.get('lag', 0):5.1f}s | mất {s.get('lost', '?')} | "
                  f"warehouse {s.get('warehouse_total', '?'):,} | loader {s.get('loader')}", flush=True)
            next_report += 60
        time.sleep(interval)

    ok = [s for s in samples if "lag" in s]
    running = [s["lag"] for s in ok if s["loader"] == "running"]
    elapsed = ok[-1]["t"] - ok[0]["t"] if len(ok) > 1 else 0
    result = {
        "minutes": minutes, "interval": interval, "samples": len(samples),
        "errors": sum(1 for s in samples if "error" in s),
        "lag_all": summarize([s["lag"] for s in ok]),
        "lag_while_running": summarize(running),  # loại các lúc PAUSE/HOLD chờ duyệt
        "max_lost_rows": max((s["lost"] for s in ok), default=None),
        "rows_loaded": ok[-1]["warehouse_total"] - ok[0]["warehouse_total"] if ok else 0,
        "rows_per_sec": (ok[-1]["warehouse_total"] - ok[0]["warehouse_total"]) / elapsed if elapsed else 0,
        "loader_states": {st: sum(1 for s in ok if s["loader"] == st) for st in {s["loader"] for s in ok}},
    }
    la, lr = result["lag_all"], result["lag_while_running"]
    print(f"\nSoak {minutes:g} phút, {result['samples']} mẫu ({result['errors']} lỗi):")
    if lr.get("n"):
        print(f"  độ trễ e2e khi loader chạy: p50 {lr['p50']:.2f}s, p95 {lr['p95']:.2f}s, max {lr['max']:.2f}s")
    if la.get("n"):
        print(f"  độ trễ e2e mọi lúc:         p50 {la['p50']:.2f}s, p95 {la['p95']:.2f}s, max {la['max']:.2f}s")
    print(f"  mất dòng tối đa ở mọi mẫu:  {result['max_lost_rows']}")
    print(f"  đã nạp {result['rows_loaded']:,} dòng, trung bình {result['rows_per_sec']:.1f} dòng/s")
    _save("soak", {**result, "series": samples})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    a = sub.add_parser("schema")
    a.add_argument("--runs", type=int, default=10)
    a.add_argument("--timeout", type=float, default=60)
    b = sub.add_parser("soak")
    b.add_argument("--minutes", type=float, default=30)
    b.add_argument("--interval", type=float, default=5)
    args = ap.parse_args()
    if args.mode == "schema":
        bench_schema(args.runs, args.timeout)
    else:
        bench_soak(args.minutes, args.interval)
