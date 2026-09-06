"""Exercise a locally built Docker image without network access at runtime."""

import argparse
import os
import subprocess
import sys
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
        # Atomic report files are mode 0600. On native Linux, the container must
        # write as the host user so that this process can read its report. Docker
        # Desktop's bind-mount translation can otherwise hide this mismatch.
        user_args = []
        if hasattr(os, "getuid"):
            user_args = ["--user", f"{os.getuid()}:{os.getgid()}"]
        else:
            # Windows has no POSIX UID/GID; Docker Desktop mediates the mount.
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
            *user_args,
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
        if sys.platform.startswith("linux"):
            assert output.stat().st_uid == os.getuid(), (
                "report must belong to the host user"
            )
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
