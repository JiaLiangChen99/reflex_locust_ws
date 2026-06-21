"""CLI: ``reflex-locust-ws discover``."""

from __future__ import annotations

import argparse
import json
import sys


def _cmd_discover(args: argparse.Namespace) -> int:
    importlib_module = __import__("importlib")
    importlib = importlib_module.import_module

    try:
        from reflex_locust_ws.registry import discover_atoms
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    atoms = discover_atoms(args.app)

    if args.format == "json":
        payload = [
            {
                "locust_name": a.locust_name,
                "event_name": a.event_name,
                "weight": a.weight,
                "path": a.path,
                "archetype": a.archetype,
                "payload": a.payload,
                "description": a.description,
                "registered": a.registered,
            }
            for a in atoms
        ]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(f"Load-test atoms (@ws_loadtest) in {args.app}: {len(atoms)}\n")
    for atom in atoms:
        status = "ok" if atom.registered else "MISSING"
        desc = f" — {atom.description}" if atom.description else ""
        print(
            f"  [{status}] weight={atom.weight} archetype={atom.archetype} "
            f"path={atom.path!r}{desc}"
        )
        print(f"         locust: {atom.locust_name}")
        print(f"         event:  {atom.event_name}")
        if atom.payload:
            print(f"         payload sample: {atom.payload}")
        print()

    missing = [a for a in atoms if not a.registered]
    if missing and any(a.registered for a in atoms):
        print(
            f"Warning: {len(missing)} atom(s) not found in RegistrationContext.",
            file=sys.stderr,
        )
        return 1
    if not atoms:
        print("No @ws_loadtest handlers found. Add ws_loadtest above @rx.event.", file=sys.stderr)
        return 1
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from pathlib import Path

    from reflex_locust_ws.report import build_report

    report_dir = Path(args.dir)
    try:
        outputs = build_report(report_dir)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Report written to {report_dir.resolve()}")
    print(f"  Dashboard: {outputs['dashboard']}")
    print(f"  Summary:   {outputs['summary']}")
    chart_count = 0
    for key, path in outputs.items():
        if key not in ("dashboard", "summary") and str(path).endswith(".png"):
            print(f"  Chart:     {path}")
            chart_count += 1
    if chart_count == 0:
        print(
            "  (no charts — install matplotlib: uv pip install matplotlib)",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reflex-locust-ws",
        description="Reflex WebSocket (/_event) load testing helpers.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="List @ws_loadtest-decorated event handlers")
    discover.add_argument(
        "--app",
        default="roomdesign.roomdesign",
        help="Python module that imports the Reflex app (default: roomdesign.roomdesign)",
    )
    discover.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    discover.set_defaults(func=_cmd_discover)

    report = sub.add_parser("report", help="Build dashboard + charts from Locust CSV")
    report.add_argument(
        "--dir",
        default="loadtest/locust_report",
        help="Directory with Locust --csv exports (default: loadtest/locust_report)",
    )
    report.set_defaults(func=_cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
