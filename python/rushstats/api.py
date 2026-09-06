"""Public API; only summary results cross the Rust/Python boundary."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import _core
from .report import render

ANALYSES = (
    "overview",
    "describe",
    "missing",
    "correlation",
    "distribution",
    "categorical",
    "outliers",
    "cardinality",
)


@dataclass(frozen=True)
class AnalysisResult:
    """Versioned structured summaries. No raw dataset is retained in Python."""

    data: dict[str, Any]

    def to_markdown(
        self, path: str | os.PathLike[str] | None = None, *, force: bool = False
    ) -> str:
        """Render a report; optionally write atomically, refusing existing paths."""
        markdown = render(self.data)
        if path is not None:
            destination = Path(path)
            source = Path(self.data["source"])
            if destination.resolve() == source.resolve() or (
                source.exists()
                and destination.exists()
                and os.path.samefile(destination, source)
            ):
                raise ValueError("output must not replace the input dataset")
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    newline="\n",
                    dir=destination.parent,
                    delete=False,
                ) as handle:
                    temporary = Path(handle.name)
                    handle.write(markdown)
                    handle.flush()
                    os.fsync(handle.fileno())
                if force:
                    os.replace(temporary, destination)
                else:
                    # Atomic no-clobber publication, including concurrent writers.
                    os.link(temporary, destination)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return markdown


def analyze(
    path: str | os.PathLike[str],
    *,
    analyses: Iterable[str] | None = None,
    types: Mapping[str, str] | None = None,
    delimiter: str = ",",
    headers: bool = True,
    correlation: Iterable[str] = ("pearson",),
    percentiles: Iterable[float] = (0, 25, 50, 75, 100),
    top: int = 10,
    description: str | None = None,
    target: str | None = None,
    date_column: str | None = None,
    max_bytes: int = 512 * 1024 * 1024,
) -> AnalysisResult:
    """Analyze a CSV. Invalid data/options raise ValueError; I/O raises OSError.

    `analyses=["all"]` selects every analysis. `types` maps exact column names
    to integer, float, boolean or categorical. Target and date_column are labels
    only and never change parsing or select statistical models.
    """
    source = Path(path).resolve()
    selected = (
        list(analyses) if analyses is not None else ["overview", "describe", "missing"]
    )
    if isinstance(analyses, str) or isinstance(correlation, str):
        raise ValueError("analyses and correlation must be sequences, not strings")
    if selected == ["all"]:
        selected = list(ANALYSES)
    if len(delimiter) != 1 or not delimiter.isascii():
        raise ValueError("delimiter must be one ASCII character")
    options = {
        "load": {
            "delimiter": ord(delimiter),
            "headers": headers,
            "types": dict(types or {}),
            "max_bytes": max_bytes,
        },
        "analyses": selected,
        "correlation": list(correlation),
        "percentiles": list(percentiles),
        "top": top,
    }
    data = json.loads(_core.analyze_json(source, json.dumps(options, allow_nan=False)))
    names = {column["name"] for column in data["columns"]}
    for label, value in (("target", target), ("date_column", date_column)):
        if value is not None and value not in names:
            raise ValueError(f"unknown {label} column: {value!r}")
    data.update(
        source=str(source),
        description=description,
        target=target,
        date_column=date_column,
    )
    return AnalysisResult(data)
