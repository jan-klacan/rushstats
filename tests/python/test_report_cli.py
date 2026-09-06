import csv
import io
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from rushstats import __version__, analyze
from rushstats.report import escape


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "rushstats", *map(str, args)],
        capture_output=True,
        text=True,
    )


def test_cli_all_and_overwrite(csv_file, tmp_path):
    source = csv_file("x,city\n1,Paris\n2,London\n")
    output = tmp_path / "report.md"
    run = cli(source, "--all", "--correlation-method", "both", "-o", output)
    assert run.returncode == 0, run.stderr
    text = output.read_text(encoding="utf-8")
    for title in (
        "Dataset Overview",
        "Descriptive Statistics",
        "Missing Data",
        "Correlations",
        "Distributions",
        "Categorical Variables",
        "IQR Outliers",
        "Cardinality",
        "Methodology",
    ):
        assert f"## {title}" in text
    assert cli(source, "-o", output).returncode == 1
    assert output.read_text(encoding="utf-8") == text
    assert (
        cli(
            source,
            "--all",
            "--correlation-method",
            "both",
            "-o",
            output,
            "--force",
            "--quiet",
        ).stdout
        == ""
    )
    assert output.read_text(encoding="utf-8") == text


def test_default_selection(csv_file):
    source = csv_file("x\n1\n2\n")
    run = cli(source)
    assert run.returncode == 0
    text = source.with_name("data_report.md").read_text(encoding="utf-8")
    assert "## Descriptive Statistics" in text
    assert "## Correlations" not in text


def test_cli_errors(tmp_path, csv_file):
    run = cli(tmp_path / "missing.csv")
    assert run.returncode == 1 and "Error:" in run.stderr
    assert "Traceback" not in run.stderr
    assert cli("--nonsense").returncode == 2
    assert cli("--help").returncode == 0
    assert __version__ in cli("--version").stdout
    p = csv_file("x\n1\n")
    assert cli(p, "--type", "bad").returncode == 1
    assert cli(p, "--type", "x=float", "--type", "x=integer").returncode == 1


def test_markdown_safety(csv_file):
    name = "|*_`#[x]\\! <script>alert(1)</script>\n東京"
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([name])
    writer.writerow(["[click](javascript:alert(1))|<img src=x>"])
    report = analyze(
        csv_file(buf.getvalue()), analyses=["all"], description="<script>evil</script>"
    ).to_markdown()
    assert "<script>" not in report and "<img" not in report
    assert "[click]" not in report
    assert "&#124;" in report and "東京" in report
    assert "&#96;" in escape("`")
    assert "&amp;" in escape("&#124;")
    assert "<br>" in report


def test_atomic_write_protection(csv_file, tmp_path):
    source = csv_file("x\n1\n")
    result = analyze(source)
    with pytest.raises(ValueError, match="input dataset"):
        result.to_markdown(source, force=True)
    link = tmp_path / "link.csv"
    link.symlink_to(source)
    with pytest.raises(ValueError):
        result.to_markdown(link, force=True)
    output = tmp_path / "report.md"

    def write():
        try:
            result.to_markdown(output)
            return True
        except FileExistsError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: write(), range(2))) == [False, True]
    assert output.read_text(encoding="utf-8") == result.to_markdown()
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "data.csv",
        "link.csv",
        "report.md",
    ]


def test_no_numeric_columns(csv_file):
    r = analyze(csv_file("city\nParis\nLondon\n"), analyses=["all"])
    assert "No numeric columns." in r.to_markdown()
    assert "No applicable columns." in r.to_markdown()


def test_export_after_input_removed(csv_file, tmp_path):
    source = csv_file("x\n1\n2\n")
    result = analyze(source)
    source.unlink()
    output = tmp_path / "report.md"
    output.write_text("old", encoding="utf-8")
    result.to_markdown(output, force=True)
    assert output.read_text(encoding="utf-8") == result.to_markdown()
    with pytest.raises(ValueError, match="input dataset"):
        result.to_markdown(source, force=True)


def test_installed_package_identity():
    from importlib.metadata import distribution

    import rushstats

    dist = distribution("rushstats")
    assert dist.version == rushstats.__version__
    assert any(
        e.name == "rushstats" and e.value == "rushstats.cli:main"
        for e in dist.entry_points
    )


def test_cli_new_analyses_and_grouping(csv_file, tmp_path):
    source = csv_file("g,x\nA,1\nA,1\nA,3\nB,100\n")
    output = tmp_path / "grouped.md"
    result = cli(
        source,
        "--robust",
        "--duplicates",
        "--categorical",
        "--trim",
        "0.2",
        "--group-by",
        "g",
        "--max-groups",
        "2",
        "-o",
        output,
    )
    assert result.returncode == 0, result.stderr
    text = output.read_text(encoding="utf-8")
    for title in ("Robust Statistics", "Duplicate Rows", "Grouped Summaries"):
        assert f"## {title}" in text
    assert "Entropy" in text
    assert "## Descriptive Statistics" not in text
    failed = cli(
        source, "--group-by", "g", "--max-groups", "1", "-o", tmp_path / "too_many.md"
    )
    assert failed.returncode == 1
    assert "max_groups" in failed.stderr
    assert not (tmp_path / "too_many.md").exists()
