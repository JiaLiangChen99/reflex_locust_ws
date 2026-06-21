"""Build charts and an HTML dashboard from Locust CSV exports."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class EndpointStat:
    type: str
    name: str
    request_count: int
    failure_count: int
    median_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    rps: float
    p95_ms: float
    p99_ms: float


@dataclass
class HistoryPoint:
    timestamp: float
    user_count: int
    total_rps: float
    total_avg_ms: float
    total_median_ms: float
    total_p95_ms: float


def _find_csv(report_dir: Path, suffix: str) -> Path | None:
    """Locate ``*_stats.csv`` or ``*_stats_history.csv`` (prefer newest by mtime)."""
    direct = report_dir / suffix
    if direct.is_file():
        return direct

    matches = sorted(
        report_dir.glob(f"*{suffix}"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if matches:
        return matches[0]
    return None


def _pct(row: dict[str, str], key: str) -> float:
    raw = row.get(key, "") or "0"
    try:
        return float(raw)
    except ValueError:
        return 0.0


def load_stats(report_dir: Path) -> list[EndpointStat]:
    path = _find_csv(report_dir, "stats.csv")
    if path is None:
        msg = f"No stats CSV in {report_dir} (run with --csv prefix first)"
        raise FileNotFoundError(msg)

    rows: list[EndpointStat] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = row.get("Name", "")
            if not name or name == "Aggregated":
                continue
            rows.append(
                EndpointStat(
                    type=row.get("Type", ""),
                    name=name,
                    request_count=int(row.get("Request Count") or 0),
                    failure_count=int(row.get("Failure Count") or 0),
                    median_ms=_pct(row, "Median Response Time"),
                    avg_ms=_pct(row, "Average Response Time"),
                    min_ms=_pct(row, "Min Response Time"),
                    max_ms=_pct(row, "Max Response Time"),
                    rps=_pct(row, "Requests/s"),
                    p95_ms=_pct(row, "95%"),
                    p99_ms=_pct(row, "99%"),
                )
            )
    return rows


def load_history(report_dir: Path) -> list[HistoryPoint]:
    path = _find_csv(report_dir, "stats_history.csv")
    if path is None:
        return []

    points: list[HistoryPoint] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("Name") not in ("Aggregated", ""):
                continue
            try:
                ts = float(row.get("Timestamp") or 0)
            except ValueError:
                continue
            points.append(
                HistoryPoint(
                    timestamp=ts,
                    user_count=int(float(row.get("User Count") or 0)),
                    total_rps=_pct(row, "Requests/s"),
                    total_avg_ms=_pct(row, "Total Average Response Time")
                    or _pct(row, "Average Response Time"),
                    total_median_ms=_pct(row, "Total Median Response Time")
                    or _pct(row, "50%"),
                    total_p95_ms=_pct(row, "95%"),
                )
            )
    return points


def _summary(stats: list[EndpointStat], history: list[HistoryPoint]) -> dict[str, Any]:
    wsr = [s for s in stats if s.type == "WSR"]
    total_req = sum(s.request_count for s in stats)
    total_fail = sum(s.failure_count for s in stats)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_requests": total_req,
        "total_failures": total_fail,
        "failure_rate_pct": round(100 * total_fail / total_req, 4) if total_req else 0,
        "endpoints": [asdict(s) for s in stats],
        "peak_rps": max((p.total_rps for p in history), default=0),
        "peak_users": max((p.user_count for p in history), default=0),
    }


def _require_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt
    except ImportError as exc:
        msg = "matplotlib is required for charts: uv pip install matplotlib"
        raise ImportError(msg) from exc


def _chart_latency_bars(stats: list[EndpointStat], out: Path) -> None:
    plt = _require_matplotlib()
    wsr = sorted([s for s in stats if s.type == "WSR"], key=lambda s: s.p95_ms, reverse=True)
    if not wsr:
        wsr = sorted(stats, key=lambda s: s.p95_ms, reverse=True)
    if not wsr:
        return

    labels = [s.name for s in wsr]
    x = range(len(labels))
    width = 0.35
    medians = [s.median_ms for s in wsr]
    p95s = [s.p95_ms for s in wsr]

    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.9), 5))
    ax.bar([i - width / 2 for i in x], medians, width, label="Median (ms)", color="#6366f1")
    ax.bar([i + width / 2 for i in x], p95s, width, label="P95 (ms)", color="#f97316")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel("Response time (ms)")
    ax.set_title("WebSocket event latency by handler")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def _chart_timeline(history: list[HistoryPoint], out: Path) -> None:
    if len(history) < 2:
        return
    plt = _require_matplotlib()

    t0 = history[0].timestamp
    minutes = [(p.timestamp - t0) / 60 for p in history]
    rps = [p.total_rps for p in history]
    median = [p.total_median_ms for p in history]
    p95 = [p.total_p95_ms for p in history]
    users = [p.user_count for p in history]

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(minutes, rps, color="#059669", label="Total RPS", linewidth=2)
    ax1.set_xlabel("Elapsed (minutes)")
    ax1.set_ylabel("Requests / sec", color="#059669")
    ax1.tick_params(axis="y", labelcolor="#059669")
    ax1.grid(alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(minutes, median, color="#6366f1", label="Median (ms)", linestyle="--")
    ax2.plot(minutes, p95, color="#f97316", label="P95 (ms)", linestyle=":")
    ax2.set_ylabel("Latency (ms)")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    peak_u = max(users) if users else 0
    ax1.set_title(f"Load test timeline (peak users: {peak_u})")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def _chart_bubble(stats: list[EndpointStat], out: Path) -> None:
    """Bubble chart: volume vs latency (intuitive alternative to a volcano plot)."""
    plt = _require_matplotlib()
    wsr = [s for s in stats if s.type == "WSR" and s.request_count > 0]
    if not wsr:
        return

    xs = [s.request_count for s in wsr]
    ys = [s.median_ms for s in wsr]
    sizes = [max(40, (s.p95_ms - s.median_ms + 1) * 8) for s in wsr]
    colors = [s.failure_count for s in wsr]

    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(xs, ys, s=sizes, c=colors, cmap="YlOrRd", alpha=0.75, edgecolors="#334155")
    for s in wsr:
        ax.annotate(s.name, (s.request_count, s.median_ms), fontsize=8, xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("Request count (volume)")
    ax.set_ylabel("Median latency (ms)")
    ax.set_title("Volume vs latency (bubble size ≈ P95−Median)")
    cb = fig.colorbar(scatter, ax=ax)
    cb.set_label("Failures")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def _write_dashboard(
    report_dir: Path,
    summary: dict[str, Any],
    chart_files: list[str],
) -> Path:
    rows_html = ""
    for ep in summary.get("endpoints", []):
        if ep.get("name") == "Aggregated":
            continue
        fail_style = ' style="color:#b91c1c"' if ep.get("failure_count") else ""
        rows_html += f"""
        <tr>
          <td>{ep.get('type','')}</td>
          <td>{ep.get('name','')}</td>
          <td>{ep.get('request_count',0)}</td>
          <td{fail_style}>{ep.get('failure_count',0)}</td>
          <td>{ep.get('median_ms',0):.1f}</td>
          <td>{ep.get('p95_ms',0):.1f}</td>
          <td>{ep.get('p99_ms',0):.1f}</td>
          <td>{ep.get('rps',0):.2f}</td>
        </tr>"""

    charts_html = "\n".join(
        f'    <section><h2>{Path(c).stem.replace("_", " ").title()}</h2>'
        f'<img src="{c}" alt="{c}" style="max-width:100%;height:auto;border:1px solid #e2e8f0;border-radius:8px;" /></section>'
        for c in chart_files
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>reflex-locust-ws dashboard</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #0f172a; background: #f8fafc; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .meta {{ color: #64748b; margin-bottom: 1.5rem; }}
    .cards {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }}
    .card {{ background: white; padding: 1rem 1.25rem; border-radius: 8px; box-shadow: 0 1px 3px rgb(0 0 0 / 8%); min-width: 140px; }}
    .card strong {{ display: block; font-size: 1.5rem; }}
    table {{ border-collapse: collapse; width: 100%; background: white; border-radius: 8px; overflow: hidden; }}
    th, td {{ border-bottom: 1px solid #e2e8f0; padding: 0.5rem 0.75rem; text-align: left; font-size: 0.9rem; }}
    th {{ background: #f1f5f9; }}
    section {{ margin: 2rem 0; }}
    a {{ color: #4f46e5; }}
  </style>
</head>
<body>
  <h1>Reflex WebSocket 压测报告</h1>
  <p class="meta">Generated {summary.get('generated_at','')} · reflex-locust-ws</p>
  <div class="cards">
    <div class="card">Total requests<strong>{summary.get('total_requests',0)}</strong></div>
    <div class="card">Failures<strong>{summary.get('total_failures',0)}</strong></div>
    <div class="card">Failure rate<strong>{summary.get('failure_rate_pct',0)}%</strong></div>
    <div class="card">Peak RPS<strong>{summary.get('peak_rps',0):.2f}</strong></div>
    <div class="card">Peak users<strong>{summary.get('peak_users',0)}</strong></div>
  </div>
  <p>Locust 原始报告: <a href="report.html">report.html</a> · JSON: <a href="summary.json">summary.json</a></p>
  <h2>Endpoints</h2>
  <table>
    <thead><tr><th>Type</th><th>Name</th><th>Req</th><th>Fail</th><th>Med</th><th>P95</th><th>P99</th><th>RPS</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
{charts_html}
</body>
</html>"""
    out = report_dir / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    return out


def build_report(report_dir: Path) -> dict[str, Path]:
    """Generate summary.json, PNG charts, and dashboard.html."""
    report_dir = report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = report_dir / "charts"
    charts_dir.mkdir(exist_ok=True)

    stats = load_stats(report_dir)
    history = load_history(report_dir)
    summary = _summary(stats, history)

    summary_path = report_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    chart_paths: list[Path] = []
    try:
        p1 = charts_dir / "latency_bars.png"
        _chart_latency_bars(stats, p1)
        chart_paths.append(p1)

        p2 = charts_dir / "timeline.png"
        _chart_timeline(history, p2)
        if p2.exists() and p2.stat().st_size > 0:
            chart_paths.append(p2)

        p3 = charts_dir / "volume_vs_latency.png"
        _chart_bubble(stats, p3)
        chart_paths.append(p3)
    except ImportError:
        chart_paths = []

    rel_charts = [str(p.relative_to(report_dir)) for p in chart_paths if p.is_file()]
    dashboard = _write_dashboard(report_dir, summary, rel_charts)

    return {
        "summary": summary_path,
        "dashboard": dashboard,
        **{p.stem: p for p in chart_paths},
    }
