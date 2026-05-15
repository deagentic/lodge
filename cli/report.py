#!/usr/bin/env python3
"""
lodge report — CLI for querying the API observability service.

Install: pip install -e .
Usage:
    cornerstone-obs report summary [--url URL] [--project SLUG] [--from DATE] [--to DATE] [--format table|json|csv]
    cornerstone-obs report events  [--url URL] [--event-type TYPE] [--limit N] [--format table|json]
    cornerstone-obs report cost    [--url URL] [--from DATE] [--to DATE] [--group-by project|model|skill]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any


def _base_url(args) -> str:
    url = getattr(args, "url", None) or os.environ.get("AGENTIC_TELEMETRY_URL", "")
    if not url:
        print(
            "ERROR: --url is required or set AGENTIC_TELEMETRY_URL env var.",
            file=sys.stderr,
        )
        sys.exit(1)
    return url.rstrip("/")


def _get(url: str, params: dict[str, str]) -> dict[str, Any]:
    query = "&".join(f"{k}={v}" for k, v in params.items() if v)
    full_url = f"{url}?{query}" if query else url
    try:
        with urllib.request.urlopen(full_url, timeout=10) as resp:  # nosec B310  # URL sourced from config/env, not user input
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"ERROR: HTTP {e.code} — {body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def _default_dates() -> tuple[str, str]:
    to = datetime.now(timezone.utc)
    from_ = to - timedelta(days=30)
    return from_.strftime("%Y-%m-%d"), to.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# summary subcommand
# ---------------------------------------------------------------------------


def _print_summary_csv(data: dict) -> None:
    writer = csv.writer(sys.stdout)
    writer.writerow(["metric", "value"])
    for k, v in data.items():
        if isinstance(v, dict):
            for sk, sv in v.items():
                writer.writerow([f"{k}.{sk}", sv])
        elif isinstance(v, list):
            pass  # lists (top_skills, top_models) are omitted from CSV flat output
        else:
            writer.writerow([k, v])


def _print_summary_table(data: dict) -> None:
    ci = data.get("ci_runs", {})
    pass_rate = (
        f"{round(ci.get('passed', 0) / ci.get('total', 1) * 100)}%"
        if ci.get("total")
        else "N/A"
    )

    rows = [
        ("Proyectos generados", data.get("projects_generated", 0)),
        ("Skills invocados", data.get("skills_invoked", 0)),
        ("Runs CI (total)", ci.get("total", 0)),
        ("CI passed", ci.get("passed", 0)),
        ("CI failed", ci.get("failed", 0)),
        ("CI pass rate", pass_rate),
        ("Herramientas ejecutadas", data.get("tools_executed", 0)),
        ("Conocimiento creado", data.get("knowledge_created", 0)),
        ("Conocimiento usado", data.get("knowledge_used", 0)),
        ("Costo total estimado (USD)", f"${data.get('total_cost_usd', 0):.6f}"),
    ]

    print("\n=== Resumen de lodge ===\n")
    for label, value in rows:
        print(f"  {label:<35} {value}")

    if data.get("top_skills"):
        print("\n  Top Skills:")
        for s in data["top_skills"][:5]:
            print(f"    {s['skill_name']:<40} {s['count']:>6} invocaciones")

    if data.get("top_models"):
        print("\n  Costo por Modelo:")
        for m in data["top_models"]:
            print(
                f"    {m['model']:<45} {m['count']:>6} calls   ${m['total_cost_usd']:.6f}"
            )
    print()


def cmd_summary(args) -> None:
    base = _base_url(args)
    from_default, to_default = _default_dates()
    params = {
        "from": (getattr(args, "from_dt", None) or from_default) + "T00:00:00Z",
        "to": (getattr(args, "to_dt", None) or to_default) + "T23:59:59Z",
        "project_slug": getattr(args, "project", "") or "",
    }
    data = _get(f"{base}/v1/summary", params)

    fmt = getattr(args, "format", "table")

    if fmt == "json":
        print(json.dumps(data, indent=2))
        return

    if fmt == "csv":
        _print_summary_csv(data)
        return

    _print_summary_table(data)


# ---------------------------------------------------------------------------
# events subcommand
# ---------------------------------------------------------------------------


def cmd_events(args) -> None:
    base = _base_url(args)
    params = {
        "event_type": getattr(args, "event_type", "") or "",
        "limit": str(getattr(args, "limit", 50)),
    }
    data = _get(f"{base}/v1/events", params)
    items = data.get("items", [])

    fmt = getattr(args, "format", "table")
    if fmt == "json":
        print(json.dumps(items, indent=2, default=str))
        return

    print(f"\n=== Eventos ({data.get('total', 0)} total) ===\n")
    print(f"  {'Tipo':<25} {'Proyecto':<25} {'Timestamp':<25}")
    print("  " + "-" * 75)
    for item in items:
        print(
            f"  {item['event_type']:<25} {item['project_slug']:<25} {item.get('event_ts', '')[:19]}"
        )
    print()


# ---------------------------------------------------------------------------
# cost subcommand
# ---------------------------------------------------------------------------


def cmd_cost(args) -> None:
    base = _base_url(args)
    from_default, to_default = _default_dates()
    params = {
        "from": (getattr(args, "from_dt", None) or from_default) + "T00:00:00Z",
        "to": (getattr(args, "to_dt", None) or to_default) + "T23:59:59Z",
    }
    data = _get(f"{base}/v1/summary", params)
    group_by = getattr(args, "group_by", "model")

    print(f"\n=== Costo estimado por {group_by} ===\n")

    if group_by == "model":
        for m in data.get("top_models", []):
            print(
                f"  {m['model']:<45} ${m['total_cost_usd']:.6f}  ({m['count']} calls)"
            )
    elif group_by == "skill":
        for s in data.get("top_skills", []):
            print(f"  {s['skill_name']:<45} {s['count']} invocaciones")
    else:  # project — not directly available in summary without filtering; show total
        print(f"  Total: ${data.get('total_cost_usd', 0):.6f}")

    print(f"\n  TOTAL: ${data.get('total_cost_usd', 0):.6f} USD\n")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lodge", description="Lodge CLI"
    )
    sub = parser.add_subparsers(dest="command")

    # report
    report_p = sub.add_parser("report", help="Query the observability service")
    report_sub = report_p.add_subparsers(dest="subcommand")

    # report summary
    summary_p = report_sub.add_parser("summary")
    summary_p.add_argument("--url", default="")
    summary_p.add_argument("--project", default="")
    summary_p.add_argument("--from", dest="from_dt", default="")
    summary_p.add_argument("--to", dest="to_dt", default="")
    summary_p.add_argument(
        "--format", choices=["table", "json", "csv"], default="table"
    )

    # report events
    events_p = report_sub.add_parser("events")
    events_p.add_argument("--url", default="")
    events_p.add_argument("--event-type", dest="event_type", default="")
    events_p.add_argument("--limit", type=int, default=50)
    events_p.add_argument("--format", choices=["table", "json"], default="table")

    # report cost
    cost_p = report_sub.add_parser("cost")
    cost_p.add_argument("--url", default="")
    cost_p.add_argument("--from", dest="from_dt", default="")
    cost_p.add_argument("--to", dest="to_dt", default="")
    cost_p.add_argument(
        "--group-by",
        dest="group_by",
        choices=["project", "model", "skill"],
        default="model",
    )

    args = parser.parse_args()

    if args.command == "report":
        if args.subcommand == "summary":
            cmd_summary(args)
        elif args.subcommand == "events":
            cmd_events(args)
        elif args.subcommand == "cost":
            cmd_cost(args)
        else:
            report_p.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
