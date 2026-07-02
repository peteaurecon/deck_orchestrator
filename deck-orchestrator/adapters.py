"""
adapters.py - the agent adapters for the deck-orchestrator loop.

Each adapter wraps one role and returns a *patch* (list of {op, path, value}) that
the orchestrator validates against the ownership map and applies. Adapters never
write the manifest directly - they hand patches to the single writer.

Two kinds:

  Mechanical (no model) - CooperAssess, EdwardVerify. Scoring is a rubric and
  number-checking is arithmetic; you do not want a language model doing either.
  These are fully functional now.

  Generative (skill + model) - AnnaStoryline, BenBuild, AnnaReconcile, DanielBrand.
  These need the skill's judgement, so each loads its SKILL.md as the system prompt
  and asks the model to return a JSON patch. Offline (no model) they fall back to a
  deterministic stub so the whole loop still runs; wire a real model to go live.

Swap the backend in one line:  runner uses StubModel() offline, ClaudeModel() live.
"""

from __future__ import annotations
import json, re, math
from pathlib import Path

from orchestrator import Orchestrator, PatchError

HERE = Path(__file__).parent
SKILLS = HERE.parent  # /mnt/skills/user

SKILL_PATH = {
    "dylan-rules": SKILLS / "dylan-rules" / "SKILL.md",
    "render-tufte-chart": SKILLS / "render-tufte-chart" / "SKILL.md",
    "assess-graphical-excellence": SKILLS / "assess-graphical-excellence" / "SKILL.md",
    "aureconed": SKILLS / "aureconed" / "SKILL.md",
}


# --------------------------------------------------------------------------
# Model backend (pluggable)
# --------------------------------------------------------------------------
class ModelClient:
    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError


class StubModel(ModelClient):
    """Offline marker. Generative adapters check `model is None` and use their stub;
    if a StubModel is passed instead of None it raises, so a misconfigured live run
    fails loudly rather than silently faking output."""
    def complete(self, system, user):
        raise RuntimeError("StubModel cannot complete - run adapters offline (model=None) "
                           "or wire a real ModelClient.")


class ClaudeModel(ModelClient):
    """Live backend. Not exercised in the offline demo, but this is the whole wiring.
    The adapter's system prompt is the role's SKILL.md plus 'return JSON ops'."""
    def __init__(self, model="claude-sonnet-4-6", max_tokens=4000):
        import anthropic  # only needed when actually going live
        self.client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, system, user):
        r = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens,
            system=system, messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in r.content if getattr(b, "type", None) == "text")


def parse_ops(text: str):
    """Pull a JSON patch out of a model response. Expects {"ops": [...]} (tolerates
    a bare list or code fences)."""
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    data = json.loads(t)
    ops = data["ops"] if isinstance(data, dict) and "ops" in data else data
    if not isinstance(ops, list):
        raise ValueError("model did not return a list of ops")
    for op in ops:
        if not {"op", "path"} <= set(op):
            raise ValueError(f"malformed op: {op}")
    return ops


def load_skill(name: str) -> str:
    p = SKILL_PATH[name]
    return p.read_text() if p.exists() else f"[{name} SKILL.md not found]"


# --------------------------------------------------------------------------
# Base adapter
# --------------------------------------------------------------------------
class Adapter:
    agent = None

    def __init__(self, model: ModelClient | None = None):
        self.model = model

    def run(self, orch: Orchestrator, **kw):
        ops = self.build_ops(orch.m, **kw)
        if ops:
            orch.apply_patch(self.agent, ops, note=type(self).__name__)
        return ops

    def build_ops(self, m, **kw):
        if self.model is None:
            return self.stub(m, **kw)
        system, user = self.prompt(m, **kw)
        return parse_ops(self.model.complete(system, user))

    def stub(self, m, **kw):
        raise NotImplementedError

    def prompt(self, m, **kw):
        raise NotImplementedError


def _find(coll, key, _id):
    return next((x for x in coll if x[key] == _id), None)


