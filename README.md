# rushstats

Generate deterministic Markdown statistical reports from CSV with one command.
Rust parses the data and computes statistics; Python exposes a small API and CLI.
The Python package, import, and command are all named `rushstats`.

```sh
rushstats examples/customers.csv --all -o report.md
```

No Python runtime dependencies, no external service, and no data leaves your machine.
The project is not yet published to PyPI. Install from this checkout or a built wheel.

## Installation

Python 3.10+ is required. Building from source also needs stable Rust/Cargo and a
platform C linker (for example Xcode Command Line Tools on macOS). Installing a
compatible prebuilt wheel needs only Python; end users do not need Rust.

```sh
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install .
rushstats --version
rushstats --help
```

To build and install a wheel explicitly:

```sh
python -m pip install 'maturin>=1.14,<2'
maturin build --release --locked
python -m pip install target/wheels/rushstats-*.whl
```

Wheels are platform specific, with Python's stable ABI starting at Python 3.10.
The package has been tested locally on macOS ARM64 with CPython 3.14; the CI workflow
also defines Linux, macOS and Windows checks. CI results require running that workflow.

## Quick start

```sh
# Default: overview, descriptive statistics, missing data.
rushstats examples/customers.csv

# Comprehensive report, including Pearson correlations.
rushstats examples/customers.csv --all -o customers.md

# Compose analyses and choose both correlation methods.
rushstats examples/customers.csv --describe --correlation --distribution --missing \
  --correlation-method both -o numeric.md

# Preserve a numeric-looking identifier as text; label dataset metadata.
rushstats transactions.csv --type customer_id=categorical \
  --description 'Customer transactions' --target revenue \
  --date-column transaction_date --all -o transactions.md

# Semicolon-separated data without headers, generated names column_1, column_2, …
rushstats readings.csv --delimiter ';' --no-header --describe --percentiles 5,50,95
```

The default report is `INPUT_STEM_report.md` beside the input. Existing output is
refused unless `--force` is given. Writes are atomic, including a concurrent-writer
no-clobber check. Input and output must be different files, even with `--force`.
The destination directory must already exist. `--quiet` suppresses success output;
errors still go to stderr. Exit codes: **0** success, **1** data/I/O/option-value
failure, **2** argparse syntax failure. `--verbose` exposes tracebacks for debugging.

## Analyses and options

With no analysis flags the default is `--overview --describe --missing`. Explicit
analysis flags replace the default selection; `--all` selects everything.

| Flag | Result |
| --- | --- |
| `--overview` | Row/column counts, total missing cells, names, types, per-column counts |
| `--describe` | Count, missing, mean, sample std/variance, min/max/range, Q1/median/Q3/IQR, percentiles |
| `--missing` | Total/non-missing/missing counts and missing percentage |
| `--correlation` | Numeric correlation matrix, complete-pair counts and reasons for undefined entries |
| `--distribution` | Adjusted skewness, excess kurtosis, unique/zero counts and quartiles |
| `--categorical` | Boolean/text/unknown-column counts, cardinality, mode, mode count and top categories |
| `--outliers` | IQR fences, outlier count and percentage |
| `--cardinality` | Unique count/percentage, constant flag, likely-identifier heuristic |
| `--all` | All of the above |
| `--correlation-method pearson\|spearman\|both` | Methods used with `--correlation` or `--all`; default Pearson |
| `--top N` | Top categories, default 10, allowed 1–1000 |
| `--percentiles 0,25,50,75,100` | Additional descriptive output; 0–100 inclusive, at most 100 values |
| `--type COLUMN=TYPE` | Repeatable exact-name override: integer, float, boolean, categorical |
| `--delimiter CHAR` | Single ASCII delimiter; default comma; not quote, NUL, CR or LF |
| `--no-header` | First row is data; generated names start at column_1 |
| `--description TEXT` | Description included in report |
| `--target COLUMN` | Validated column label only; does not fit a model |
| `--date-column COLUMN` | Validated column label only; does not parse dates |
| `--max-bytes N` | Positive input-byte limit, default 536870912 (512 MiB) |
| `-o PATH`, `--output PATH` | Destination Markdown file |
| `--force`, `--quiet`, `--verbose` | Overwrite, quiet success output, debug errors |
| `--help`, `--version` | Usage and version |

