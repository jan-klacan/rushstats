# Contributing to rushstats

Small, focused bug fixes, tests, documentation improvements and statistical modules
are welcome. For a substantial feature, open an issue describing the intended use,
statistical definition and CLI/API behavior before investing in implementation.

## Development

Python 3.10+, stable Rust and a platform C linker are required. From a checkout:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'maturin>=1.14,<2' 'pytest>=8,<10' 'ruff>=0.12,<1'
maturin develop
cargo test --locked
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
python -m pytest -q
ruff check python tests examples scripts
ruff format --check python tests examples scripts
python scripts/check_release.py
```

Windows activation is `.venv\Scripts\activate`. Re-run `maturin develop` after Rust
changes. Tests must exercise the installed extension; no Python statistics fallback
is used. The CI matrix tests wheels on Python 3.10 and 3.14. See the README for the
architecture and `docs/RELEASING.md` for distribution checks.

## Statistical changes

Document the exact estimator, denominator, missing-value strategy, minimum sample
size, handling of ties and constant columns, and numerical limitations. Include a
small manually verifiable example plus meaningful regression or reference tests.
Keep computation in Rust and formatting in Python. Report output must remain
deterministic; escape every user-supplied name, category and group key.

## Pull requests

Explain the user-visible problem and resulting behavior, tests run, and any changes
to report structure or the public result schema. Keep changes focused and update
relevant documentation. Include no real private datasets, credentials or generated
build artifacts. Synthetic fixtures and illustrative reports are welcome.

Contributions are accepted under the project's MIT license. Be respectful, critique
ideas rather than people, and keep discussions relevant and constructive. Maintainers
may moderate abusive or disruptive content. There is no guaranteed response time;
this is a small community project.

For suspected vulnerabilities, follow `SECURITY.md` rather than posting sensitive
material in a public issue.
