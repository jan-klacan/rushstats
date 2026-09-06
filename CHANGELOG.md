# Changelog

## 0.2.0

- Add unscaled median absolute deviation and configurable symmetric trimmed means.
- Add categorical entropy in bits and dominant-category percentage.
- Add exact duplicate-row counts without dropping observations.
- Add grouped reports with composite keys, explicit missing groups and a group limit.
- Preserve full-dataset column types within each group.

Distribution work prepared for this release:

- Cross-platform wheel builds, installed-wheel tests and source-distribution validation.
- Optional multi-stage Docker image with an unprivileged runtime user.
- Manual TestPyPI/PyPI publishing through Trusted Publishing.
- Contributor guidance, issue templates and release documentation.

## 0.1.0

- Initial Rust/PyO3 engine, Python API and composable command-line interface.
- CSV inference, missing data, descriptive statistics, Pearson/Spearman correlations,
  distributions, categorical summaries, IQR outliers and cardinality.
- Deterministic escaped Markdown and atomic report writes with overwrite protection.
- Fix UTF-8 BOM parsing, extreme IQR fence overflow and export after input removal.

These versions describe repository milestones; they do not imply that corresponding
packages have been published to an index. Verify availability before installing by name.
