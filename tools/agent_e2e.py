"""End-to-end agent tests: can Claude Code / Codex make films using ONLY the skills and the oex CLI?

    python tools/agent_e2e.py --agent claude --scenario short30|edu3min|long6min|vertical_mascot|sound|all [--keep]

Each scenario builds an isolated workspace with the generated project skills (.claude/skills, .agents/skills),
AGENTS.md / CLAUDE.md, a script and its narration (macOS `say` at a natural 165 wpm, local), plus the scenario's
assets (mascot source PNGs, sound library with music) taken from this repo's own original demo assets. The agent
gets one prompt with all approvals pre-given and runs non-interactively. Success is judged from RESULT FILES, never
from the agent's words. Writes <workspace>/agent-e2e.json; appends a line to build-agent-e2e.jsonl in the repo.
Uses the agent account of the person running it (this costs usage).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EX = REPO / "examples"
CATS = [
    "Why do cats always land on their feet? It looks like magic, but it is physics.",
    "As a cat falls, it turns its front half first, then swings its back half around to follow.",
    "It can do this because its spine is very flexible and it has no fixed collarbone.",
    "So next time a cat lands perfectly, you will know the trick. Thanks for watching.",
]


def says(example: str) -> list[str]:
    return [s["say"] for s in json.loads((EX / example / "storyboard.json").read_text())["scenes"]]


SCENARIOS = {
    "short30": {"script": CATS, "format": "16:9", "style": "midnight", "extras": "no mascot, no music, no sound effects",
                "range": (15, 45)},
    "edu3min": {"script": says("gps-3min"), "format": "16:9", "style": "paper",
                "extras": "no mascot, no music, no sound effects", "range": (162, 198)},
    "long6min": {"script": says("power-6min"), "format": "16:9", "style": "chalk",
                 "extras": "no mascot and no sound effects; background music: ./library/music/calm-loop.wav "
                           "(licence: MIT, made for this toolkit)", "range": (300, 360), "assets": ["library"]},
    "vertical_mascot": {"script": says("mascot-30s"), "format": "9:16", "style": "midnight",
                        "extras": "a talking mascot: the user's approved mascot images are in ./mascot (prepare them "
                                  "with the toolkit first and use its gestures where they fit the words); no music, "
                                  "no sound effects", "range": (20, 40), "assets": ["mascot"]},
    "sound": {"script": says("email-30s"), "format": "16:9", "style": "pop",
              "extras": "no mascot; background music ./library/music/calm-loop.wav (licence: MIT, made for this "
                        "toolkit) and sound effects from the catalog ./library/catalog.json (automatic placement, "
                        "keep it restrained)", "range": (20, 40), "assets": ["library"]},
}

PROMPT = """Make a short explainer video with the Open Explainer toolkit, using its skills (start with the
explainer-director skill) and the `oex` command, in the folder ./film.

Everything is already decided and approved, so do not ask me questions:
- Narration: ./narration.wav (already recorded, English). The script, one paragraph per scene, is in ./script.txt.
- Format {format}, style "{style}", captions on; {extras}.
- The script and the storyboard are approved; choose fitting scene types and on-screen text yourself.

