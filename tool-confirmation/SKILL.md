---
name: tool_confirmation
description: Mandatory preflight for the deck pipeline. Run this FIRST, before any stage of deck-orchestrator executes - whenever someone invokes deck-orchestrator, "run the deck pipeline", "build the whole deck", or any end-to-end Aurecon deck build. Verifies every system binary, package, skill file and harness capability the orchestrator depends on, and blocks the pipeline if anything critical is missing. Also run it standalone when asked to "check the deck environment", "verify tooling", or when porting the pipeline to a new harness. This skill only verifies; it never builds anything.
---

# Tool Confirmation (deck-orchestrator preflight)

Stage -1 of the deck pipeline. deck-orchestrator assumes a working environment;
this skill proves it before any agent runs. A missing binary discovered at
stage 10 wastes the whole run - discover it at stage -1 instead.

## Contract

- **Runs before deck-orchestrator stage 0.** The orchestrator must not ingest
  inputs until this preflight exits 0.
- **BLOCK failures stop the pipeline.** Report them to the human with the fix,
  do not attempt workarounds, and do not substitute alternative tooling
  (no PowerPoint COM, no python-pptx-as-builder, no matplotlib PNG charts).
  The sanctioned toolchain is PptxGenJS + the pptx skill scripts, full stop.
- **WARN failures degrade specific paths** (editing path, thumbnails) - note
  them in the run log and continue.
- **MANUAL items are attested, not tested.** The running agent confirms in the
  run log that it can (a) view rendered slide images, (b) spawn subagents for
  visual QA and parallel XML edits - or explicitly accepts degraded QA.

## Run it

```bash
python check_environment.py                      # standard preflight
python check_environment.py --live               # also require ANTHROPIC_API_KEY
python check_environment.py --skills-root /path  # non-standard skill mount
```

Exit 0 = proceed to deck-orchestrator stage 0. Exit 1 = blocked; surface the
FAIL rows and their fixes to the human.

## What it checks

| Category | BLOCK | WARN |
|---|---|---|
| Binaries | python3, node, npm, pdftoppm, soffice (direct or via pptx wrapper) | extract-text |
| Packages | pptxgenjs (installed, or npm registry reachable) | Pillow, defusedxml, jsonschema |
| Skills | SKILL.md for deck-orchestrator, dylan-rules, render-tufte-chart, assess-graphical-excellence, aureconed, pptx | pptx scripts (thumbnail, unpack, soffice, clean) |
| Orchestrator files | orchestrator.py, adapters.py, run_pipeline.py, assembler.js, manifest.schema.json (parses), package.json, assets/aurecon_logo.png | - |
| Harness | writable working dir; API key with `--live` | - |
| Manual attestation | vision, subagent spawning | - |

## Fixes for common failures

- **pptxgenjs**: `cd deck-orchestrator && npm install` (registry.npmjs.org must
  be network-allowed)
- **pdftoppm**: `apt-get install poppler-utils`
- **soffice**: install LibreOffice; the pptx skill's
  `scripts/office/soffice.py` wrapper handles sandboxed configs
- **extract-text**: not packageable - substitute a python zipfile/XML text dump
  for content QA and note it in the run log
- **Pillow / defusedxml / jsonschema**: `pip install <pkg> --break-system-packages`

## Boundaries

Verification only. It never installs, builds, patches the manifest, or touches
a .pptx. Fix-and-retry decisions belong to the human or the orchestrator's run
log, not this skill.
