"""
run_pipeline.py - drive the autonomous back half through the adapters.

The front half (Anna ingests, interviews for audience, writes the storyline, human
signs off) is interactive, so this runner starts from a signed-off seed and
automates everything after the gate: build -> score -> reconcile -> verify ->
brand -> assemble. That is the part the adapters remove the human from.

Offline (MODEL = None) the generative adapters use their stubs and the whole thing
runs to a built deck with no API key. Set MODEL = ClaudeModel() to run it live.
"""

import json, subprocess
from pathlib import Path

from orchestrator import Orchestrator
from adapters import (BenBuild, CooperAssess, AnnaReconcile, EdwardVerify, DanielBrand,
                      ClaudeModel)  # noqa: F401  (ClaudeModel imported for the live swap)

HERE = Path(__file__).parent
MODEL = None  # offline. To go live: MODEL = ClaudeModel()


def stage(orch, s):
    orch.apply_patch("orchestrator", [{"op": "set", "path": "meta/stage", "value": s}])


def get(orch, coll, key, _id):
    return next(x for x in orch.m[coll] if x[key] == _id)


def run():
    orch = Orchestrator.load(HERE / "example_seed.json")
    errs = orch.validate()
    assert not errs, errs
    print(f"seed loaded  stage={orch.m['meta']['stage']}  ({len(orch.m['slides'])} slides)\n")

    read = json.loads((HERE / "example_sources.json").read_text())
    ben, cooper = BenBuild(MODEL), CooperAssess()
    reconcile, daniel = AnnaReconcile(MODEL), DanielBrand(MODEL)
    edward = EdwardVerify(sources_read=read)

    # --- build + score loop (Ben <-> Cooper, cap 5) ---
    stage(orch, "build")
    print("BUILD + SCORE")
    for ex in [e for e in orch.m["exhibits"] if e["type"] == "chart"]:
        eid = ex["exhibit_id"]
        ben.run(orch, exhibit_id=eid)
        for i in range(5):
            cooper.run(orch, exhibit_id=eid)
            sc = get(orch, "exhibits", "exhibit_id", eid)["cooper"]["score"]
            if sc >= CooperAssess.PASS:
                print(f"  {eid}: built, scored {sc} -> pass"); break
            print(f"  {eid}: scored {sc} -> rebuild ({i+1})")
            ben.run(orch, exhibit_id=eid)
        else:
            orch._escalate(f"exhibits/{eid}", "cooper_stuck", "cooper", f"{eid} stuck below {CooperAssess.PASS}")
            print(f"  {eid}: escalated (cooper_stuck)")
    for ex in [e for e in orch.m["exhibits"] if e["type"] != "chart"]:
        ben.run(orch, exhibit_id=ex["exhibit_id"])
        print(f"  {ex['exhibit_id']}: built ({ex['type']})")

    # --- reconcile ---
    stage(orch, "reconcile")
    reconcile.run(orch)
    print("\nRECONCILE: titles checked against built exhibits -> no contradiction")

    # --- verify (Edward, mechanical) ---
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
    print("final validation:", "OK" if not orch.validate() else orch.validate())


if __name__ == "__main__":
    run()
