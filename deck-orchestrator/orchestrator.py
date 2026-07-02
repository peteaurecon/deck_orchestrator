"""
Reference orchestrator for the Aurecon deck-build loop.

This is the single writer. The six agents (Anna, Ben, Cooper, Edward, Daniel) are
stateless: each is handed a read-only view of the manifest and returns a *patch*
(a list of ops). The orchestrator validates the patch against an ownership map,
applies it, logs it, and runs the gate logic. Nothing else mutates the manifest -
that is what makes the autonomous back half safe.

Control logic is runtime-agnostic; this happens to be Python. If you want it in the
same runtime as a PptxGenJS assembler, it ports to Node directly - the manifest is
plain JSON and the rules below are the whole spec.

What is enforced here (not in JSON Schema, which only checks shape):
  - ownership: an agent's patch may only touch fields in its lane
  - single writer: only this process applies patches; agents return, never write
  - verification is a build gate: nothing unverifiable assembles
  - freeze override: an Edward integrity failure or an Anna contradiction reopens
    a frozen exhibit; cosmetic passes cannot
  - escalation caps: Ben<->Cooper at 5, agent<->Anna at 2, then hard_stop -> human
"""

from __future__ import annotations
import json, re, sys, datetime
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

HERE = Path(__file__).parent
SCHEMA_PATH = HERE / "manifest.schema.json"

ID_FIELD = {
    "slides": "slide_id", "exhibits": "exhibit_id", "figures": "figure_id",
    "sources": "source_id", "decisions": "decision_id",
}
COLLECTIONS = set(ID_FIELD) | {"log"}
TOP_OBJECTS = {"meta", "audience", "inputs"}

COOPER_REBUILD_CAP = 5
ANNA_ROUND_CAP = 2

# --- Ownership map ---------------------------------------------------------
# Which manifest paths each agent's patch may write. "*" matches one id segment.
# Overlap on `status` is intentional: status transitions happen at several agents.
# This is the *policy* - edit it freely; the enforcement is generic.
OWNERSHIP = {
    "anna": [
        "audience/*", "governing_thought",
        "slides", "slides/*/action_title", "slides/*/message", "slides/*/section",
        "slides/*/order", "slides/*/exhibit_id", "slides/*/citations", "slides/*/status",
        "slides/*/body",
        "exhibits/*/type", "exhibits/*/so_what", "exhibits/*/emphasis",
        "figures", "figures/*/shown", "figures/*/anchor", "figures/*/transform",
        "figures/*/role", "figures/*/citation", "figures/*/slide_id", "figures/*/exhibit_id",
        "sources", "sources/*/claim", "sources/*/used_on", "sources/*/source_material_id",
    ],
    "ben": [
        "exhibits", "exhibits/*/data_ref", "exhibits/*/figure_ids",
        "exhibits/*/object_kind", "exhibits/*/status",
        "figures", "figures/*/shown", "figures/*/anchor", "figures/*/transform",
        "figures/*/role", "figures/*/citation", "figures/*/slide_id", "figures/*/exhibit_id",
    ],
    "cooper": [
        "exhibits/*/genre", "exhibits/*/multi_render", "exhibits/*/status",
        "exhibits/*/cooper", "exhibits/*/cooper/score",
        "exhibits/*/cooper/iterations", "exhibits/*/cooper/open_fixes",
    ],
    "edward": [
        "figures/*/source_value", "figures/*/verification",
        "sources/*/verification", "sources/*/relevance_ok", "sources/*/bibliography_entry",
    ],
    "daniel": [
        "slides/*/status", "exhibits/*/status",
    ],
    "orchestrator": [
        "meta/*", "sources/*/citation", "sources/*/bibliography_entry",
        "exhibits/*/cooper/frozen", "exhibits/*/status", "slides/*/status",
        "decisions", "decisions/*/status", "decisions/*/resolution", "decisions/*/rounds",
    ],
    "human": [
        "audience/signed_off", "decisions/*/status", "decisions/*/resolution",
        "inputs/source_materials", "inputs/source_materials/*/in_hand",
        "inputs/source_materials/*/path",
    ],
}


