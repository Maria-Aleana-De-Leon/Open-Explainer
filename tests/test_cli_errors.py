"""Common user mistakes: every one ends in a readable `error:` with a `fix:`, a non-zero exit, and no traceback."""
import json
import subprocess
import sys

import pytest

OEX = [sys.executable, "-m", "openexplainer.cli"]


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    d = tmp_path_factory.mktemp("ux") / "g"
    subprocess.run(OEX + ["new", str(d), "--demo"], check=True, capture_output=True)
    return d


def run(*args, cwd=None):
    return subprocess.run(OEX + list(args), capture_output=True, text=True, cwd=cwd)


@pytest.mark.parametrize("args", [
    ["-C", "{d}/nowhere", "plan"],
    ["-C", "{d}", "estimate", "--target", "abc"],
    ["-C", "{d}", "words", "import", "{d}/missing.json"],
    ["-C", "{d}", "render", "--only", "s09"],
    ["-C", "{d}", "qa"],
    ["mascot", "prepare", "{d}/no-such-folder"],
    ["sfx", "--catalog", "{d}/none.json", "find", "whoosh"],
])
def test_mistakes_give_a_clear_error(demo, args):
    r = run(*[a.format(d=demo) for a in args])
    assert r.returncode != 0
    assert "error:" in r.stderr and "fix:" in r.stderr and "Traceback" not in r.stderr + r.stdout


def test_broken_json_points_at_the_line(demo, tmp_path):
    bad = tmp_path / "p"
    subprocess.run(OEX + ["new", str(bad)], check=True, capture_output=True)
    (bad / "project.json").write_text('{"title": "x",}')
    r = run("-C", str(bad), "validate")
    assert r.returncode != 0 and "line 1" in r.stderr and "trailing commas" in r.stderr


def test_unknown_field_suggests_the_right_name(demo, tmp_path):
    cfg = json.loads((demo / "project.json").read_text())
    cfg["styel"] = "paper"
    p = tmp_path / "q"
    subprocess.run(OEX + ["new", str(p), "--demo"], check=True, capture_output=True)
    (p / "project.json").write_text(json.dumps(cfg))
    r = run("-C", str(p), "validate")
    assert r.returncode != 0 and "did you mean 'style'" in r.stderr


def test_new_project_location_warnings(tmp_path, monkeypatch):
    from openexplainer import cli
    assert "temporary folder" in cli.location_warning(tmp_path / "film")      # pytest's tmp is a temp dir
    monkeypatch.setattr(cli, "_is_temp", lambda r: False)                    # pretend tmp_path is durable
    assert cli.location_warning(tmp_path / "film") is None
    repo = tmp_path / "toolkit"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "openexplainer"\n')
    assert "source folder" in cli.location_warning(repo / "examples" / "mine")
    monkeypatch.undo()
    r = run("new", str(tmp_path / "film2"))
    assert r.returncode == 0 and "warning:" in r.stderr and "temporary folder" in r.stderr
