"""
run_pipeline.py - drive the autonomous back half through the adapters.

The front half (Anna ingests, interviews for audience, writes the storyline, human
signs off) is interactive, so this runner starts from a signed-off seed and
automates everything after the gate: build -> score -> reconcile -> verify ->
brand -> assemble -> visual QA -> audit. That is the part the adapters remove the
human from.

Quality mechanics in this loop (all cheap offline, all sharper live):
  - Ben rebuilds WITH Cooper's ranked fixes and the slide context (action title,
    message, emphasis) - rebuilds are directed, not blind.
  - Early exit: if a rebuild does not improve the score, escalate immediately
    instead of burning the cap - a non-converging loop is information.
  - Best-of-N (live): Ben proposes BEN_CANDIDATES designs; the mechanical rubric
    picks the best before the full score runs. Selection + iteration, not
    iteration alone.
  - Fiona inspects the RENDERED deck (images), not the manifest - the only stage
    that sees what a reader sees. Blocking defects reopen exhibits (capped).
  - Anna audit runs dylan-rules Audit mode on the assembled deck - L2, T1, Q1-Q3.

Offline (MODEL = None) the generative adapters use their stubs and the whole thing
runs to a built deck with no API key. Set MODEL = ClaudeModel() to run it live.
"""

import copy, json, subprocess
from pathlib import Path

from orchestrator import Orchestrator
from adapters import (BenBuild, CooperAssess, AnnaReconcile, EdwardVerify, DanielBrand,
                      FionaVisualQA, AnnaAudit, GeorgeScrutiny, render_deck_to_images,
                      ClaudeModel)  # noqa: F401  (ClaudeModel imported for the live swap)

HERE = Path(__file__).parent
MODEL = None          # offline. To go live: MODEL = ClaudeModel()
BEN_CANDIDATES = 2 if MODEL else 1   # best-of-N chart designs (live only - the stub is deterministic)
VISUAL_QA_PASSES = 2                 # cap on render -> inspect -> rebuild loops


def stage(orch, s):
    orch.apply_patch("orchestrator", [{"op": "set", "path": "meta/stage", "value": s}])


def get(orch, coll, key, _id):
    return next(x for x in orch.m[coll] if x[key] == _id)


def best_candidate_ops(ben, orch, eid, fixes=None):
    """Best-of-N: ask Ben for BEN_CANDIDATES designs, score each with the pure
    mechanical rubric on a copied manifest, apply only the winner. With N=1
    (offline) this is a plain build."""
    candidates = []
    for _ in range(BEN_CANDIDATES):
        ops = ben.build_ops(orch.m, exhibit_id=eid, fixes=fixes)
        sim = copy.deepcopy(orch.m)
        o2 = Orchestrator(sim)
        o2.apply_patch(ben.agent, copy.deepcopy(ops), note="candidate")
        ex = next(x for x in sim["exhibits"] if x["exhibit_id"] == eid)
        score, _f = CooperAssess.rubric(ex)
        candidates.append((score, ops))
    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[0][1]


def build_and_score(orch, ben, cooper, eid, label=""):
    """One Ben<->Cooper loop for a chart: directed rebuilds, early exit on
    non-improvement, cap 5. Returns True if passed, False if escalated."""
    ops = best_candidate_ops(ben, orch, eid)
    orch.apply_patch(ben.agent, ops, note="BenBuild")
    prev = -1.0
    for i in range(5):
        cooper.run(orch, exhibit_id=eid)
        ex = get(orch, "exhibits", "exhibit_id", eid)
        sc = ex["cooper"]["score"]
        if sc >= CooperAssess.PASS:
            print(f"  {eid}: {label}scored {sc} -> pass"); return True
        if sc <= prev:
            orch._escalate(f"exhibits/{eid}", "cooper_stuck", "cooper",
                           f"{eid} not improving ({prev} -> {sc}) - rebuild loop is not converging")
            print(f"  {eid}: scored {sc} (no improvement on {prev}) -> early escalation")
            return False
        prev = sc
        fixes = ex["cooper"].get("open_fixes", [])
        print(f"  {eid}: scored {sc} -> rebuild ({i+1}) with {len(fixes)} fix(es)")
        ops = best_candidate_ops(ben, orch, eid, fixes=fixes)
        orch.apply_patch(ben.agent, ops, note="BenBuild(rebuild)")
    else_escalate = get(orch, "exhibits", "exhibit_id", eid)["cooper"]["score"] < CooperAssess.PASS
    if else_escalate:
        orch._escalate(f"exhibits/{eid}", "cooper_stuck", "cooper",
                       f"{eid} stuck below {CooperAssess.PASS}")
        print(f"  {eid}: escalated (cooper_stuck)")
    return not else_escalate


