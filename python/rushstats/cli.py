"""Composable command-line analyses using Python's standard argparse."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from . import __version__
from .api import ANALYSES, analyze


def paint(text: str, code: str, mode: str, stream) -> str:
    enabled = mode == "always" or (
        mode == "auto"
        and stream.isatty()
        and "NO_COLOR" not in os.environ
        and os.environ.get("TERM") != "dumb"
    )
    # Escape control characters in filenames and errors before displaying them.
    text = "".join(
        c if c in "\n\t" or (ord(c) >= 32 and ord(c) != 127) else repr(c)[1:-1]
        for c in text
    )
    return f"\033[{code}m{text}\033[0m" if enabled else text


class TerminalParser(argparse.ArgumentParser):
    color_mode = "auto"

    def _print_message(self, message, file=None):
        if message:
            stream = file or sys.stderr
            stream.write(paint(message, "36", self.color_mode, stream))


def parser() -> argparse.ArgumentParser:
    p = TerminalParser(
        description="Generate Markdown statistical reports from CSV, one dataset at a time.",
        allow_abbrev=False,
        epilog="Examples: rushstats data.csv --all | rushstats data.csv --describe --correlation -o report.md",
    )
    p.color = False  # Use our colour policy on Python 3.14 as well.
    p.add_argument(
        "input", type=Path, nargs="+", help="UTF-8 CSV files, processed in order"
    )
    p.add_argument("--version", action="version", version=f"rushstats {__version__}")
    for name in ANALYSES:
        p.add_argument(
            f"--{name}",
            action=argparse.BooleanOptionalAction,
            default=False,
            help=f"include {name} analysis",
        )
    p.add_argument(
        "--all",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="include all analyses",
    )
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
        "--no-header",
        action="store_true",
        help="generate names column_1, column_2, …",
    )
    p.add_argument(
        "--header",
        dest="no_header",
        action="store_false",
        help="use the first row as headers (override preset)",
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
    p.add_argument(
        "--output-dir", type=Path, help="existing directory for per-dataset reports"
    )
    p.add_argument("--config", type=Path, help="load a JSON analysis configuration")
    p.add_argument(
        "--save-config",
        type=Path,
        help="save effective settings after successful analysis (new file only)",
    )
    p.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="terminal colour policy (default: auto; respects NO_COLOR)",
    )
    p.add_argument(
        "--continue-on-error",
        action="store_true",
        help="continue batch after a dataset fails; still exit with status 1",
    )
    p.add_argument(
        "--force",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="replace an existing report",
    )
    p.add_argument(
        "--quiet",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="suppress success output",
    )
    p.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="show traceback on failure",
    )
    return p


# Presets deliberately exclude paths and operational flags such as --force.
CONFIG_KEYS = (
    *ANALYSES,
    "all",
    "correlation_method",
    "type",
    "delimiter",
    "no_header",
    "top",
    "percentiles",
    "trim",
    "group_by",
    "max_groups",
    "description",
    "target",
    "date_column",
    "max_bytes",
)


def load_config(path: Path, p: argparse.ArgumentParser) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {"version", "options"}:
        raise ValueError("configuration requires version and options")
    if type(payload["version"]) is not int or payload["version"] != 1:
        raise ValueError("unsupported configuration version; expected 1")
    options = payload["options"]
    if not isinstance(options, dict) or set(options) - set(CONFIG_KEYS):
        raise ValueError("configuration contains unknown options")
    actions = {a.dest: a for a in p._actions}
    for key, value in options.items():
        action = actions[key]
        default = action.default
        expected = type(default) if default is not None else str
        if type(value) is not expected and not (value is None and default is None):
            raise ValueError(f"invalid configuration type for {key}")
        if isinstance(value, list) and any(not isinstance(v, str) for v in value):
            raise ValueError(f"{key} must contain strings")
        if action.choices and value not in action.choices:
            raise ValueError(f"invalid configuration choice for {key}")
    return options


def save_config(path: Path, args: argparse.Namespace) -> None:
    payload = {
        "version": 1,
        "options": {key: getattr(args, key) for key in CONFIG_KEYS},
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def same_path(left: Path, right: Path) -> bool:
    return left.resolve() == right.resolve() or (
        left.exists() and right.exists() and os.path.samefile(left, right)
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = parser()
    bootstrap = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    bootstrap.add_argument("--config", type=Path)
    bootstrap.add_argument(
        "--color", choices=("auto", "always", "never"), default="auto"
    )
    initial, _ = bootstrap.parse_known_args(argv)
    p.color_mode = initial.color
    try:
        if initial.config and not any(v in argv for v in ("--help", "-h", "--version")):
            options = load_config(initial.config, p)
            # An explicit analysis selection replaces the saved selection as a unit.
            explicit = {v.split("=", 1)[0] for v in argv}
            if any(f"--{key}" in explicit for key in (*ANALYSES, "all")):
                options.update({key: False for key in (*ANALYSES, "all")})
            # Repeated list flags replace, rather than append to, saved lists.
            for key in ("type", "group_by"):
                if "--" + key.replace("_", "-") in explicit:
                    options[key] = []
            p.set_defaults(**options)
        args = p.parse_args(argv)
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
        if args.output and (len(args.input) != 1 or args.output_dir):
            raise ValueError(
                "--output requires one dataset and cannot be combined with --output-dir"
            )
        if args.output_dir and not args.output_dir.is_dir():
            raise ValueError("--output-dir must be an existing directory")
        outputs = [
            args.output
            or (args.output_dir or source.parent) / (source.stem + "_report.md")
            for source in args.input
        ]
        protected = args.input + ([args.config] if args.config else [])
        for index, output in enumerate(outputs):
            if not output.parent.is_dir():
                raise ValueError(
                    f"report destination directory must already exist: {output.parent}"
                )
            if any(same_path(output, path) for path in protected):
                raise ValueError(
                    "output must not replace an input dataset or configuration"
                )
            if any(same_path(output, previous) for previous in outputs[:index]):
                raise ValueError(
                    "datasets produce the same output path; use distinct filenames"
                )
            if output.exists() and not args.force:
                raise FileExistsError(
                    f"report already exists: {output}; use --force to replace it"
                )
        if args.save_config:
            if args.save_config.exists() or any(
                same_path(args.save_config, path) for path in protected + outputs
            ):
                raise FileExistsError(
                    "--save-config requires a new path distinct from inputs and reports"
                )
            if not args.save_config.parent.is_dir():
                raise ValueError(
                    "configuration destination directory must already exist"
                )
        failures = 0
        for index, (source, output) in enumerate(zip(args.input, outputs), 1):
            try:
                if not args.quiet:
                    print(
                        paint(
                            f"[{index}/{len(args.input)}] Analyzing {source}",
                            "36",
                            args.color,
                            sys.stdout,
                        )
                    )
                result = analyze(
                    source,
                    analyses=["all"] if args.all else selected or None,
                    types=types,
                    delimiter=args.delimiter,
                    headers=not args.no_header,
                    top=args.top,
                    trim=args.trim,
                    group_by=args.group_by,
                    max_groups=args.max_groups,
                    percentiles=[float(v) for v in args.percentiles.split(",")],
                    correlation=methods,
                    description=args.description,
                    target=args.target,
                    date_column=args.date_column,
                    max_bytes=args.max_bytes,
                )
                result.to_markdown(output, force=args.force)
                if not args.quiet:
                    print(
                        paint(
                            f"Analyzed {result.data['rows']:,} rows × {result.data['column_count']} columns. Report written to {output}",
                            "32",
                            args.color,
                            sys.stdout,
                        )
                    )
            except (OSError, ValueError, TypeError) as error:
                if args.verbose:
                    raise
                failures += 1
                print(
                    paint(f"Error: {source}: {error}", "31", args.color, sys.stderr),
                    file=sys.stderr,
                )
                if not args.continue_on_error:
                    break
        if len(args.input) > 1 and not args.quiet:
            print(
                paint(
                    f"Batch: {index - failures} succeeded, {failures} failed, {len(args.input) - index} skipped.",
                    "33" if failures else "32",
                    args.color,
                    sys.stdout,
                )
            )
        if failures:
            return 1
        if args.save_config:
            save_config(args.save_config, args)
            if not args.quiet:
                print(
                    paint(
                        f"Configuration saved to {args.save_config}",
                        "32",
                        args.color,
                        sys.stdout,
                    )
                )
        return 0
    except (OSError, ValueError, TypeError) as error:
        if "args" in locals() and args.verbose:
            raise
        print(
            paint(f"Error: {error}", "31", initial.color, sys.stderr), file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
