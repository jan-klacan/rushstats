import io
import json
import subprocess
import sys

import pytest
from rushstats.cli import main, paint


def cli(*args, env=None):
    return subprocess.run(
        [sys.executable, "-m", "rushstats", *map(str, args)],
        capture_output=True,
        text=True,
        env=env,
    )


def sources(tmp_path):
    paths = [tmp_path / "first.csv", tmp_path / "second.csv"]
    for path in paths:
        path.write_text("g,x\nA,1\nB,3\n", encoding="utf-8")
    return paths


def test_batch_reports_and_order(tmp_path, capsys, monkeypatch):
    import rushstats.cli as module

    paths = sources(tmp_path)
    output = tmp_path / "reports"
    output.mkdir()
    actual = module.analyze
    calls = []

    def recorded(path, **kwargs):
        if calls:
            assert (output / "first_report.md").exists()
        calls.append(path)
        return actual(path, **kwargs)

    monkeypatch.setattr(module, "analyze", recorded)
    assert main([*map(str, paths), "--describe", "--output-dir", str(output)]) == 0
    assert calls == paths
    assert "2 succeeded, 0 failed" in capsys.readouterr().out
    assert all((output / (p.stem + "_report.md")).exists() for p in paths)


@pytest.mark.parametrize("keep_going", [False, True])
def test_batch_failure_policy(tmp_path, keep_going):
    paths = sources(tmp_path)
    paths[0].write_text('x\n"bad', encoding="utf-8")
    # A missing file reliably fails independently of CSV parser tolerance.
    paths[0].unlink()
    run = cli(*paths, *(["--continue-on-error"] if keep_going else []))
    assert run.returncode == 1
    assert (tmp_path / "second_report.md").exists() is keep_going
    assert "1 failed" in run.stdout


def test_preflight_protects_other_inputs_and_collisions(tmp_path):
    paths = sources(tmp_path)
    other = tmp_path / "first_report.md"
    other.write_text("x\n99\n", encoding="utf-8")
    before = other.read_bytes()
    assert cli(paths[0], other, "--force").returncode == 1
    assert other.read_bytes() == before
    assert cli(paths[0], paths[0], "--force").returncode == 1
    assert cli(*paths, "-o", tmp_path / "one.md").returncode == 1
    sub = tmp_path / "sub"
    sub.mkdir()
    duplicate = sub / paths[0].name
    duplicate.write_bytes(paths[0].read_bytes())
    assert cli(paths[0], duplicate, "--output-dir", tmp_path, "--force").returncode == 1


def test_preset_roundtrip_and_overrides(tmp_path):
    first, second = sources(tmp_path)
    config = tmp_path / "settings.json"
    run = cli(
        first, "--all", "--group-by", "g", "--type", "x=float", "--save-config", config
    )
    assert run.returncode == 0, run.stderr
    payload = json.loads(config.read_text())
    assert payload["version"] == 1
    assert (
        not {"input", "output", "force", "save_config", "config"}
        & payload["options"].keys()
    )
    run = cli(
        second, "--config", config, "--describe", "--type", "x=integer", "--quiet"
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout == ""
    report = (tmp_path / "second_report.md").read_text()
    assert "## Descriptive Statistics" in report
    assert "## Correlations" not in report
    assert "integer" in report
    original = config.read_bytes()
    assert cli(second, "--force", "--save-config", config).returncode == 1
    assert config.read_bytes() == original


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"version": 2, "options": {}},
        {"version": True, "options": {}},
        {"version": 1, "options": {"force": True}},
        {"version": 1, "options": {"top": True}},
        {"version": 1, "options": {"type": [1]}},
        {"version": 1, "options": {"all": "yes"}},
        {"version": 1, "options": {"correlation_method": "bad"}},
    ],
)
def test_invalid_presets(tmp_path, payload):
    source = sources(tmp_path)[0]
    config = tmp_path / "invalid.json"
    config.write_text(json.dumps(payload))
    run = cli(source, "--config", config)
    assert run.returncode == 1
    assert "Traceback" not in run.stderr
    assert not (tmp_path / "first_report.md").exists()


def test_config_and_report_paths_cannot_overlap(tmp_path):
    source = sources(tmp_path)[0]
    config = tmp_path / "config.json"
    config.write_text('{"version": 1, "options": {}}')
    assert cli(source, "--config", config, "-o", config, "--force").returncode == 1
    assert cli(source, "--save-config", tmp_path / "first_report.md").returncode == 1
    assert not (tmp_path / "first_report.md").exists()


def test_colours_and_quiet(tmp_path):
    source = sources(tmp_path)[0]
    for mode, expected in [("auto", False), ("never", False), ("always", True)]:
        run = cli(source, "--force", "--color", mode)
        assert run.returncode == 0, run.stderr
        assert ("\x1b[" in run.stdout) is expected
        assert "\x1b[" not in (tmp_path / "first_report.md").read_text()
        assert ("\x1b[" in cli("--help", "--color", mode).stdout) is expected
    run = cli(source, "--force", "--quiet", "--color", "always")
    assert run.stdout == ""
    assert "\x1b[" in cli(tmp_path / "missing.csv", "--color", "always").stderr


def test_auto_color_environment_and_escape(monkeypatch):
    class Terminal(io.StringIO):
        def isatty(self):
            return True

    stream = Terminal()
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")
    assert "\x1b[" in paint("hello", "32", "auto", stream)
    monkeypatch.setenv("NO_COLOR", "")
    assert paint("hello", "32", "auto", stream) == "hello"
    assert "\x1b" not in paint("bad\x1b[2J", "32", "never", stream)


def test_header_override(tmp_path):
    source = sources(tmp_path)[0]
    config = tmp_path / "header.json"
    config.write_text('{"version": 1, "options": {"no_header": true}}')
    run = cli(source, "--config", config, "--header")
    assert run.returncode == 0, run.stderr
    assert "Analyzed 2 rows" in run.stdout
