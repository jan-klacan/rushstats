"""Check version consistency and optional release-tag identity without importing Rust."""

import argparse
import ast
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="expected release tag, e.g. v0.3.0")
    parser.add_argument("--require-tag", action="store_true")
    args = parser.parse_args()
    versions = {}
    for name in ("Cargo.toml", "pyproject.toml"):
        match = re.search(r'^version = "([^"]+)"$', (ROOT / name).read_text(), re.M)
        if match is None:
            parser.error(f"missing version in {name}")
        versions[name] = match[1]
    module = ast.parse((ROOT / "python/rushstats/__init__.py").read_text())
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        ):
            versions["__version__"] = ast.literal_eval(node.value)
    lock = (ROOT / "Cargo.lock").read_text()
    match = re.search(r'name = "rushstats-core"\nversion = "([^"]+)"', lock)
    if match:
        versions["Cargo.lock"] = match[1]
    if len(versions) != 4 or len(set(versions.values())) != 1:
        parser.error(f"version mismatch: {versions}")
    version = versions["Cargo.toml"]
    if f"## {version}\n" not in (ROOT / "CHANGELOG.md").read_text():
        parser.error(f"missing changelog entry for {version}")
    tag = args.tag
    if args.require_tag and tag is None:
        ref = os.environ.get("GITHUB_REF", "")
        if not ref.startswith("refs/tags/"):
            parser.error("publishing must run from a version tag, not a branch")
        tag = ref.removeprefix("refs/tags/")
    if tag is not None and tag != f"v{version}":
        parser.error(f"tag {tag!r} does not match version v{version}")
    print(f"Release metadata consistent: rushstats {version}")


if __name__ == "__main__":
    main()
