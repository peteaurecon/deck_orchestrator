#!/usr/bin/env python3
"""
tool-confirmation preflight for deck-orchestrator.

Verifies every system tool, package, skill file and harness capability the
orchestrator needs, before any pipeline stage runs.

Exit codes: 0 = all blocking checks pass, 1 = at least one blocking failure.

Usage:
    python check_environment.py [--skills-root /mnt/skills] [--live]
    --live  also require ANTHROPIC_API_KEY (for MODEL = ClaudeModel() runs)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

BLOCK, WARN, MANUAL = "BLOCK", "WARN", "MANUAL"
results = []  # (severity, name, ok, detail)


def check(severity, name, ok, detail=""):
    results.append((severity, name, bool(ok), detail))


def which(binary):
    return shutil.which(binary)


def run(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return out.returncode == 0, (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr).strip() else ""
    except Exception as e:
        return False, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-root", default="/mnt/skills")
    ap.add_argument("--live", action="store_true",
                    help="require ANTHROPIC_API_KEY (ClaudeModel runs)")
    args = ap.parse_args()
    root = args.skills_root

    # ---------- 1. System binaries ----------
    for b, sev, why in [
        ("python3",  BLOCK, "control spine (orchestrator.py, run_pipeline.py)"),
        ("node",     BLOCK, "assembler.js / PptxGenJS"),
        ("npm",      BLOCK, "installing pptxgenjs"),
        ("pdftoppm", BLOCK, "QA: PDF -> slide images (poppler-utils)"),
    ]:
        p = which(b)
        check(sev, f"binary: {b}", p, p or f"missing - needed for {why}")

    # soffice: direct or via the pptx skill wrapper
    soffice = which("soffice") or which("libreoffice")
    wrapper = os.path.join(root, "public/pptx/scripts/office/soffice.py")
    check(BLOCK, "binary: soffice (LibreOffice)",
          soffice or os.path.isfile(wrapper),
          soffice or (f"via wrapper {wrapper}" if os.path.isfile(wrapper)
                      else "missing - needed for ground-truth render"))

    # extract-text: replaceable, so WARN not BLOCK
    check(WARN, "binary: extract-text", which("extract-text"),
          which("extract-text") or "missing - substitute a python-zipfile text dump for content QA")

    # ---------- 2. Packages ----------
    orch = os.path.join(root, "user/deck-orchestrator")
    local_pgj = os.path.isdir(os.path.join(orch, "node_modules", "pptxgenjs"))
    ok_g, _ = run(["npm", "ls", "-g", "pptxgenjs", "--depth=0"]) if which("npm") else (False, "")
    net_ok, _ = run(["npm", "ping", "--registry", "https://registry.npmjs.org"]) if which("npm") else (False, "")
    check(BLOCK, "package: pptxgenjs", local_pgj or ok_g or net_ok,
          "installed" if (local_pgj or ok_g)
          else ("not installed, but registry reachable - `npm install` in deck-orchestrator/ will fix"
                if net_ok else "not installed and npm registry unreachable"))

    for mod, sev, why in [
        ("PIL",        WARN, "thumbnail.py grids (template analysis only)"),
        ("defusedxml", WARN, "pptx editing path XML parsing"),
        ("jsonschema", WARN, "manifest.schema.json validation (orchestrator degrades gracefully)"),
    ]:
        try:
            __import__(mod)
            check(sev, f"python module: {mod}", True, "importable")
        except ImportError:
            check(sev, f"python module: {mod}", False, f"missing - {why}")

    # ---------- 3. Skill folders and orchestrator files ----------
    skills = {
        "user/deck-orchestrator":            BLOCK,
        "user/dylan-rules":                  BLOCK,
        "user/render-tufte-chart":           BLOCK,
        "user/assess-graphical-excellence":  BLOCK,
        "user/aureconed":                    BLOCK,
        "public/pptx":                       BLOCK,
    }
    for rel, sev in skills.items():
        p = os.path.join(root, rel, "SKILL.md")
        check(sev, f"skill: {rel}", os.path.isfile(p), p if os.path.isfile(p) else "SKILL.md not found")

    for f in ["orchestrator.py", "adapters.py", "run_pipeline.py", "assembler.js",
              "manifest.schema.json", "package.json", "assets/aurecon_logo.png"]:
        p = os.path.join(orch, f)
        check(BLOCK, f"orchestrator file: {f}", os.path.isfile(p),
              "" if os.path.isfile(p) else "missing from deck-orchestrator/")

    # manifest schema parses
    sp = os.path.join(orch, "manifest.schema.json")
    if os.path.isfile(sp):
        try:
            json.load(open(sp))
            check(BLOCK, "manifest.schema.json parses", True)
        except Exception as e:
            check(BLOCK, "manifest.schema.json parses", False, str(e))

    # pptx skill scripts used by the pipeline
    for f in ["scripts/thumbnail.py", "scripts/office/unpack.py",
              "scripts/office/soffice.py", "scripts/clean.py"]:
        p = os.path.join(root, "public/pptx", f)
        check(WARN, f"pptx script: {f}", os.path.isfile(p),
              "" if os.path.isfile(p) else "missing - editing/QA path affected")

    # ---------- 4. Harness capabilities ----------
    # Writable scratch space
    try:
        t = "/home/claude/.tc_writetest" if os.path.isdir("/home/claude") else "./.tc_writetest"
        open(t, "w").close(); os.remove(t)
        check(BLOCK, "harness: writable working dir", True)
    except Exception as e:
        check(BLOCK, "harness: writable working dir", False, str(e))

    if args.live:
        check(BLOCK, "harness: ANTHROPIC_API_KEY", bool(os.environ.get("ANTHROPIC_API_KEY")),
              "required for MODEL = ClaudeModel() in run_pipeline.py")

    # Not programmatically testable - the running agent must attest
    check(MANUAL, "harness: vision (agent can view rendered slide images)", True,
          "attest before proceeding - visual QA is dead without it")
    check(MANUAL, "harness: subagent spawning (QA fresh-eyes, parallel XML edits)", True,
          "attest, or accept degraded in-context QA")

    # ---------- Report ----------
    blocked = [r for r in results if r[0] == BLOCK and not r[2]]
    warned  = [r for r in results if r[0] == WARN and not r[2]]

    w = max(len(r[1]) for r in results)
    print(f"\n{'CHECK'.ljust(w)}  SEV     RESULT")
    print("-" * (w + 22))
    for sev, name, ok, detail in results:
        mark = "PASS" if ok else ("ATTEST" if sev == MANUAL else "FAIL")
        line = f"{name.ljust(w)}  {sev.ljust(6)}  {mark}"
        if detail and (not ok or sev == MANUAL):
            line += f"  ({detail})"
        print(line)

    print()
    if blocked:
        print(f"PREFLIGHT FAILED - {len(blocked)} blocking issue(s). Do not start the pipeline.")
        sys.exit(1)
    if warned:
        print(f"PREFLIGHT PASSED with {len(warned)} warning(s) - degraded paths noted above.")
    else:
        print("PREFLIGHT PASSED - all checks clean.")
    print("MANUAL items require agent attestation in the run log before stage 1.")
    sys.exit(0)


if __name__ == "__main__":
    main()
