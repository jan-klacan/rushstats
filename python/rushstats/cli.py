"""Composable command-line analyses using Python's standard argparse."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .api import ANALYSES, analyze


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate a Markdown statistical report from CSV.",
        epilog="Examples: rushstats data.csv --all | rushstats data.csv --describe --correlation -o report.md",
    )
    p.add_argument("input", type=Path, help="UTF-8 CSV input file")
    p.add_argument("--version", action="version", version=f"rushstats {__version__}")
    for name in ANALYSES:
        p.add_argument(
            f"--{name}", action="store_true", help=f"include {name} analysis"
        )
    p.add_argument("--all", action="store_true", help="include all analyses")
    p.add_argument(
        "--correlation-method",
        choices=("pearson", "spearman", "both"),
        default="pearson",
        help="method for --correlation (default: pearson)",
    )
    p.add_argument(
        "--type",
        action="append",
        default=[],
        metavar="COLUMN=TYPE",
        help="override type: integer, float, boolean, categorical; repeatable",
    )
    p.add_argument(
        "--delimiter", default=",", help="single ASCII delimiter (default: comma)"
    )
    p.add_argument(
        "--no-header", action="store_true", help="generate names column_1, column_2, …"
    )
    p.add_argument(
        "--top", type=int, default=10, help="top categories, 1–1000 (default: 10)"
    )
    p.add_argument(
        "--percentiles",
        default="0,25,50,75,100",
        help="comma-separated percentiles from 0 to 100",
    )
    p.add_argument(
        "--trim",
        type=float,
        default=0.1,
        help="fraction trimmed from each tail for --robust, 0 <= fraction < 0.5 (default: 0.1)",
    )
    p.add_argument(
        "--group-by",
        action="append",
        default=[],
        metavar="COLUMN",
        help="add grouped reports; repeat for multi-column groups (exact column names)",
    )
    p.add_argument(
        "--max-groups",
        type=int,
        default=100,
        help="maximum number of groups, 1–10000 (default: 100); errors if exceeded",
    )
    p.add_argument("--description", help="dataset description")
    p.add_argument("--target", help="target column label (metadata only)")
    p.add_argument(
        "--date-column", help="date column label (metadata only; dates remain text)"
    )
    p.add_argument(
        "--max-bytes",
        type=int,
        default=512 * 1024 * 1024,
        help="input size limit in bytes (default: 536870912)",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output (default: INPUT_STEM_report.md beside input)",
    )
    p.add_argument("--force", action="store_true", help="replace an existing report")
    p.add_argument("--quiet", action="store_true", help="suppress success output")
    p.add_argument("--verbose", action="store_true", help="show traceback on failure")
    return p


def main(argv: list[str] | None = None) -> int:
    p = parser()
    args = p.parse_args(argv)
    try:
        types = {}
        for override in args.type:
            name, sep, kind = override.rpartition("=")
            if not sep or not name or name in types:
                raise ValueError("--type requires COLUMN=TYPE with no repeated columns")
            types[name] = kind
        selected = [name for name in ANALYSES if getattr(args, name)]
        methods = (
            ["pearson", "spearman"]
            if args.correlation_method == "both"
            else [args.correlation_method]
        )
        output = args.output or args.input.with_name(args.input.stem + "_report.md")
        if output.exists() and not args.force:
            raise FileExistsError(
                f"report already exists: {output}; use --force to replace it"
            )
        result = analyze(
            args.input,
            analyses=["all"] if args.all else selected or None,
            types=types,
            delimiter=args.delimiter,
            headers=not args.no_header,
            top=args.top,
            trim=args.trim,
            group_by=args.group_by,
            max_groups=args.max_groups,
            percentiles=[float(p) for p in args.percentiles.split(",")],
            correlation=methods,
            description=args.description,
            target=args.target,
            date_column=args.date_column,
            max_bytes=args.max_bytes,
        )
        result.to_markdown(output, force=args.force)
        if not args.quiet:
            print(
                f"Analyzed {result.data['rows']:,} rows × {result.data['column_count']} columns. Report written to {output}"
            )
        return 0
    except (OSError, ValueError, TypeError) as error:
        if args.verbose:
            raise
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
