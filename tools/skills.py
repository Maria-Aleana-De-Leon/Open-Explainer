"""Build, mirror, lock, install and uninstall the Open Explainer Agent Skills (spec S6).

    python tools/skills.py sync [--check]       build .claude/skills + .agents/skills mirrors in this repo,
                                                skills.lock.json, AGENTS.md + CLAUDE.md (from docs/agent-guide.md)
    python tools/skills.py install --agent claude|codex|both [--dest DIR] [--force]
    python tools/skills.py uninstall --agent claude|codex|both [--dest DIR]
    python tools/skills.py status --agent claude|codex|both [--dest DIR]

Every installed skill folder carries `.oex-manifest.json` (version + sha256 of each file we wrote). Install refuses
to touch a folder without our manifest, or one whose files were edited locally, unless --force. Uninstall removes
only files listed in our manifest. The skills call the `oex` CLI, installed separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "skills"
MANIFEST = ".oex-manifest.json"
TARGETS = {"claude": Path.home() / ".claude" / "skills", "codex": Path.home() / ".codex" / "skills"}
MIRRORS = {"claude": REPO / ".claude" / "skills", "codex": REPO / ".agents" / "skills"}
SKIP = {"__pycache__", ".DS_Store"}


def version() -> str:
    for line in (REPO / "pyproject.toml").read_text().splitlines():
        if line.startswith("version"):
            return line.split("=")[1].strip().strip('"')
    return "0"


def _files(root: Path) -> dict[str, bytes]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not (set(p.relative_to(root).parts) & SKIP) and p.name != MANIFEST:
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


def _bundled_doc(text: str) -> str:
    """Rewrite docs/mascot links so they resolve inside mascot-prep/references/ (prompts are bundled, images not)."""
    text = text.replace("](../../prompts/", "](prompts/")
    return re.sub(r"!\[([^\]]*)\]\(img/([^)]+)\)", r"*(Image in the Open Explainer repository: `docs/mascot/img/\2`: \1)*",
                  text)


def build() -> dict[str, dict[str, bytes]]:
    """skill name -> {relative path: bytes}, with mascot prompts and guides bundled into mascot-prep."""
    skills = {}
    for d in sorted(p for p in SRC.iterdir() if (p / "SKILL.md").exists()):
        files = _files(d)
        if d.name == "mascot-prep":
            for rel, b in _files(REPO / "prompts").items():
                files[f"references/prompts/{rel}"] = b
            for doc in ("GUIDE.md", "ASSETS.md"):
                files[f"references/{doc}"] = _bundled_doc((REPO / "docs" / "mascot" / doc).read_text()).encode()
        skills[d.name] = files
    return skills


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def tree_hash(files: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode() + b"\0" + sha(files[rel]).encode() + b"\n")
    return h.hexdigest()


def guide_text(name: str) -> str:
    g = (REPO / "docs" / "agent-guide.md").read_text()
    return g if name == "AGENTS.md" else g.replace("# Open Explainer: guide for AI agents",
                                                   "# Open Explainer: guide for AI agents (Claude Code)", 1)


def sync(check: bool) -> int:
    skills = build()
    problems = []
    wanted: dict[Path, bytes] = {}
    for root in MIRRORS.values():
        for name, files in skills.items():
            for rel, b in files.items():
                wanted[root / name / rel] = b
    lock = {"version": version(), "skills": {n: {"files": len(f), "sha256": tree_hash(f)} for n, f in skills.items()}}
    wanted[REPO / "skills.lock.json"] = (json.dumps(lock, indent=1) + "\n").encode()
    for name in ("AGENTS.md", "CLAUDE.md"):
        wanted[REPO / name] = guide_text(name).encode()
    for p, b in wanted.items():
        if check:
            if not p.exists() or p.read_bytes() != b:
                problems.append(f"out of date: {p.relative_to(REPO)}")
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b)
    for root in MIRRORS.values():
        if root.exists():
            for p in root.rglob("*"):
                if p.is_file() and p not in wanted:
                    if check:
                        problems.append(f"stale file: {p.relative_to(REPO)}")
                    else:
                        p.unlink()
    for p in problems:
        print(p)
    print(f"{'checked' if check else 'synced'} {len(skills)} skills, {len(wanted)} files; {len(problems)} problem(s)")
    return 1 if problems else 0


def _manifest(d: Path) -> dict | None:
    f = d / MANIFEST
    return json.loads(f.read_text()) if f.exists() else None


def _modified(d: Path, man: dict) -> list[str]:
    return [rel for rel, h in man["files"].items() if not (d / rel).exists() or sha((d / rel).read_bytes()) != h]


def install(dest: Path, force: bool) -> int:
    skills = build()
    for name in skills:
        d = dest / name
        if d.exists():
            man = _manifest(d)
            if man is None and not force:
                print(f"{d} exists and was not installed by Open Explainer. Move it aside or use --force.")
                return 1
            if man and _modified(d, man) and not force:
                print(f"{d} has local edits ({', '.join(_modified(d, man)[:3])}). Keep a copy, then use --force.")
                return 1
    for name, files in skills.items():
        d = dest / name
        if d.exists():
            man = _manifest(d)
            if man:
                for rel in man["files"]:
                    (d / rel).unlink(missing_ok=True)
            else:
                shutil.rmtree(d)
        for rel, b in files.items():
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_bytes(b)
        (d / MANIFEST).write_text(json.dumps({"tool": "open-explainer", "version": version(),
                                              "files": {r: sha(b) for r, b in files.items()}}, indent=1))
        print(f"installed {name} -> {d}")
    return 0


def uninstall(dest: Path) -> int:
    for name in build():
        d = dest / name
        man = _manifest(d) if d.exists() else None
        if not man:
            continue
        edited = set(_modified(d, man))
        for rel in man["files"]:
            if rel not in edited:              # never delete a file the user changed
                (d / rel).unlink(missing_ok=True)
        if edited:
            print(f"kept {len(edited)} edited file(s) in {d}: {', '.join(sorted(edited))}")
        (d / MANIFEST).unlink()
        for p in sorted(d.rglob("*"), key=lambda p: -len(p.parts)):
            if p.is_dir() and not any(p.iterdir()):
                p.rmdir()
        if d.exists() and not any(d.iterdir()):
            d.rmdir()
        print(f"removed {name} from {dest}" + (" (kept files that were not ours)" if d.exists() else ""))
    return 0


def status(dest: Path) -> int:
    skills = build()
    bad = 0
    for name, files in skills.items():
        d = dest / name
        man = _manifest(d) if d.exists() else None
        if not d.exists():
            st = "missing"
        elif man is None:
            st = "foreign (not installed by Open Explainer)"
        elif _modified(d, man):
            st = "modified locally"
        elif man["files"] != {r: sha(b) for r, b in files.items()}:
            st = f"outdated (installed {man['version']})"
        else:
            st = "ok"
        bad += st != "ok"
        print(f"  {name:<20} {st}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("action", choices=["sync", "install", "uninstall", "status"])
    ap.add_argument("--agent", choices=["claude", "codex", "both"])
    ap.add_argument("--dest")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.action == "sync":
        return sync(a.check)
    if not a.agent:
        ap.error("--agent is required")
    agents = ["claude", "codex"] if a.agent == "both" else [a.agent]
    if a.dest and len(agents) > 1:
        ap.error("--dest works with one --agent")
    rc = 0
    for ag in agents:
        dest = Path(a.dest).expanduser() if a.dest else TARGETS[ag]
        print(f"[{ag}] {dest}")
        rc |= {"install": lambda: install(dest, a.force), "uninstall": lambda: uninstall(dest),
               "status": lambda: status(dest)}[a.action]()
    if a.action == "install":
        if not shutil.which("oex"):
            print(f"\nThe skills call `oex`. Install it once:  uv tool install '{REPO}[transcribe]'")
        print("Restart Claude Code / Codex so they load the skills.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
