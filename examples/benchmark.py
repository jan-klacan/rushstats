"""Generate representative data outside the repository and time all analyses."""

import argparse
import csv
import tempfile
import time
from pathlib import Path

from rushstats import analyze


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100_000)
    args = parser.parse_args()
    if args.rows < 1:
        parser.error("rows must be positive")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "benchmark.csv"
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["id", "amount", "quantity", "city", "active"])
            for i in range(args.rows):
                writer.writerow(
                    [
                        i,
                        "" if i % 37 == 0 else (i * 17 % 10000) / 100,
                        i % 19,
                        f"city_{i % 100}",
                        i % 2 == 0,
                    ]
                )
        start = time.perf_counter()
        result = analyze(path, analyses=["all"], correlation=["pearson", "spearman"])
        elapsed = time.perf_counter() - start
        print(
            f"{result.data['rows']:,} rows × {result.data['column_count']} columns; "
            f"{path.stat().st_size / 1024**2:.2f} MiB; {elapsed:.3f} seconds"
        )
        print(f"Markdown: {len(result.to_markdown()):,} characters")


if __name__ == "__main__":
    main()