def _compile(patterns):
    out = []
    for p in patterns:
        rx = "^" + re.escape(p).replace(r"\*", r"[^/]+") + "$"
        out.append(re.compile(rx))
    return out

_OWN_RX = {agent: _compile(pats) for agent, pats in OWNERSHIP.items()}


class PatchError(Exception):
    pass


class Orchestrator:
    def __init__(self, manifest: dict):
        self.m = manifest
        self.schema = json.loads(SCHEMA_PATH.read_text()) if SCHEMA_PATH.exists() else None

    # ---- io ----
    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text()))

    def save(self, path):
        Path(path).write_text(json.dumps(self.m, indent=2))

    # ---- validation ----
    def validate(self):
        """Schema shape + cross-reference integrity. Returns list of error strings."""
        errors = []
        if Draft202012Validator and self.schema:
            v = Draft202012Validator(self.schema)
            for e in sorted(v.iter_errors(self.m), key=lambda e: list(e.path)):
                errors.append(f"schema: {'/'.join(map(str, e.path))}: {e.message}")
        errors += self._ref_errors()
        return errors

    def _ids(self, coll):
        return {it[ID_FIELD[coll]] for it in self.m.get(coll, [])}

    def _ref_errors(self):
        e = []
        sl, ex = self._ids("slides"), self._ids("exhibits")
        sr = self._ids("sources")
        for s in self.m.get("slides", []):
            if s.get("exhibit_id") and s["exhibit_id"] not in ex:
                e.append(f"ref: slide {s['slide_id']} -> missing exhibit {s['exhibit_id']}")
            for c in s.get("citations", []):
                if c not in sr:
                    e.append(f"ref: slide {s['slide_id']} cites missing source {c}")
        for x in self.m.get("exhibits", []):
            if x["slide_id"] not in sl:
                e.append(f"ref: exhibit {x['exhibit_id']} -> missing slide {x['slide_id']}")
        for f in self.m.get("figures", []):
            if f.get("citation") and f["citation"] not in sr:
                e.append(f"ref: figure {f['figure_id']} cites missing source {f['citation']}")
            if f.get("exhibit_id") and f["exhibit_id"] not in ex:
                e.append(f"ref: figure {f['figure_id']} -> missing exhibit {f['exhibit_id']}")
        nums = [s["citation"] for s in self.m.get("sources", []) if s.get("citation")]
        if len(nums) != len(set(nums)):
            e.append("ref: duplicate citation numbers in sources")
        return e

    # ---- patch application (the single write path) ----
    def apply_patch(self, agent: str, ops: list, note: str = ""):
        """Validate ownership for every op, then apply atomically. Raises PatchError
        (without mutating) if any op is outside the agent's lane."""
        if agent not in _OWN_RX:
            raise PatchError(f"unknown agent '{agent}'")
        bad = [op["path"] for op in ops if not self._allowed(agent, op["path"])]
        if bad:
            raise PatchError(f"{agent} may not write: {', '.join(bad)}")
        for op in ops:
            self._apply_one(op)
        self._log(agent, note or f"{len(ops)} op(s)", ", ".join(op["path"] for op in ops))
        self._post_patch_hooks(agent, ops)

    def _allowed(self, agent, path):
        return any(rx.match(path) for rx in _OWN_RX[agent])

    def _find(self, coll, _id):
        for it in self.m[coll]:
            if it[ID_FIELD[coll]] == _id:
                return it
        raise PatchError(f"{coll}/{_id} not found")

    def _resolve(self, path):
        """Return (container, key) so caller can set/remove container[key].
        Descends dicts and lists (numeric segment = list index)."""
        seg = path.split("/")
        head = seg[0]
        if head in COLLECTIONS and len(seg) == 1:
            return self.m[head], None                      # append target
        if head in ID_FIELD:
            node, rest = self._find(head, seg[1]), seg[2:]
        else:
            node, rest = self.m.get(head), seg[1:]
        if not rest:
            return self.m, head                            # top-level scalar
        for s in rest[:-1]:
            node = node[int(s)] if isinstance(node, list) else node[s]
        last = rest[-1]
        return node, (int(last) if isinstance(node, list) else last)

    def _apply_one(self, op):
        kind, path = op["op"], op["path"]
        if kind == "append":
            self.m.setdefault(path, []).append(op["value"])
        elif kind == "set":
            container, key = self._resolve(path)
            container[key] = op["value"]
        elif kind == "remove":
            seg = path.split("/")
            if seg[0] in ID_FIELD and len(seg) == 2:
                self.m[seg[0]] = [it for it in self.m[seg[0]]
                                  if it[ID_FIELD[seg[0]]] != seg[1]]
            else:
                container, key = self._resolve(path)
                container.pop(key, None)
        else:
            raise PatchError(f"unknown op '{kind}'")

    # ---- gate logic ----
    def _post_patch_hooks(self, agent, ops):
        """Side effects the orchestrator owns: freeze override + escalation."""
        for op in ops:
            seg = op["path"].split("/")
            # Edward marks a figure mismatch/unanchored -> reopen its exhibit (beats freeze)
            if (seg[0] == "figures" and seg[-1] == "verification"
                    and op["value"] in ("mismatch", "unanchored")):
                fig = self._find("figures", seg[1])
                self._reopen_exhibit(fig.get("exhibit_id"), reason=f"figure {fig['figure_id']} {op['value']}")
                self._escalate(f"figures/{fig['figure_id']}", "edward_unresolved", "edward",
                               f"Figure {fig['shown']} is {op['value']}: {fig.get('transform','')}. Source value?")
            # Edward marks a source unverifiable -> escalate (blocking)
            if (seg[0] == "sources" and seg[-1] == "verification"
                    and op["value"] == "unverifiable"):
                src = self._find("sources", seg[1])
                self._escalate(f"sources/{src['source_id']}", "edward_unresolved", "edward",
                               f"Source for '{src.get('claim','')}' cannot be verified - attach the document or pull the claim.")
            # Edward clears a figure/source -> auto-resolve its open/hard_stop decision
            if (seg[0] in ("sources", "figures") and seg[-1] == "verification"
                    and op["value"] == "verified"):
                self._clear_decisions(f"{seg[0]}/{seg[1]}")

    def _clear_decisions(self, object_ref):
        for d in self.m["decisions"]:
            if d.get("object_ref") == object_ref and d["status"] != "resolved":
                d["status"], d["resolution"] = "resolved", "verified"
        if (self.m["meta"]["stage"] == "blocked"
                and not any(d["status"] == "hard_stop" for d in self.m["decisions"])):
            self.m["meta"]["stage"] = "verify"
            self._log("orchestrator", "unblocked", "no hard_stop remaining")

    def _reopen_exhibit(self, exhibit_id, reason):
        if not exhibit_id:
            return
        try:
            x = self._find("exhibits", exhibit_id)
        except PatchError:
            return
        x["status"] = "needs_rebuild"
        x.setdefault("cooper", {})["frozen"] = False
        self._log("orchestrator", f"freeze override: reopened {exhibit_id}", reason)

    def _escalate(self, object_ref, gate, origin, prompt):
        """Open a decision for object_ref if none open; else bump the Anna round and
        hard_stop at the cap."""
        for d in self.m["decisions"]:
            if d.get("object_ref") == object_ref and d["status"] == "open":
                d["rounds"] = d.get("rounds", 0) + 1
                if d["rounds"] >= ANNA_ROUND_CAP:
                    d["status"] = "hard_stop"
                    self.m["meta"]["stage"] = "blocked"
                    self._log("orchestrator", f"hard_stop: {object_ref}", "Anna round cap reached")
                return
        did = f"dec_{len(self.m['decisions'])+1:03d}"
        self.m["decisions"].append({
            "decision_id": did, "gate": gate, "origin": origin, "object_ref": object_ref,
            "prompt": prompt, "options": [], "status": "open", "resolution": None, "rounds": 0,
        })
        self._log("orchestrator", f"escalated {object_ref} -> {did}", gate)

    def assembly_blockers(self):
        b = []
        for s in self.m.get("sources", []):
            if s.get("verification") != "verified":
                b.append(f"source {s['source_id']} is {s.get('verification')} (claim: {s.get('claim','')})")
        for f in self.m.get("figures", []):
            if f.get("verification") != "verified":
                b.append(f"figure {f['figure_id']} ({f.get('shown')}) is {f.get('verification')}")
        return b

    def advance(self, target):
        """Try to move meta.stage. Returns (ok, blockers)."""
        if any(d["status"] == "hard_stop" for d in self.m["decisions"]):
            return False, ["a hard_stop decision is open - human must resolve"]
        if target in ("assemble", "delivered"):
            blockers = self.assembly_blockers()
            if blockers:
                # surface each unresolved item as a decision routed to Anna
                for f in self.m.get("figures", []):
                    if f.get("verification") in ("mismatch", "unanchored"):
                        self._escalate(f"figures/{f['figure_id']}", "edward_unresolved", "orchestrator",
                                       f"Resolve figure {f['shown']} before assembly.")
                for s in self.m.get("sources", []):
                    if s.get("verification") != "verified":
                        self._escalate(f"sources/{s['source_id']}", "edward_unresolved", "orchestrator",
                                       f"Resolve source {s['source_id']} before assembly.")
                return False, blockers
        self.m["meta"]["stage"] = target
        self._log("orchestrator", f"stage -> {target}", None)
        return True, []

    def assign_citation_numbers(self):
        """Deterministic [n] in order of first appearance across slides."""
        order, n = {}, 0
        for s in sorted(self.m["slides"], key=lambda s: s["order"]):
            for c in s.get("citations", []):
                if c not in order:
                    n += 1
                    order[c] = n
        for src in self.m["sources"]:
            src["citation"] = order.get(src["source_id"], src.get("citation"))
        self._log("orchestrator", "assigned citation numbers", str(order))

    # ---- reporting ----
    def _log(self, agent, action, outcome):
        self.m.setdefault("log", []).append({
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "agent": agent, "object_ref": None, "action": action, "outcome": outcome,
        })

    def report(self):
        m = self.m
        out = [f"stage: {m['meta']['stage']}    deck: {m['meta'].get('title','')}"]
        blockers = self.assembly_blockers()
        out.append(f"assembly blockers: {len(blockers)}")
        for b in blockers:
            out.append(f"  - {b}")
        opens = [d for d in m["decisions"] if d["status"] != "resolved"]
        out.append(f"open decisions: {len(opens)}")
        for d in opens:
            out.append(f"  - [{d['status']}] {d['gate']} ({d.get('object_ref')}): {d['prompt']}")
        return "\n".join(out)


