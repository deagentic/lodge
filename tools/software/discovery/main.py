#!/usr/bin/env python3
"""
retro-engineer — Universal codebase analysis tool
Detects language, maps structure, builds call trees, maps API usage,
extracts software decisions, and generates a comprehensive report.

Usage:
    python main.py [PATH] [OPTIONS]

Options:
    --output, -o    Output file (default: retro-report.md)
    --format, -f    Output format: markdown|json|dot (default: markdown)
    --depth, -d     Max call tree depth (default: 6)
    --json          Also emit retro-report.json alongside markdown

Examples:
    python main.py .
    python main.py /path/to/project --output report.md
    python main.py /path/to/project --format json
    python main.py /path/to/project --format dot | dot -Tsvg > callgraph.svg
"""

import sys
import argparse
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).parent))

from language_detector import detect_language  # noqa: E402
from structure_mapper import map_structure  # noqa: E402
from call_tree import build_call_tree  # noqa: E402
from api_mapper import map_api_calls  # noqa: E402
from decision_extractor import extract_decisions  # noqa: E402
from reporter import generate_report  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Retro-engineer a codebase: detect, map, analyze, document.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "path", nargs="?", default=".", help="Path to analyze (default: current dir)"
    )
    parser.add_argument("--output", "-o", default="retro-report.md", help="Output file")
    parser.add_argument(
        "--format",
        "-f",
        dest="fmt",
        choices=["markdown", "json", "dot"],
        default="markdown",
    )
    parser.add_argument(
        "--depth", "-d", type=int, default=6, help="Max call tree depth"
    )
    parser.add_argument(
        "--json", action="store_true", help="Also write JSON report alongside markdown"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress progress output"
    )

    args = parser.parse_args()

    target = Path(args.path).resolve()
    if not target.exists():
        print(f"[ERROR] Path not found: {target}", file=sys.stderr)
        sys.exit(1)

    def log(msg):
        if not args.quiet:
            print(msg, flush=True)

    log(f"[retro-engineer] Target: {target}")

    log("[1/5] Detecting language & technology stack...")
    tech_stack = detect_language(target)
    log(
        f'      > {tech_stack["primary_language"] or "unknown"} '
        f'({tech_stack["file_count"]} files, {tech_stack["total_lines"]:,} lines)'
    )
    if tech_stack["hardware_apis"]:
        log(
            f'      > Hardware APIs: {", ".join(h["pattern"] for h in tech_stack["hardware_apis"][:6])}'
        )

    log("[2/5] Mapping structure...")
    structure = map_structure(target, tech_stack)
    log(
        f'      > {len(structure["modules"])} modules, '
        f'{len(structure["entry_points"])} entry points, '
        f'{len(structure["public_api"])} public symbols'
    )

    log("[3/5] Building call tree...")
    ct = build_call_tree(target, tech_stack, structure)
    log(
        f'      > {len(ct["edges"])} call edges, '
        f'{len(ct["external_calls"])} external API call sites'
    )

    log("[4/5] Mapping external API usage...")
    api_calls = map_api_calls(target, tech_stack)
    groups = ", ".join(f"{g}({c})" for g, c in api_calls["summary"].items())
    log(f'      > {groups or "none"}')

    log("[5/5] Extracting software decisions...")
    decisions = extract_decisions(target, tech_stack)
    log(f'      > {decisions["summary"]}')

    # Generate primary report
    output_path = Path(args.output)
    report = generate_report(
        target=target,
        tech_stack=tech_stack,
        structure=structure,
        call_tree=ct,
        api_calls=api_calls,
        decisions=decisions,
        fmt=args.fmt,
    )
    output_path.write_text(report, encoding="utf-8")
    log(f"[OK] Report written to: {output_path.resolve()}")

    # Optionally also write JSON
    if args.json and args.fmt != "json":
        json_path = output_path.with_suffix(".json")
        json_report = generate_report(
            target=target,
            tech_stack=tech_stack,
            structure=structure,
            call_tree=ct,
            api_calls=api_calls,
            decisions=decisions,
            fmt="json",
        )
        json_path.write_text(json_report, encoding="utf-8")
        log(f"[OK] JSON report written to: {json_path.resolve()}")

    # Also write DOT graph if doing markdown
    if args.fmt == "markdown" and ct.get("dot"):
        dot_path = output_path.with_suffix(".dot")
        dot_path.write_text(ct["dot"], encoding="utf-8")
        log(f"[OK] Call graph (DOT) written to: {dot_path.resolve()}")
        log(f"    Render with: dot -Tsvg {dot_path.name} > callgraph.svg")

    # Print summary to stdout for agent consumption
    if not args.quiet:
        print("\n--- Summary -------------------------------------------")
        print(f'  Language:  {tech_stack["primary_language"]}')
        print(f'  Platform:  {tech_stack["platform"]}')
        print(f'  Files:     {tech_stack["file_count"]}')
        print(f'  HW APIs:   {len(tech_stack["hardware_apis"])} patterns found')
        print(f'  Calls:     {len(ct["edges"])} edges')
        print(f'  Decisions: {len(decisions["decisions"])} found')
        print(f"  Report:    {output_path.resolve()}")
        print("-------------------------------------------------------")


if __name__ == "__main__":
    main()