Work in ./film only (read the other files where they are). Run the preflight and the final render, then look at the
contact sheet and fix anything that looks wrong. When you finish, report the QA result exactly as the tool printed
it, the path of the MP4, and anything you could not fix."""


def build(name: str, sc: dict) -> Path:
    ws = Path(tempfile.mkdtemp(prefix=f"oex-agent-{name}-"))
    for sub in (".claude/skills", ".agents/skills"):
        shutil.copytree(REPO / sub, ws / sub)
    for f in ("AGENTS.md", "CLAUDE.md"):
        shutil.copy(REPO / f, ws / f)
    (ws / "script.txt").write_text("\n\n".join(sc["script"]) + "\n")
    for a in sc.get("assets", []):
        if a == "mascot":   # the original demo character's SOURCE images (not a real-user mascot)
            shutil.copytree(EX / "mascots" / "pip", ws / "mascot", ignore=shutil.ignore_patterns("build", "LICENSE.txt"))
        if a == "library":
            shutil.copytree(EX / "audio", ws / "library")
    with tempfile.TemporaryDirectory() as td:
        aiff = Path(td) / "n.aiff"
        subprocess.run(["say", "-v", "Samantha", "-r", "165", "-o", str(aiff), " [[slnc 500]] ".join(sc["script"])],
                       check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(aiff), "-ar", "48000", str(ws / "narration.wav")],
                       check=True)
    return ws


def verify(ws: Path, sc: dict, rc: int) -> dict:
    film = ws / "film"
    rd = film / "renders"
    mp4s = [p for p in rd.glob("*.mp4") if not p.stem.endswith("-preview")] if rd.exists() else []
    qa = json.loads((film / "build" / "qa.json").read_text()) if (film / "build" / "qa.json").exists() else {}
    tl = json.loads((film / "build" / "timeline.json").read_text()) if (film / "build" / "timeline.json").exists() else {}
    cfg = json.loads((film / "project.json").read_text()) if (film / "project.json").exists() else {}
    sb = json.loads((film / "storyboard.json").read_text()) if (film / "storyboard.json").exists() else {"scenes": []}
    says_all = " ".join(s.get("say", "") for s in sb["scenes"]).lower()
    covered = sum(1 for p in sc["script"] if " ".join(p.lower().split()[:5]).rstrip(",.?!") in says_all)
    want = (1080, 1920) if sc["format"] == "9:16" else (1920, 1080)
    dur = tl.get("duration", 0)
    checks = {"agent exit code 0": rc == 0, "final MP4 rendered": bool(mp4s), "QA ok": bool(qa.get("ok")),
              "VERIFY.md written": bool(list(rd.glob("*.VERIFY.md"))) if rd.exists() else False,
              "storyboard covers every paragraph": covered == len(sc["script"]),
              f"format {sc['format']}": (tl.get("width"), tl.get("height")) == want,
              f"duration in {sc['range'][0]}-{sc['range'][1]} s": sc["range"][0] <= dur <= sc["range"][1]}
    if "mascot" in sc.get("assets", []):
        checks["mascot used (lip sync + at least one gesture)"] = bool(cfg.get("mascot")) and \
            (film / "build" / "mascot-check.json").exists() and \
            len(json.loads((film / "build" / "mascot-check.json").read_text())["changes"]) > 1
    if sc is SCENARIOS["sound"]:
        cr = next(iter(rd.glob("*[!w].credits.json")), None) if rd.exists() else None
        credits = json.loads(cr.read_text()) if cr else {"assets": []}
        kinds = {a["kind"] for a in credits["assets"]}
        checks["music + sound effects used"] = {"music", "sfx"} <= kinds
        checks["credits publish_safe"] = bool(credits.get("publish_safe"))
    review = json.loads((film / "build" / "review.json").read_text()) if (film / "build" / "review.json").exists() else []
    return {"checks": checks, "duration_s": dur, "scenes": [s.get("type") for s in sb["scenes"]],
            "review_findings": [f"{n['level']} {n['area']} {n['where']}: {n['msg']}" for n in review],
            "ok": all(checks.values())}


def run(agent: str, name: str, keep: bool, timeout: int) -> dict:
    sc = SCENARIOS[name]
    ws = build(name, sc)
    env = dict(os.environ, PATH=f"{REPO / '.venv' / 'bin'}:{os.environ['PATH']}", HF_HUB_OFFLINE="1")
    prompt = PROMPT.format(**sc)
    if agent == "claude":
        cmd = ["claude", "-p", prompt, "--output-format", "json", "--max-turns", "120",
               "--allowedTools", "Skill", "Read", "Write", "Edit", "Glob", "Grep",
               "Bash(oex:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(mkdir:*)", "Bash(cp:*)", "Bash(ffprobe:*)"]
    else:
        sys.exit("codex runs are not automated yet: open a workspace in Codex and give it the same prompt")
    t0 = time.time()
    meta = {}
    try:
        r = subprocess.run(cmd, cwd=ws, env=env, capture_output=True, text=True, timeout=timeout)
        (ws / "agent-output.txt").write_text(r.stdout + "\n--- stderr ---\n" + r.stderr)
        rc = r.returncode
        try:
            out = json.loads(r.stdout)
            meta = {"turns": out.get("num_turns"), "cost_usd": out.get("total_cost_usd"),
                    "final_message": (out.get("result") or "")[-1500:]}
        except json.JSONDecodeError:
            pass
    except subprocess.TimeoutExpired:
        (ws / "agent-output.txt").write_text(f"TIMEOUT after {timeout}s")
        rc = -1
    rep = {"agent": agent, "scenario": name, "workspace": str(ws), "seconds": round(time.time() - t0), **meta,
           **verify(ws, sc, rc), "date": time.strftime("%Y-%m-%d %H:%M")}
    (ws / "agent-e2e.json").write_text(json.dumps(rep, indent=1))
    with open(REPO / "build-agent-e2e.jsonl", "a") as f:
        f.write(json.dumps({k: v for k, v in rep.items() if k != "final_message"}) + "\n")
    for k, v in rep["checks"].items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"{name}: {'PASS' if rep['ok'] else 'FAIL'} in {rep['seconds']}s, {meta.get('turns')} turns, "
          f"${meta.get('cost_usd') or 0:.2f} - {ws}")
    return rep


if __name__ == "__main__":
    if not shutil.which("say"):
        sys.exit("this harness voices the scripts with macOS `say`")
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", choices=["claude", "codex"], required=True)
    ap.add_argument("--scenario", choices=[*SCENARIOS, "all"], default="short30")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--timeout", type=int, default=2400)
    a = ap.parse_args()
    names = list(SCENARIOS) if a.scenario == "all" else [a.scenario]
    results = [run(a.agent, n, a.keep, a.timeout) for n in names]
    print(f"\npass rate: {sum(r['ok'] for r in results)}/{len(results)}")
    sys.exit(0 if all(r["ok"] for r in results) else 1)