Column names containing commas work with `--type 'last, first=categorical'`.
The last `=` separates a column name from its type. Conflicting repeated overrides
are errors. Metadata is escaped like CSV content. Reports contain no timestamps or
absolute input paths, so equivalent input/options produce identical reports.

## Python API

```python
from rushstats import analyze

result = analyze(
    'examples/customers.csv',
    analyses=['overview', 'describe', 'correlation', 'missing'],
    correlation=['pearson', 'spearman'],
    types={'city': 'categorical'},
    percentiles=[5, 25, 50, 75, 95],
    description='Customer sample',
)
markdown = result.to_markdown()              # return a string
result.to_markdown('report.md')              # write and return the same string
result.to_markdown('report.md', force=True)  # explicitly replace
print(result.data['sections']['describe'][0]['mean'])

complete = analyze('examples/customers.csv', analyses=['all'])
```

`analyze` also accepts `delimiter`, `headers`, `top`, `target`, `date_column`, and
`max_bytes`. Paths accept `str` or `os.PathLike`. `ValueError` means invalid data or
options; filesystem failures raise `OSError` subclasses (including `FileNotFoundError`).
The result is a Python dictionary inside `AnalysisResult`, with `schema_version: 1`,
`rows`, `column_count`, `total_missing`, `columns`, `analyses`, and `sections`.
The API also records source/metadata for output protection. Saved summaries can still
be exported after the source file is removed. No input table is copied
into Python. Undefined numeric results are `None`. `data` is mutable for inspection
and downstream integration; callers should not mutate it before rendering.

## CSV rules, types and missing values

The Rust reader supports UTF-8 (with or without a byte-order mark), quoted delimiters, escaped double quotes (`""`),
multiline quoted cells, CRLF/LF, configurable delimiters and optional headers.
Blank physical lines outside quoted fields are ignored. Every record must have the
same width. Headers must be nonempty and unique; they are preserved exactly.
Empty/header-only inputs are errors. All-missing data rows are valid, with unknown
columns. Use explicit tokens such as `NA` for a one-column missing row, because a
completely blank line is ignored. Unterminated quotes, quotes inside unquoted fields,
and trailing characters after a closing quote are rejected, even though some CSV
readers accept them. There are no comment lines or backslash quote escapes.

Missing means empty/whitespace-only or **NA, N/A, null, NaN**, case-insensitive after
trimming. This includes quoted missing tokens. `None`, `unknown`, `-` and arbitrary
strings are not missing. This release does not customize the missing-token set.

Inference examines the **whole column**, excluding missing entries, in this order:

1. No non-missing entries → `unknown`.
2. All entries are `true`/`false`, case-insensitive → `boolean` (0/1 remain numeric).
3. All entries parse as finite float64 → `integer` if all lexical values parse as
   signed 64-bit integers, otherwise `float`.
4. Otherwise → `categorical`.

Numeric and boolean parsing trims whitespace. Categorical values retain original
whitespace and case. Inference never uses the identifier heuristic to change types.
Overrides validate every non-missing entry; invalid casts fail, never coerce to missing.
Dates remain categorical text in this release. Numeric-looking identifiers can lose
leading zeros through numeric interpretation; use a categorical override to retain them.
Infinity and overflowing numeric literals are rejected unless explicitly categorical;
NaN is handled as missing. All numerical calculations use IEEE float64, so integer
values beyond 2^53 and very small decimals may be rounded. Use a categorical override
when exact lexical preservation or exact identifier cardinality is required.