# --------------------------------------------------------------------------
# Generative adapters (skill + model; offline stub)
# --------------------------------------------------------------------------
class AnnaStoryline(Adapter):
    """Front half: ingest analysis, set audience, write the storyline. Interactive
    (interview + P1 sign-off), so the offline stub is a no-op - the runner starts
    from a signed-off seed. The live prompt is the real wiring."""
    agent = "anna"

    def prompt(self, m, **kw):
        system = (load_skill("dylan-rules") +
                  "\n\nYou are the storyline stage. Read the inputs and produce a patch that "
                  "writes audience, governing_thought, and the slide storyline (action titles, "
                  "messages, sections, exhibit specs). Return ONLY JSON: {\"ops\":[{\"op\":\"set\","
                  "\"path\":\"...\",\"value\":...}, ...]}.")
        user = json.dumps({"inputs": m.get("inputs"), "sections": "answer-first pyramid"}, indent=2)
        return system, user

    def stub(self, m, **kw):
        return []  # storyline arrives in the seed


class BenBuild(Adapter):
    """Build one chart exhibit as a native object. Live: render-tufte-chart designs
    it. Offline: mark it built native (the assembler draws bars from plotted_series)."""
    agent = "ben"

    def prompt(self, m, exhibit_id=None):
        ex = _find(m["exhibits"], "exhibit_id", exhibit_id)
        system = (load_skill("render-tufte-chart") +
                  "\n\nBuild this exhibit as a native PptxGenJS object (F4). Return ONLY a JSON "
                  "patch setting exhibits/<id>/object_kind and any data_ref needed.")
        return system, json.dumps({"exhibit": ex}, indent=2)

    def stub(self, m, exhibit_id=None):
        ex = _find(m["exhibits"], "exhibit_id", exhibit_id)
        kind = {"chart": "pptxgenjs_chart", "table": "pptxgenjs_table",
                "stat": "text", "diagram": "native_shapes"}.get(ex["type"], "native_shapes")
        return [{"op": "set", "path": f"exhibits/{exhibit_id}/object_kind", "value": kind}]


class AnnaReconcile(Adapter):
    """Post-build: confirm each built chart still proves its slide's message and the
    title numbers match. Live: dylan-rules. Offline: mark slides reconciled (no
    contradiction in the demo)."""
    agent = "anna"

    def prompt(self, m, **kw):
        system = (load_skill("dylan-rules") +
                  "\n\nReconcile stage: for each slide with a built exhibit, confirm the chart "
                  "proves the message and the title figures match the computed values. If a chart "
                  "contradicts its claim, do NOT mark it reconciled - leave it and flag it. Return "
                  "ONLY a JSON patch setting slides/<id>/status to 'reconciled' for those that pass.")
        return system, json.dumps({"slides": m["slides"], "exhibits": m["exhibits"]}, indent=2)

    def stub(self, m, **kw):
        return [{"op": "set", "path": f"slides/{s['slide_id']}/status", "value": "reconciled"}
                for s in m["slides"] if s.get("status") != "reconciled"
                and s["section"] not in ("cover", "appendix")]


class DanielBrand(Adapter):
    """Apply the Aurecon visual layer and sign off brand. Live: aureconed. Offline:
    mark slides/exhibits branded (the emphasis -> green is already in the manifest
    and the assembler paints it)."""
    agent = "daniel"

    def prompt(self, m, **kw):
        system = (load_skill("aureconed") +
                  "\n\nBrand the deck: Aurecon Green on each exhibit's emphasis series, grey "
                  "otherwise; Arial; layout and hairlines per spec. Reject two greens on one slide. "
                  "Return ONLY a JSON patch setting slides/<id>/status and exhibits/<id>/status to "
                  "'branded'.")
        return system, json.dumps({"slides": m["slides"], "exhibits": m["exhibits"]}, indent=2)

    def stub(self, m, **kw):
        ops = [{"op": "set", "path": f"slides/{s['slide_id']}/status", "value": "branded"}
               for s in m["slides"]]
        ops += [{"op": "set", "path": f"exhibits/{e['exhibit_id']}/status", "value": "branded"}
                for e in m["exhibits"]]
        return ops


