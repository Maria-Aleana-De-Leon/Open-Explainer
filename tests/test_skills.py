"""Agent Skills checks: the rules of the Agent Skills spec (as enforced by anthropics/skills quick_validate.py:
allowed keys, kebab-case name <= 64, description <= 1024 without angle brackets) plus our own: the name matches
the folder, SKILL.md stays short, every referenced local file exists, and every `oex` subcommand mentioned exists."""
import re
from pathlib import Path

import pytest

from openexplainer.cli import build_parser

ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted(p for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").exists())
ALLOWED = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}


def frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert m, "no YAML frontmatter"
    fm = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    return fm, m.group(2)


def test_six_skills_exist():
    assert [p.name for p in SKILLS] == ["explainer-director", "mascot-prep", "render-qa", "sound-designer",
                                        "storyboard-builder", "voice-sync"]


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.name)
def test_skill_frontmatter_and_size(skill):
    fm, body = frontmatter((skill / "SKILL.md").read_text())
    assert set(fm) <= ALLOWED
    assert fm["name"] == skill.name and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fm["name"]) and len(fm["name"]) <= 64
    assert 50 < len(fm["description"]) <= 1024 and "<" not in fm["description"] and ">" not in fm["description"]
    assert len(body.splitlines()) < 120, "keep SKILL.md focused; move detail to references/"
    assert (skill / "agents" / "openai.yaml").exists()


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.name)
def test_skill_references_and_commands_exist(skill):
    text = (skill / "SKILL.md").read_text()
    for ref in re.findall(r"`(references/[\w./-]+\.md)`", text):
        bundled = ref.startswith(("references/GUIDE", "references/ASSETS", "references/prompts"))
        assert bundled or (skill / ref).exists(), ref
    sub = build_parser()._subparsers._group_actions[0].choices
    for cmd in re.findall(r"`oex (?:-C \S+ )?(?:--catalog \S+ )?([a-z][a-z-]*)", text):
        assert cmd in sub, f"`oex {cmd}` mentioned in {skill.name} does not exist"


def _skills_tool(*args):
    import subprocess
    import sys
    return subprocess.run([sys.executable, str(ROOT / "tools" / "skills.py"), *args], capture_output=True, text=True)


def test_repo_mirrors_lock_and_standing_guides_are_in_sync():
    r = _skills_tool("sync", "--check")
    assert r.returncode == 0, r.stdout + r.stderr
    for mirror in (".claude/skills", ".agents/skills"):
        assert sorted(p.name for p in (ROOT / mirror).iterdir()) == [p.name for p in SKILLS]
    assert (ROOT / "AGENTS.md").read_text().startswith("# Open Explainer: guide for AI agents")


def test_install_detects_local_edits_and_uninstall_keeps_them(tmp_path):
    assert _skills_tool("install", "--agent", "codex", "--dest", str(tmp_path)).returncode == 0
    assert (tmp_path / "mascot-prep" / "references" / "prompts" / "01-photo-to-mascot.md").exists()
    skill = tmp_path / "render-qa" / "SKILL.md"
    skill.write_text(skill.read_text() + "\nmy note\n")
    st = _skills_tool("status", "--agent", "codex", "--dest", str(tmp_path))
    assert "modified locally" in st.stdout and st.returncode == 1
    assert _skills_tool("install", "--agent", "codex", "--dest", str(tmp_path)).returncode == 1   # refuses
    (tmp_path / "theirs").mkdir()
    assert _skills_tool("uninstall", "--agent", "codex", "--dest", str(tmp_path)).returncode == 0
    assert skill.exists() and "my note" in skill.read_text()          # the user's edit survives
    assert (tmp_path / "theirs").exists() and not (tmp_path / "voice-sync").exists()


def test_install_refuses_foreign_folder(tmp_path):
    (tmp_path / "render-qa").mkdir()
    r = _skills_tool("install", "--agent", "claude", "--dest", str(tmp_path))
    assert r.returncode == 1 and "not installed by Open Explainer" in r.stdout
