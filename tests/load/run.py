#!/usr/bin/env python3
"""Run load tests via Locust (subprocess wrapper for CI and local smoke runs).

Usage::

    # Terminal 1 — start backend
    reflex run --backend-only --env prod

    # Terminal 2 — smoke (5 users, 30s)
    python tests/load/run.py smoke

    # connection capacity probe
    python tests/load/run.py connections --users 20 --run-time 1m

    # open Locust Web UI
    python tests/load/run.py ui
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

LOAD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = LOAD_DIR.parent.parent
DEFAULT_HOST = os.getenv("LOADTEST_HOST", "http://127.0.0.1:8000")

SCENARIOS = {
    "smoke": {
        "locustfile": "locustfile.py",
        "users": "5",
        "spawn_rate": "2",
        "run_time": "30s",
        "report_name": "smoke",
    },
    "connections": {
        "locustfile": "locustfile_connections.py",
        "users": "50",
        "spawn_rate": "5",
        "run_time": "2m",
        "report_name": "connections",
    },
}


def _build_locust_cmd(
    *,
    locustfile: str,
    host: str,
    headless: bool,
    users: str | None,
    spawn_rate: str | None,
    run_time: str | None,
    report_dir: Path | None,
) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        str(LOAD_DIR / locustfile),
        "--host",
        host,
    ]
    if headless:
        cmd.append("--headless")
        if users:
            cmd.extend(["--users", users])
        if spawn_rate:
            cmd.extend(["--spawn-rate", spawn_rate])
        if run_time:
            cmd.extend(["--run-time", run_time])
        if report_dir:
            report_dir.mkdir(parents=True, exist_ok=True)
            cmd.extend(
                [
                    "--html",
                    str(report_dir / "report.html"),
                    "--csv",
                    str(report_dir / "run"),
                ]
            )
    return cmd


def _run_report(report_dir: Path) -> int:
    cmd = [
        sys.executable,
        "-m",
        "reflex_locust_ws.cli",
        "report",
        "--dir",
        str(report_dir),
    ]
    return subprocess.call(cmd, cwd=PROJECT_ROOT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run reflex_locust_ws load tests")
    parser.add_argument(
        "scenario",
        choices=[*SCENARIOS, "ui"],
        help="smoke / connections / ui (Locust Web UI)",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Reflex backend URL")
    parser.add_argument("--users", help="Override virtual user count (headless)")
    parser.add_argument("--spawn-rate", help="Override spawn rate (headless)")
    parser.add_argument("--run-time", help="Override duration, e.g. 30s, 3m (headless)")
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip reflex-locust-ws report after headless run",
    )
    args = parser.parse_args(argv)

    if args.scenario == "ui":
        cmd = _build_locust_cmd(
            locustfile="locustfile.py",
            host=args.host,
            headless=False,
            users=None,
            spawn_rate=None,
            run_time=None,
            report_dir=None,
        )
        print("Open http://localhost:8089 and set users / spawn rate.")
        return subprocess.call(cmd, cwd=PROJECT_ROOT)

    preset = SCENARIOS[args.scenario]
    report_dir = LOAD_DIR / "reports" / preset["report_name"]
    cmd = _build_locust_cmd(
        locustfile=preset["locustfile"],
        host=args.host,
        headless=True,
        users=args.users or preset["users"],
        spawn_rate=args.spawn_rate or preset["spawn_rate"],
        run_time=args.run_time or preset["run_time"],
        report_dir=report_dir,
    )
    print("Running:", " ".join(cmd))
    rc = subprocess.call(cmd, cwd=PROJECT_ROOT)
    if rc == 0 and not args.no_report:
        print(f"\nGenerating dashboard in {report_dir} ...")
        _run_report(report_dir)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