## Statistical methodology

Let n denote non-missing count. There is no imputation or automatic row deduplication.

- **Mean:** centered and scaled compensated summation. **Variance** is the sample
  sum of squared deviations divided by n−1; standard deviation is its square root.
  Both require n≥2. Scaling reduces overflow and cancellation; unrepresentable
  results become undefined instead of leaking NaN/Infinity into the report.
- **Quantiles:** Hyndman–Fan type 7, the default in R and NumPy's `method='linear'`.
  For sorted x, use h=(n−1)p and interpolate adjacent values. Q1/Q3 are p=.25/.75,
  median is p=.5, IQR=Q3−Q1, range=max−min. Quantiles require n≥1.
- **Pearson:** centered dot product divided by centered vector norms. Missingness
  uses **pairwise complete observations**, with a count matrix shown. Fewer than two
  pairs or a constant paired column is undefined, including the diagonal. Pairwise
  deletion can produce a correlation matrix that is not positive semidefinite.
- **Spearman:** filter complete pairs first, assign average ranks for ties within
  those pairs, then calculate Pearson on ranks. Missing values therefore cannot
  influence ranks indirectly.
- **Skewness:** adjusted Fisher–Pearson `sqrt(n(n−1))/(n−2) * m3/m2^(3/2)` for n≥3.
- **Excess kurtosis:** `(n−1)/((n−2)(n−3)) * ((n+1)(m4/m2²−3)+6)` for n≥4.
  Here mk is the mean kth centered power. Both shape statistics are undefined for
  constant columns. Excess kurtosis uses a normal-distribution reference of zero.
- **Outliers:** strictly below Q1−1.5×IQR or above Q3+1.5×IQR; equality is not an
  outlier. If a mathematical fence exceeds float64 range, the fence is displayed
  undefined; counting still compares against the corresponding infinite fence.
  This is a heuristic, not evidence an observation is erroneous.
- **Percentages:** missing percentage uses all rows. Category frequency, outlier
  percentage and unique percentage use non-missing observations. An empty
  denominator is undefined. Top-category percentages need not sum to 100.
- **Uniqueness:** numeric float64 equality, treating +0 and −0 as equal; boolean
  canonical true/false; text exact lexical equality. A constant has exactly one
  distinct non-missing value. Unknown/all-missing columns are not constant.
- **Identifier heuristic:** at least 20 rows, no missing values, every value unique.
  It is reported as a suggestion and does not change types. Categories sort by count
  descending, then lexicographically for ties (the same tie break selects the mode).

Reports use six significant digits. An em dash means undefined, insufficient data,
or outside float64 range. The API retains full float64 precision. All user text is
HTML-escaped and Markdown punctuation is encoded as character references; embedded
HTML, table separators, links and line breaks cannot inject report structure.

## Architecture and performance

```text
Cargo.toml / Cargo.lock     Rust dependencies and reproducible resolution
pyproject.toml              maturin packaging, CLI entry point, Python tools
src/
  lib.rs                   PyO3 boundary, releases GIL during analysis
  error.rs                 invalid-input / operating-system errors
  data.rs                  strict CSV adapter, loader, typed column model
  statistics.rs            reusable numeric algorithms, ranks, correlations
  analysis.rs              validated options, canonical registry/dispatch, summaries
python/rushstats/
  api.py                   public analyze / AnalysisResult, atomic output
  cli.py / __main__.py      argparse, exit codes
  report.py                deterministic renderer (no statistical calculations)
  _core.pyi / py.typed      native signature and typing marker
tests/python/              API, CLI, filesystem, report and adversarial tests
examples/                  sample CSV, sample Markdown, benchmark script
.github/workflows/ci.yml    build, lint and installed-wheel tests
```

