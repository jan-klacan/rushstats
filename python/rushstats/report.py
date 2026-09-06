"""Formatting only: the renderer never calculates dataset statistics."""

from __future__ import annotations

import html
from collections.abc import Iterable
from typing import Any


def escape(value: Any) -> str:
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    parts = []
    for char in text:
        if char == "\n":
            parts.append("<br>")
        elif char == "\t":
            parts.append(" ")
        elif char in "\\`*_{}[]()#+-.!|~" or ord(char) < 32:
            parts.append(f"&#{ord(char)};")
        else:
            parts.append(html.escape(char, quote=True))
    return "".join(parts)


def cell(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return format(value, ".6g") if value else "0"
    return escape(value)


def table(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    headers = list(headers)
    lines = [
        "| " + " | ".join(map(escape, headers)) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(map(cell, row)) + " |" for row in rows)
    return "\n".join(lines)


def render(data: dict[str, Any]) -> str:
    parts = ["# Dataset Statistical Report"]
    if data.get("description"):
        parts.append(escape(data["description"]))
    for key in ("target", "date_column"):
        if data.get(key) is not None:
            parts.append(
                f"{key.replace('_', ' ').title()} (metadata only): {escape(data[key])}"
            )
    if "overview" in data["analyses"]:
        parts.extend(
            [
                "## Dataset Overview",
                table(
                    ["Property", "Value"],
                    [
                        ["Rows", data["rows"]],
                        ["Columns", data["column_count"]],
                        ["Missing values", data["total_missing"]],
                    ],
                ),
                "## Column Overview",
                table(
                    ["Column", "Type", "Non-missing", "Missing"],
                    (
                        [c["name"], c["type"], c["count"], c["missing"]]
                        for c in data["columns"]
                    ),
                ),
            ]
        )
    sections = data["sections"]
    layouts = {
        "describe": (
            "Descriptive Statistics",
            [
                ("name", "Column"),
                ("count", "Count"),
                ("missing", "Missing"),
                ("mean", "Mean"),
                ("std", "Std"),
                ("variance", "Variance"),
                ("min", "Min"),
                ("q1", "Q1"),
                ("median", "Median"),
                ("q3", "Q3"),
                ("max", "Max"),
                ("range", "Range"),
                ("iqr", "IQR"),
            ],
        ),
        "missing": (
            "Missing Data",
            [
                ("name", "Column"),
                ("count", "Non-missing"),
                ("missing", "Missing"),
                ("missing_percentage", "Missing %"),
                ("total", "Total"),
            ],
        ),
        "distribution": (
            "Distributions",
            [
                ("name", "Column"),
                ("count", "Count"),
                ("unique", "Unique"),
                ("zeros", "Zeros"),
                ("skewness", "Skewness"),
                ("excess_kurtosis", "Excess kurtosis"),
                ("q1", "Q1"),
                ("median", "Median"),
                ("q3", "Q3"),
            ],
        ),
        "outliers": (
            "IQR Outliers",
            [
                ("name", "Column"),
                ("lower", "Lower bound"),
                ("upper", "Upper bound"),
                ("count", "Outliers"),
                ("percentage", "Outliers %"),
            ],
        ),
        "cardinality": (
            "Cardinality",
            [
                ("name", "Column"),
                ("count", "Non-missing"),
                ("missing", "Missing"),
                ("unique", "Unique"),
                ("unique_percentage", "Unique %"),
                ("constant", "Constant"),
                ("likely_identifier", "Likely identifier (heuristic)"),
            ],
        ),
    }
    for name in (
        "describe",
        "missing",
        "correlation",
        "distribution",
        "categorical",
        "outliers",
        "cardinality",
    ):
        if name not in sections:
            continue
        section = sections[name]
        if name in layouts:
            title, fields = layouts[name]
            parts.append(f"## {title}")
            parts.append(
                table(
                    [title for _, title in fields],
                    ([row[key] for key, _ in fields] for row in section),
                )
                if section
                else "No applicable columns."
            )
            if name == "describe" and section:
                parts.extend(
                    [
                        "### Selected Percentiles",
                        table(
                            ["Column", "Percentile", "Value"],
                            (
                                [row["name"], q["percentile"], q["value"]]
                                for row in section
                                for q in row["percentiles"]
                            ),
                        ),
                    ]
                )
        elif name == "correlation":
            parts.append("## Correlations")
            for method, matrix in section.items():
                parts.append(f"### {method.title()}")
                names = matrix["columns"]
                if not names:
                    parts.append("No numeric columns.")
                    continue
                parts.append(
                    table(
                        ["Column", *names],
                        (
                            [col, *(v["value"] for v in row)]
                            for col, row in zip(names, matrix["cells"])
                        ),
                    )
                )
                parts.extend(
                    [
                        "Complete-pair counts:",
                        table(
                            ["Column", *names],
                            (
                                [col, *(v["count"] for v in row)]
                                for col, row in zip(names, matrix["cells"])
                            ),
                        ),
                    ]
                )
                undefined = [
                    [names[i], names[j], v["reason"]]
                    for i, row in enumerate(matrix["cells"])
                    for j, v in enumerate(row)
                    if j >= i and v["reason"]
                ]
                if undefined:
                    parts.append(
                        table(["Column A", "Column B", "Not defined"], undefined)
                    )
        else:
            parts.append("## Categorical Variables")
            if not section:
                parts.append("No categorical or boolean columns.")
            for row in section:
                parts.extend(
                    [
                        f"### {escape(row['name'])}",
                        table(
                            ["Count", "Missing", "Unique", "Mode", "Mode count"],
                            [
                                [
                                    row[k]
                                    for k in (
                                        "count",
                                        "missing",
                                        "unique",
                                        "mode",
                                        "mode_count",
                                    )
                                ]
                            ],
                        ),
                        table(
                            ["Category", "Count", "Percentage"],
                            (
                                [r["value"], r["count"], r["percentage"]]
                                for r in row["top"]
                            ),
                        ),
                    ]
                )
    parts.extend(
        [
            "## Methodology",
            METHODOLOGY,
            "## Notes",
            "— means undefined, insufficient observations, or a result outside the finite float64 range. "
            "All-missing columns have unknown type unless overridden. Dates remain text. "
            "Numeric calculations use float64; integers beyond 2^53 may lose precision. "
            "Outliers and identifier suggestions are heuristics, not proof of data errors. "
            "Duplicate rows are retained; duplicate-row counting is not performed.",
        ]
    )
    return "\n\n".join(parts) + "\n"


METHODOLOGY = """- Missing tokens: empty/whitespace-only, NA, N/A, null, NaN (case-insensitive after trimming). No imputation.
- Count excludes missing values. Missing percentages use all rows; category, outlier and unique percentages use non-missing observations.
- Variance and standard deviation use the sample denominator n−1. Quantiles use Hyndman–Fan type 7 (linear interpolation at (n−1)p).
- Pearson uses centered complete pairs. Spearman ranks those same pairs with average ranks for ties, then applies Pearson. Constant paired columns and fewer than two pairs give undefined correlation. Pairwise deletion can yield a matrix that is not positive semidefinite.
- Skewness is adjusted Fisher–Pearson: sqrt(n(n−1))/(n−2) × m3/m2^(3/2), for n≥3. Excess kurtosis is (n−1)/((n−2)(n−3)) × ((n+1)(m4/m2²−3)+6), for n≥4. Here mk is the mean kth centered power. Both are undefined for constant columns.
- Outliers lie strictly outside Q1−1.5×IQR and Q3+1.5×IQR. A likely identifier has at least 20 rows, no missing values and all values unique; this never changes its type.
- Numeric uniqueness compares float64 values (signed zeros are equal); boolean values are case-normalized; categorical strings preserve whitespace and case. Category ties sort lexicographically.
- Reports use six significant digits and a fixed section order, with no timestamp."""