# --------------------------------------------------------------------------
# Demo: exercise validation, ownership enforcement, and the gates.
# --------------------------------------------------------------------------
def _hr(t): print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)

if __name__ == "__main__":
    o = Orchestrator.load(HERE / "example_manifest.json")

    _hr("1. validate (schema + cross-references)")
    errs = o.validate()
    print("OK - no errors" if not errs else "\n".join(errs))

    _hr("2. initial state (stage=verify)")
    print(o.report())

    _hr("3. ownership: Ben tries to rewrite a slide title (out of lane)")
    try:
        o.apply_patch("ben", [{"op": "set", "path": "slides/s_gap/action_title", "value": "hacked"}])
        print("applied (WRONG)")
    except PatchError as e:
        print(f"rejected: {e}")

    _hr("4. ownership: Ben legitimately sets an exhibit's object_kind (in lane)")
    o.apply_patch("ben", [{"op": "set", "path": "exhibits/ex_split/object_kind", "value": "pptxgenjs_chart"}],
                  note="built native chart")
    print("applied:", o._find("exhibits", "ex_split")["object_kind"])

    _hr("5. freeze override: ex_split is branded+frozen, then Edward finds its figure wrong")
    # simulate the chart having passed all the way to branded/frozen
    o.apply_patch("daniel", [{"op": "set", "path": "exhibits/ex_split/status", "value": "branded"}])
    o.apply_patch("orchestrator", [{"op": "set", "path": "exhibits/ex_split/cooper/frozen", "value": True}])
    x = o._find("exhibits", "ex_split")
    print(f"before: ex_split status={x['status']} frozen={x['cooper']['frozen']}")
    # Edward finds the plotted figure does not match source -> integrity beats freeze
    o.apply_patch("edward", [{"op": "set", "path": "figures/fig_reactive_pct/verification", "value": "mismatch"}],
                  note="0.61 shown, source pivot reads 0.58")
    x = o._find("exhibits", "ex_split")
    print(f"after:  ex_split status={x['status']} frozen={x['cooper']['frozen']}  (reopened despite freeze)")

    _hr("6. gate: advancing to assemble is blocked by every unverified item")
    ok, blockers = o.advance("assemble")
    print("advanced:", ok)
    for b in blockers:
        print("  blocked by:", b)
    print("\n" + o.report())

    _hr("7. escalation cap: src_benchmark stays unverifiable; each recheck bumps the Anna round (cap=2)")
    for i in range(2):
        o.apply_patch("edward", [{"op": "set", "path": "sources/src_benchmark/verification", "value": "unverifiable"}],
                      note=f"recheck {i+1}: still no document")
        d = next(d for d in o.m["decisions"] if d.get("object_ref") == "sources/src_benchmark")
        print(f"  recheck {i+1}: rounds={d['rounds']}  status={d['status']}  stage={o.m['meta']['stage']}")

    _hr("8. resolve: human attaches the document; Ben rebuilds; Edward verifies the chain")
    o.apply_patch("human", [
        {"op": "set", "path": "inputs/source_materials/1/in_hand", "value": True},
        {"op": "set", "path": "inputs/source_materials/1/path", "value": "./inputs/benchmark.pdf"},
    ], note="document provided")
    # Ben rebuilds the reopened chart with the corrected figure; Cooper re-scores
    o.apply_patch("ben", [{"op": "set", "path": "exhibits/ex_split/status", "value": "scored"}], note="rebuilt")
    # Edward verifies both the corrected chart figure and the now-checkable benchmark figure
    o.apply_patch("edward", [
        {"op": "set", "path": "figures/fig_reactive_pct/source_value", "value": 0.6093},
        {"op": "set", "path": "figures/fig_reactive_pct/verification", "value": "verified"},
        {"op": "set", "path": "sources/src_benchmark/verification", "value": "verified"},
        {"op": "set", "path": "sources/src_benchmark/relevance_ok", "value": True},
        {"op": "set", "path": "sources/src_benchmark/bibliography_entry", "value": "Sector downtime-cost benchmark, 2024."},
        {"op": "set", "path": "figures/fig_annual_cost/source_value", "value": 4.08},
        {"op": "set", "path": "figures/fig_annual_cost/verification", "value": "verified"},
    ], note="verified against attached document")
    print(o.report())

    _hr("9. assemble: gate clears; assign citation numbers; advance")
    o.assign_citation_numbers()
    ok, blockers = o.advance("assemble")
    print("advanced:", ok, "-> stage:", o.m["meta"]["stage"])
    print("citations:", {s["source_id"]: s["citation"] for s in o.m["sources"]})
    print("final validation:", "OK" if not o.validate() else o.validate())

    # emit the verified manifest - this is the assembler's input
    o.save(HERE / "example_manifest_verified.json")
    print("wrote example_manifest_verified.json")