A single read parses the CSV in Rust. During loading, column state holds numeric candidates and
category frequency maps. Numeric lexical maps are released before analysis; raw cell strings are not duplicated across the language
boundary. Summaries are serialized with a versioned JSON envelope and decoded in
Python; this small copy keeps Rust ownership and the public API straightforward.
Rust releases the GIL during loading/computation. Report rendering only formats
results. Add new analyses in the registry/dispatcher, with independent statistics
functions and a renderer section. The Rust library can also be used directly.

This is an **in-memory exact engine**, not an out-of-core system. The CSV stream is
read incrementally, but numeric values and category maps remain resident. Memory
can substantially exceed file size for many unique strings and for per-row numeric
storage. The 512 MiB input limit bounds input bytes, not process memory, and can be
adjusted. Do not raise it indiscriminately on memory-constrained machines.
Numeric summaries sort once per column, O(n log n). Pearson is O(k²n), Spearman
O(k²n log n), with O(k²) matrix output; many numeric columns can be expensive.
Category maps use ordered trees, O(n log u) per column, and ranking costs O(u log u).
Selecting fewer analyses skips unrelated statistics, but loading still performs
whole-column inference and gathers frequency maps. Exact duplicate-row counting,
date inference, histograms, custom missing tokens, configuration files and streaming
approximate quantiles are intentionally outside this release.

### Dependencies

Stable releases were checked against upstream documentation on 2026-09-06:

| Dependency | Selection | Reason / license |
| --- | --- | --- |
| [PyO3](https://docs.rs/pyo3/0.29.2/pyo3/) | 0.29.2 | Maintained Rust/Python binding, stable ABI / MIT or Apache-2.0 |
| [csv](https://docs.rs/csv/1.4.0/csv/) | 1.4.0 | Mature CSV parser; strict quote adapter adds validation / MIT or Unlicense |
| [Serde](https://docs.rs/serde/latest/serde/) | 1.x (lock: 1.0.229) | Typed option deserialization / MIT or Apache-2.0 |
| [serde_json](https://docs.rs/serde_json/latest/serde_json/) | 1.x (lock: 1.0.151) | Small structured summary boundary / MIT or Apache-2.0 |
| [maturin](https://pypi.org/project/maturin/) | ≥1.14,<2 (tested 1.15.0) | Standard mixed Rust/Python builds / MIT or Apache-2.0 |

No DataFrame engine or numerical runtime is necessary for these algorithms.
Python uses argparse, dataclasses, JSON and filesystem utilities from the standard
library. Development-only tools are pytest and Ruff. Cargo.lock is tracked; use
`--locked` for release builds. Stable Rust is selected by rust-toolchain.toml.

## Development and validation

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'maturin>=1.14,<2' 'pytest>=8,<10' 'ruff>=0.12,<1'
maturin develop
cargo test --locked
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
python -m pytest -q
ruff check python tests examples
ruff format --check python tests examples

# After editing Rust:
maturin develop
# Release wheel and source distribution:
maturin build --release --locked
maturin sdist
```

To check the actual installed wheel independently of an editable checkout:

```sh
python3 -m venv .venv-wheel
.venv-wheel/bin/python -m pip install target/wheels/rushstats-*.whl pytest
.venv-wheel/bin/python -m pytest -q
.venv-wheel/bin/rushstats examples/customers.csv --all -o /tmp/customers.md
```

Tests compare manually verifiable datasets, sample moments against Python's
`statistics`, tied/pairwise ranks, huge/tiny and constant inputs, invalid CSV,
Unicode and Markdown injection, malformed options, CLI errors and atomic writes.
Markdown escaping is tested in Python because the renderer is Python. Rust unit
tests are colocated with the parser/statistics/analysis modules.

Run a reproducible, generated mixed-data benchmark with an installed release build:

```sh
python examples/benchmark.py --rows 100000
```

The script prints timing and result dimensions; timings are hardware dependent and
are not a performance guarantee. See `examples/customers.md` for the full sample
report. The MIT license is preserved in `LICENSE`.