# --------------------------------------------------------------------------
# Mechanical adapters (real code, no model)
# --------------------------------------------------------------------------
class CooperAssess(Adapter):
    """Score a chart against a rubric. Deterministic - no model. Sets genre (if the
    pre-flight left it open), the score, and the status; returns ranked fixes when it
    falls below the pass threshold so Ben can rebuild."""
    agent = "cooper"
    PASS = 8.0

    def build_ops(self, m, exhibit_id=None):
        ex = _find(m["exhibits"], "exhibit_id", exhibit_id)
        if not ex or ex["type"] != "chart":
            return []
        series = (ex.get("data_ref") or {}).get("plotted_series") or []
        fixes, score = [], 10.0
        genre = ex.get("genre")
        if not genre:
            genre = "bar"  # inferred from a small categorical series
        if ex.get("emphasis") in (None, "") and len(series) > 1:
            score -= 1.0; fixes.append("B4: no series carries the so-what - set an emphasis")
        if len(series) > 6:
            score -= 2.0; fixes.append("C3: too many series - switch to small multiples")
        if any((d.get("value") is None) for d in series):
            score -= 3.0; fixes.append("data: missing values in the plotted series")
        score = max(0.0, min(10.0, score))
        it = (ex.get("cooper") or {}).get("iterations", 0) + 1
        status = "scored" if score >= self.PASS else "needs_rebuild"
        ops = [
            {"op": "set", "path": f"exhibits/{exhibit_id}/genre", "value": genre},
            {"op": "set", "path": f"exhibits/{exhibit_id}/cooper/score", "value": round(score, 1)},
            {"op": "set", "path": f"exhibits/{exhibit_id}/cooper/iterations", "value": it},
            {"op": "set", "path": f"exhibits/{exhibit_id}/cooper/open_fixes", "value": fixes},
            {"op": "set", "path": f"exhibits/{exhibit_id}/status", "value": status},
        ]
        return ops


class EdwardVerify(Adapter):
    """Verify the number ledger and the reference registry. Deterministic - no model
    for the arithmetic. `sources_read` stands in for reading the in-hand documents
    (figure_id -> raw value); live, Edward extracts these from the attached files.
    The legitimacy/relevance judgement (claim vs source) is the one part that would
    use the model; here in-hand sources are taken as relevant."""
    agent = "edward"

    def __init__(self, model=None, sources_read=None):
        super().__init__(model)
        self.read = sources_read or {}

    def build_ops(self, m, **kw):
        ops = []
        sm_by_id = {s["source_material_id"]: s for s in m["inputs"]["source_materials"]}

        # sources: in-hand -> verified (+ a bibliography entry); not in hand -> unverifiable
        for src in m["sources"]:
            sm = sm_by_id.get(src.get("source_material_id"))
            if sm and sm.get("in_hand"):
                if src.get("verification") != "verified":
                    ops += [
                        {"op": "set", "path": f"sources/{src['source_id']}/verification", "value": "verified"},
                        {"op": "set", "path": f"sources/{src['source_id']}/relevance_ok", "value": True},
                        {"op": "set", "path": f"sources/{src['source_id']}/bibliography_entry",
                         "value": sm.get("label") or src.get("claim") or src["source_id"]},
                    ]
            else:
                if src.get("verification") != "unverifiable":
                    ops.append({"op": "set", "path": f"sources/{src['source_id']}/verification",
                                "value": "unverifiable"})

        # figures: check shown against the value read from the (in-hand) source
        for fig in m["figures"]:
            if fig.get("verification") == "verified":
                continue
            src = _find(m["sources"], "source_id", fig.get("citation"))
            sm = sm_by_id.get(src.get("source_material_id")) if src else None
            readable = sm and sm.get("in_hand") and fig["figure_id"] in self.read
            if not readable:
                continue  # stays pending -> blocks assembly until the source is in hand
            raw = self.read[fig["figure_id"]]
            ok = self._matches(raw, fig.get("transform", ""), fig["shown"])
            ops += [
                {"op": "set", "path": f"figures/{fig['figure_id']}/source_value", "value": raw},
                {"op": "set", "path": f"figures/{fig['figure_id']}/verification",
                 "value": "verified" if ok else "mismatch"},
            ]
        return ops

    @staticmethod
    def _matches(raw, transform, shown):
        """Apply the declared transform to the raw source value and compare to shown.
        Handles the % and $m forms; falls back to a loose numeric compare."""
        s = str(shown).strip()
        try:
            if s.endswith("%"):
                target = float(s[:-1])
                expected = round(raw * 100) if raw <= 1 else round(raw)
                return abs(expected - target) <= 0.5
            if s.startswith("$") and s.lower().endswith("m"):
                target = float(s[1:-1])
                return abs(round(raw, 1) - target) <= 0.05
            target = float(re.sub(r"[^\d.\-]", "", s))
            return abs(raw - target) <= max(0.01, abs(target) * 0.01)
        except (ValueError, TypeError):
            return False
