"""Exercise a locally built Docker image without network access at runtime."""

import argparse
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="rushstats:0.2.0")
    args = parser.parse_args()

    def run(*command: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, check=check, capture_output=True, text=True)

    uid = run(
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--entrypoint",
        "python",
        args.image,
        "-c",
        "import os; print(os.getuid())",
    ).stdout.strip()
    assert uid == "10001", f"expected non-root UID 10001, got {uid}"
    with tempfile.TemporaryDirectory(prefix="rushstats-container-") as directory:
        root = Path(directory)
        # The default container UID must be able to write to this synthetic fixture.
        root.chmod(0o777)
        source = root / "input.csv"
        source.write_text("group,value\nA,1\nA,1\nB,3\n", encoding="utf-8")
        source.chmod(0o644)
        base = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--mount",
            f"type=bind,source={root},target=/data",
            args.image,
        ]
        command = [
            *base,
            "input.csv",
            "--all",
            "--group-by",
            "group",
            "-o",
            "report.md",
        ]
        run(*command)
        output = root / "report.md"
        report = output.read_text(encoding="utf-8")
        for section in ("Grouped Summaries", "Robust Statistics", "Duplicate Rows"):
            assert f"## {section}" in report
        refusal = run(*command, check=False)
        assert refusal.returncode == 1 and "already exists" in refusal.stderr
        assert output.read_text(encoding="utf-8") == report
        missing = run(*base, "absent.csv", "-o", "missing.md", check=False)
        assert missing.returncode == 1 and "Traceback" not in missing.stderr
    print(
        "Container smoke checks passed: non-root, offline, read-only root, reports, errors"
    )


if __name__ == "__main__":
    main()
