"""
Vẽ biểu đồ hiệu năng (PNG, để chèn vào báo cáo) từ kết quả của demo.bench:

    pip install matplotlib          # chỉ cần cho script này, engine không dùng
    python -m demo.charts           # lấy file schema-*.json và soak-*.json mới nhất trong demo/results/

Ảnh được ghi vào demo/results/charts/.
"""
import json
import sys
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    sys.exit("Cần matplotlib: pip install matplotlib")

RESULTS = Path(__file__).parent / "results"
OUT = RESULTS / "charts"

# Bảng màu chung (dataviz reference palette, nền sáng): 1 chuỗi = 1 màu, chữ dùng màu mực, không dùng màu chuỗi.
SERIES, SURFACE, INK, INK_2, MUTED, GRID = "#2a78d6", "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e6e5e0"

LABELS = {
    "add_column": "Thêm cột\n(tự đồng bộ)",
    "widen": "Nới rộng kiểu\n(tự đồng bộ)",
    "breaking_freeze": "Thu hẹp kiểu\n(breaking → freeze)",
    "rollback_unfreeze": "Nguồn hoàn tác\n(tự gỡ freeze)",
}


def _latest(prefix: str) -> Path | None:
    files = sorted(RESULTS.glob(f"{prefix}-*.json"))
    return files[-1] if files else None


def _style(ax, title: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold", pad=12)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def chart_reaction(path: Path) -> Path:
    """Strip plot: mỗi chấm là 1 lần chạy; vạch đậm = p50; nhãn bên phải = p50 / p95."""
    data = json.loads(path.read_text(encoding="utf-8"))
    names = [k for k in LABELS if data["timings"].get(k)]
    fig, ax = plt.subplots(figsize=(8, 0.9 * len(names) + 1.4), facecolor=SURFACE)
    _style(ax, f"Thời gian engine phản ứng với thay đổi schema (n = {data['runs']} lần / kịch bản)")
    xmax = max(max(data["timings"][k]) for k in names) * 1.35
    for i, k in enumerate(names):
        y = len(names) - 1 - i
        values, st = data["timings"][k], data["stats"][k]
        ax.scatter(values, [y] * len(values), s=46, color=SERIES, alpha=0.55,
                   edgecolors=SURFACE, linewidths=1.5, zorder=3)
        ax.plot([st["p50"]] * 2, [y - 0.28, y + 0.28], color=INK, linewidth=2, solid_capstyle="round", zorder=4)
        ax.text(xmax * 0.985, y, f"p50 {st['p50']:.2f}s · p95 {st['p95']:.2f}s",
                va="center", ha="right", fontsize=9, color=INK_2)
    ax.set_yticks(range(len(names)), [LABELS[k] for k in reversed(names)], color=INK)
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.6, len(names) - 0.4)
    ax.set_xlabel("giây, tính từ lúc thay đổi có hiệu lực ở nguồn", color=MUTED, fontsize=9)
    fig.tight_layout()
    out = OUT / "reaction_time.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def chart_soak(path: Path) -> Path:
    """Độ trễ end-to-end (nguồn -> kho) theo thời gian trong lần chạy dài."""
    data = json.loads(path.read_text(encoding="utf-8"))
    ok = [s for s in data["series"] if "lag" in s]
    t = [s["t"] / 60 for s in ok]
    lag = [s["lag"] for s in ok]
    fig, ax = plt.subplots(figsize=(8, 3.4), facecolor=SURFACE)
    _style(ax, f"Độ trễ end-to-end Postgres → ClickHouse trong {data['minutes']:g} phút chạy liên tục")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.grid(axis="x", visible=False)
    ax.plot(t, lag, color=SERIES, linewidth=2, solid_joinstyle="round")
    p50, p95 = data["lag_all"]["p50"], data["lag_all"]["p95"]
    ax.axhline(p95, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(t[-1], p95, f" p95 {p95:.2f}s", va="bottom", ha="right", fontsize=9, color=INK_2)
    ax.set_ylim(0, max(lag) * 1.25)
    ax.set_xlim(0, t[-1])
    ax.set_xlabel("phút", color=MUTED, fontsize=9)
    ax.set_ylabel("độ trễ (giây)", color=MUTED, fontsize=9)
    ax.text(0.0, -0.32, f"{data['rows_loaded']:,} dòng đã nạp ({data['rows_per_sec']:.0f} dòng/s) · "
            f"mất dòng tối đa: {data['max_lost_rows']} · p50 {p50:.2f}s · {data['errors']} lỗi đo",
            transform=ax.transAxes, fontsize=9, color=INK_2)
    fig.tight_layout()
    out = OUT / "soak_latency.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    if (p := _latest("schema")):
        made.append(chart_reaction(p))
    if (p := _latest("soak")):
        made.append(chart_soak(p))
    if not made:
        sys.exit(f"Chưa có kết quả trong {RESULTS}: chạy python -m demo.bench schema / soak trước")
    for m in made:
        print(f"đã ghi {m}")


if __name__ == "__main__":
    main()