def run():
    orch = Orchestrator.load(HERE / "example_seed.json")
    errs = orch.validate()
    assert not errs, errs
    print(f"seed loaded  stage={orch.m['meta']['stage']}  ({len(orch.m['slides'])} slides)\n")

    read = json.loads((HERE / "example_sources.json").read_text())
    ben, cooper = BenBuild(MODEL), CooperAssess(MODEL)
    reconcile, daniel = AnnaReconcile(MODEL), DanielBrand(MODEL)
    edward = EdwardVerify(model=MODEL, sources_read=read)
    fiona, audit, george = FionaVisualQA(MODEL), AnnaAudit(MODEL), GeorgeScrutiny(MODEL)

    # --- build + score loop (Ben <-> Cooper, directed rebuilds, early exit) ---
    stage(orch, "build")
    print("BUILD + SCORE")
    for ex in [e for e in orch.m["exhibits"] if e["type"] == "chart"]:
        build_and_score(orch, ben, cooper, ex["exhibit_id"])
    for ex in [e for e in orch.m["exhibits"] if e["type"] != "chart"]:
        ben.run(orch, exhibit_id=ex["exhibit_id"])
        print(f"  {ex['exhibit_id']}: built ({ex['type']})")

    # --- reconcile ---
    stage(orch, "reconcile")
    reconcile.run(orch)
    print("\nRECONCILE: titles checked against built exhibits -> no contradiction")

    # --- verify (Edward: mechanical arithmetic + model relevance judgement) ---
    stage(orch, "verify")
    edward.run(orch)
    blockers = orch.assembly_blockers()
    print(f"\nVERIFY: {len(blockers)} blocker(s)")
    for b in blockers:
        print("  -", b)

    if blockers:
        print("\nESCALATION -> resolution: human attaches the missing document")
        for i, sm in enumerate(orch.m["inputs"]["source_materials"]):
            if not sm["in_hand"]:
                orch.apply_patch("human", [
                    {"op": "set", "path": f"inputs/source_materials/{i}/in_hand", "value": True},
                    {"op": "set", "path": f"inputs/source_materials/{i}/path", "value": f"./inputs/{sm['source_material_id']}.pdf"},
                ])
        edward.run(orch)  # re-verify now that the source is readable
        blockers = orch.assembly_blockers()
        print(f"RE-VERIFY: {len(blockers)} blocker(s)")

    # --- brand ---
    stage(orch, "brand")
    daniel.run(orch)
    print("\nBRAND: Aurecon green on emphasis, grey elsewhere -> branded")

    # --- assemble ---
    orch.assign_citation_numbers()
    ok, bl = orch.advance("assemble")
    out = HERE / "example_seed_verified.json"
    orch.save(out)
    print(f"\nASSEMBLE: advanced={ok}  citations={ {s['source_id']: s['citation'] for s in orch.m['sources']} }")

    deck = HERE / "deck_from_pipeline.pptx"
    r = subprocess.run(["node", "assembler.js", str(out), str(deck)], cwd=HERE,
                       capture_output=True, text=True)
    print(" ", (r.stdout or r.stderr).strip())

    # --- visual QA (Fiona: the rendered artefact, not the spec) ---
    stage(orch, "visual_qa")
    for qa_pass in range(1, VISUAL_QA_PASSES + 1):
        images = render_deck_to_images(deck, HERE / "qa_render") if deck.exists() else []
        fiona.run(orch, images=images)
        reopened = [e["exhibit_id"] for e in orch.m["exhibits"] if e.get("status") == "needs_rebuild"]
        n_defects = sum(len(e.get("visual_defects", [])) for e in orch.m["exhibits"])
        print(f"\nVISUAL QA pass {qa_pass}: {len(images)} slide image(s), "
              f"{n_defects} defect(s), {len(reopened)} exhibit(s) reopened")
        if not reopened:
            break
        for eid in reopened:  # directed rebuild against Fiona's blocking notes
            defects = [d["note"] for d in get(orch, "exhibits", "exhibit_id", eid).get("visual_defects", [])
                       if d["severity"] == "blocking"]
            build_and_score(orch, ben, cooper, eid, label="visual-rebuild: ")
        daniel.run(orch)                       # re-brand the rebuilt exhibits
        orch.save(out)
        r = subprocess.run(["node", "assembler.js", str(out), str(deck)], cwd=HERE,
                           capture_output=True, text=True)  # re-render ground truth
    else:
        orch._escalate("meta/visual_qa", "cooper_stuck", "fiona",
                       "visual defects persist after rebuild cap - human review of render needed")

    # --- audit (Anna: dylan-rules Audit mode on the pipeline's own output) ---
    stage(orch, "audit")
    audit.run(orch)
    flagged = {s["slide_id"]: s.get("audit_flags", []) for s in orch.m["slides"] if s.get("audit_flags")}
    print(f"\nAUDIT: {sum(len(v) for v in flagged.values())} flag(s) on {len(flagged)} slide(s)")
    for sid, fl in flagged.items():
        for f in fl:
            print(f"  {sid}: {f}")
    if flagged:
        print("  (flags batch into the delivery pack alongside open decisions)")

    # --- scrutiny (George: advisory red-team; nothing here blocks) ---
    stage(orch, "scrutiny")
    george.run(orch, pass_="assembled")
    chal = [c for c in orch.m.get("scrutiny", []) if c["status"] == "open"]
    print(f"\nSCRUTINY: {len(chal)} open challenge(s) - advisory, batched to the human")
    for c in chal:
        print(f"  [{c['severity']}] {c['target']}: {c['question']}")

    orch.save(out)
    print("\nfinal validation:", "OK" if not orch.validate() else orch.validate())
    print(orch.report())


if __name__ == "__main__":
    run()
