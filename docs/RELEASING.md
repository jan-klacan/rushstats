# Releasing rushstats

The project prepares wheels and an sdist. Publishing is deliberately manual and runs
only from a matching `vVERSION` tag; pushing a commit or tag does not publish a package.
No PyPI API token belongs in this repository.

## GitHub Releases (current distribution channel)

No PyPI account is required for this route.

1. Commit the version changes on a feature branch and open a pull request into
   `main`. Wait for the `tests` workflow and merge the PR.
2. Run **Actions → Distribution builds → Run workflow** on the merged commit's
   branch. Wait for all five wheels and the sdist to pass.
3. Download the workflow artifacts and extract their ZIP wrappers. Keep the
   `.whl` files themselves intact.
4. Create a GitHub Release with tag `v0.3.0` targeting the exact commit that was
   built. If `main` has advanced, select the built commit rather than its new tip.
   Attach the five `.whl` files and `rushstats-0.3.0.tar.gz` as release assets.
5. Add the v0.3.0 changelog notes, publish the release, and update README download
   links from v0.2.0 to v0.3.0. Remove the development-version notice at that point.

The automatically generated GitHub source archives are separate from the built
sdist. The **Publish Python package** workflow is unnecessary for GitHub-only releases.

## Optional one-time setup for PyPI/TestPyPI

1. Confirm the PyPI name `rushstats` is available or under your control. PyPI and
   TestPyPI are independent services and require separate accounts/configuration.
2. Create GitHub environments named `testpypi` and `pypi`. Configure deployment
   protection rules and a required reviewer for `pypi` where available. Restrict
   deployment refs to your release tags. An environment name in YAML alone does
   **not** configure these protections.
3. Configure a Trusted Publisher (or pending publisher for a new project) at each
   index: owner `jan-klacan`, repository `rushstats`, workflow `publish.yml`, and
   the corresponding environment name. See
   [PyPI's Trusted Publishing guide](https://docs.pypi.org/trusted-publishers/).
4. Enable private vulnerability reporting in the repository's Security settings.
   Configure branch protection so tests are required before merging to the default
   branch. Review Dependabot updates rather than merging them blindly.

These are account/repository settings; adding the workflow files does not activate
them automatically. Fork maintainers must replace project URLs and publisher identity.

## Prepare a version

Update all four version declarations together:

- `pyproject.toml` (`project.version`)
- `Cargo.toml` (package version)
- `Cargo.lock` (the `rushstats-core` entry; regenerate with Cargo when needed)
- `python/rushstats/__init__.py` (`__version__`)

Add the changelog entry, update versioned examples in Docker/release docs and the
container smoke script's default image tag, and run:

```sh
python scripts/check_release.py --tag v0.3.0
cargo test --locked
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
maturin develop
python -m pytest -q
ruff check python tests examples scripts
ruff format --check python tests examples scripts
```

The result schema uses its own version, independent of the package version. Bump it
only when making incompatible result-schema changes, and document migrations.

## Build and inspect locally

```sh
python -m pip install 'maturin==1.15.0' 'twine>=6,<7'
maturin build --release --locked --strip --out dist
maturin sdist --out dist
python -m twine check dist/rushstats-0.3.0*
```

Use a clean output directory per release; do not mix versions. Also rebuild from the
source archive to catch missing package files:

```sh
python -m pip wheel --no-deps --no-build-isolation \
  dist/rushstats-0.3.0.tar.gz --wheel-dir target/sdist-check
```

Install that wheel in a clean virtual environment, run the test suite and exercise
`rushstats --all --group-by city` against the synthetic example. A native local Linux
wheel is not necessarily portable; the distribution workflow handles manylinux tags.
Test the Docker image separately using `docs/DOCKER.md`.

## Cross-platform build workflow

Run **Distribution builds** in GitHub Actions before publication. It prepares:

| Platform | Wheel target |
| --- | --- |
| Linux x86-64 | manylinux2014 / glibc ≥2.17 |
| Linux ARM64 | manylinux2014 / glibc ≥2.17 |
| macOS Intel | x86_64 |
| macOS Apple Silicon | arm64 |
| Windows x86-64 | amd64 |

The PyO3 stable ABI starts at CPython 3.10. Each wheel is installed and tested on
Python 3.10 and 3.14 on its native runner. The sdist job rebuilds a wheel from the
archive, tests it and validates package metadata. Artifacts are downloadable from
the workflow run. Alpine/musl, Windows ARM64, PyPy and free-threaded CPython wheels
are not in the initial release matrix.

The workflow configuration expresses intended coverage. Only completed successful
runs establish that a particular version works on those platforms. GitHub-hosted
runner availability and runtime costs depend on repository visibility and account.

## Publish

After reviewing the changes and successful checks, commit and push the release, then
create and push its matching version tag. For example, with an already reviewed commit:

```sh
git tag v0.3.0
git push origin v0.3.0
```

Run **Publish Python package** from that tag, first selecting `testpypi`. The workflow
checks version consistency, builds and tests all distributions, and then requests an
OIDC credential only in the publishing job. If using GitHub CLI:

```sh
gh workflow run publish.yml --ref v0.3.0 -f destination=testpypi
```

Verify a TestPyPI installation in a fresh environment:

```sh
python -m pip install --index-url https://test.pypi.org/simple/ \
  --only-binary=:all: --no-deps rushstats==0.3.0
rushstats --version
```

Then run the same workflow on the same tag with destination `pypi` and approve the
protected environment deployment. Existing package versions cannot be overwritten;
fix problems in a new version. The workflow does not use `skip-existing`, so partial
publication failures are visible and require inspection before retrying.

After successful publication, create a GitHub Release with the changelog and links
to distributions, and update the README's publication status and installation
instructions. This workflow does not create GitHub Releases or publish Docker images.
