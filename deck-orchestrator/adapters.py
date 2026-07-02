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

    def prompt(self, m, exhibit_id=None, fixes=None):
        ex = _find(m["exhibits"], "exhibit_id", exhibit_id)
        slide = _find(m["slides"], "slide_id", ex["slide_id"]) or {}
        figures = [f for f in m.get("figures", []) if f.get("exhibit_id") == exhibit_id]
        system = (load_skill("render-tufte-chart") +
                  "\n\nBuild this exhibit as a native PptxGenJS object (F4). The chart must "
                  "PROVE the slide's action title and message - design so the asserted figure "
                  "or delta is the most prominent thing on the graphic (direct labels on the "
                  "emphasis series, the title number visibly derivable from the marks). "
                  "Return ONLY a JSON patch setting exhibits/<id>/object_kind and any "
                  "data_ref needed.")
        payload = {
            "exhibit": ex,
            "slide_context": {  # design TO the message, not just from the data
                "action_title": slide.get("action_title"),
                "message": slide.get("message"),
                "so_what": ex.get("so_what"),
                "emphasis": ex.get("emphasis"),
            },
            "figures_on_this_exhibit": figures,
        }
        if fixes:
            payload["rebuild_fixes"] = fixes
            system += ("\n\nThis is a REBUILD. Address every listed fix - they are ranked "
                       "highest impact first and tagged with the Tufte remedy (B-code) or "
                       "genre switch (C-code) to apply. Do not regress anything that passed.")
        return system, json.dumps(payload, indent=2)

    def stub(self, m, exhibit_id=None, fixes=None):
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
    """Hybrid scorer. The mechanical rubric is the hard gate - encodable rules
    (missing data, series overload, no emphasis) checked deterministically, never
    by a model. With a model wired, a second *perceptual* pass runs the judgement
    criteria the rubric cannot encode - "understood simply", direct-label fit,
    the default-challenge rule - using assess-graphical-excellence as its brief.
    Final score = min(mechanical, perceptual): the model can pull a chart back
    for rebuild but can never wave through a rubric failure. Perceptual fixes
    merge into open_fixes so Ben's rebuild addresses both kinds."""
    agent = "cooper"
    PASS = 8.0

    @staticmethod
    def rubric(ex):
        """Pure mechanical rubric over one exhibit dict -> (score, fixes).
        Kept static so the runner can score best-of-N candidates without patching."""
        series = (ex.get("data_ref") or {}).get("plotted_series") or []
        fixes, score = [], 10.0
        if ex.get("emphasis") in (None, "") and len(series) > 1:
            score -= 1.0; fixes.append("B4: no series carries the so-what - set an emphasis")
        if len(series) > 6:
            score -= 2.0; fixes.append("C3: too many series - switch to small multiples")
        if any((d.get("value") is None) for d in series):
            score -= 3.0; fixes.append("data: missing values in the plotted series")
        return max(0.0, min(10.0, score)), fixes

    def _perceptual(self, m, ex):
        """Model pass over the non-encodable criteria. Returns (score, fixes) or
        None on any failure - the mechanical gate still stands either way."""
        if self.model is None:
            return None
        slide = _find(m["slides"], "slide_id", ex["slide_id"]) or {}
        system = (load_skill("assess-graphical-excellence") +
                  "\n\nYou are the perceptual pass of a hybrid scorer. A mechanical rubric has "
                  "already checked the encodable rules; score ONLY the judgement criteria: "
                  "(1) can it be understood simply, at a glance, by this audience; "
                  "(2) do the direct labels work in this instance (no collision, no ambiguity); "
                  "(3) the default-challenge rule - is this genre justified against the "
                  "second-line VDQI alternatives, or is it a quiet default; "
                  "(4) does the design make the slide's asserted message the most prominent "
                  "thing on the graphic. "
                  "Return ONLY JSON: {\"score\": <0-10>, \"fixes\": [\"<ranked, B/C-tagged>\", ...]}.")
        user = json.dumps({"exhibit": ex,
                           "slide_context": {"action_title": slide.get("action_title"),
                                             "message": slide.get("message")},
                           "audience": m.get("audience")}, indent=2)
        try:
            data = json.loads(re.sub(r"^```(?:json)?|```$", "",
                                     self.model.complete(system, user).strip(), flags=re.M).strip())
            return float(data["score"]), list(data.get("fixes", []))
        except Exception:
            return None  # fail safe to mechanical; never fail the pipeline on the extra pass

    def build_ops(self, m, exhibit_id=None):
        ex = _find(m["exhibits"], "exhibit_id", exhibit_id)
        if not ex or ex["type"] != "chart":
            return []
        genre = ex.get("genre") or "bar"  # inferred from a small categorical series
        mech_score, fixes = self.rubric(ex)
        score = mech_score
        p_score, p_fixes = None, []
        p = self._perceptual(m, ex)
        if p is not None:
            p_score, p_fixes = p
            score = min(mech_score, p_score)   # judgement can demand better, never excuse worse
            fixes = fixes + [f for f in p_fixes if f not in fixes]
        it = (ex.get("cooper") or {}).get("iterations", 0) + 1
        status = "scored" if score >= self.PASS else "needs_rebuild"
        ops = [
            {"op": "set", "path": f"exhibits/{exhibit_id}/genre", "value": genre},
            {"op": "set", "path": f"exhibits/{exhibit_id}/cooper/score", "value": round(score, 1)},
            {"op": "set", "path": f"exhibits/{exhibit_id}/cooper/iterations", "value": it},
            {"op": "set", "path": f"exhibits/{exhibit_id}/cooper/open_fixes", "value": fixes},
            {"op": "set", "path": f"exhibits/{exhibit_id}/status", "value": status},
        ]
        if p_score is not None:
            ops += [
                {"op": "set", "path": f"exhibits/{exhibit_id}/cooper/perceptual_score", "value": round(p_score, 1)},
                {"op": "set", "path": f"exhibits/{exhibit_id}/cooper/perceptual_fixes", "value": p_fixes},
            ]
        return ops


class EdwardVerify(Adapter):
    """Verify the number ledger and the reference registry. Deterministic - no model
    for the arithmetic. `sources_read` stands in for reading the in-hand documents
    (figure_id -> raw value); live, Edward extracts these from the attached files.
    The legitimacy/relevance judgement (claim vs source) is the one part that would
    use the model; here in-hand sources are taken as relevant."""
    agent = "edward"

    def __init__(self, model=None, sources_read=None, source_excerpts=None):
        super().__init__(model)
        self.read = sources_read or {}
        self.excerpts = source_excerpts or {}  # source_material_id -> text excerpt, for the relevance pass

    def _relevant(self, src, sm):
        """Judgement half of 'legitimate + relevant'. Arithmetic is never the model's;
        relevance always is - does this document actually support this claim? Offline
        (no model, or no excerpt) it degrades to True, as before."""
        if self.model is None:
            return True
        excerpt = self.excerpts.get(sm["source_material_id"])
        if not excerpt:
            return True
        system = ("You are auditing a reference registry. Answer whether the source excerpt "
                  "actually supports the claim - not merely mentions the topic. "
                  "Return ONLY JSON: {\"relevant\": true|false, \"reason\": \"...\"}.")
        user = json.dumps({"claim": src.get("claim"), "source_label": sm.get("label"),
                           "excerpt": excerpt[:6000]}, indent=2)
        try:
            data = json.loads(re.sub(r"^```(?:json)?|```$", "",
                                     self.model.complete(system, user).strip(), flags=re.M).strip())
            return bool(data["relevant"])
        except Exception:
            return True  # fail safe; the mechanical chain still gates assembly

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
                        {"op": "set", "path": f"sources/{src['source_id']}/relevance_ok",
                         "value": self._relevant(src, sm)},
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


# --------------------------------------------------------------------------
# Post-assembly QA adapters - the stages that look at the ARTEFACT, not the spec
# --------------------------------------------------------------------------
class FionaVisualQA(Adapter):
    """Inspect the rendered deck, not the manifest. Everything upstream verifies
    specs; PptxGenJS specs that validate perfectly can still render clipped text,
    overlapping direct labels, collided end-labels, or elements off the slide.
    Fiona renders each slide to an image and scores what a reader actually sees
    against the F-rules and chart legibility.

    Live: a vision model receives the slide images (rendered via
    `render_deck_to_images`) plus each slide's manifest row. Blocking defects
    (legibility failures) reopen the exhibit through the orchestrator hook -
    they beat the freeze, because a chart that cannot be read is a broken chart.
    Minor defects are logged and batched into the delivery pack.

    Offline: stub passes every slide, so the demo loop runs unchanged."""
    agent = "fiona"

    def prompt(self, m, images=None, **kw):
        system = ("You are the visual QA stage of an Aurecon deck pipeline. You receive "
                  "rendered slide images and each slide's manifest row. Check ONLY what is "
                  "visible: clipped or truncated text, overlapping labels or shapes, direct "
                  "labels colliding with marks, elements off the canvas, illegible sizes "
                  "(<11pt equivalent), banded tables, shadows/3-D (F1-F4), and two green "
                  "moments on one slide. Severity: 'blocking' for anything that impairs "
                  "reading the exhibit; 'minor' for polish. Return ONLY JSON: "
                  "{\"ops\":[{\"op\":\"set\",\"path\":\"slides/<id>/visual_qa\",\"value\":\"pass|defects\"},"
                  "{\"op\":\"set\",\"path\":\"exhibits/<id>/visual_defects\",\"value\":"
                  "[{\"severity\":\"blocking|minor\",\"note\":\"...\"}]}, ...]}.")
        user = json.dumps({"slides": m["slides"], "exhibits": m["exhibits"],
                           "rendered_images": images or []}, indent=2)
        return system, user

    def stub(self, m, images=None, **kw):
        return [{"op": "set", "path": f"slides/{s['slide_id']}/visual_qa", "value": "pass"}
                for s in m["slides"]]


def render_deck_to_images(pptx_path, out_dir):
    """Render every slide of a built .pptx to PNG for Fiona (and the human pack).
    Uses LibreOffice -> PDF -> pdftoppm; returns the image paths, or [] if the
    toolchain is unavailable (Fiona then runs on manifest rows alone, degraded)."""
    import subprocess, shutil
    from pathlib import Path
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    if not (shutil.which("soffice") and shutil.which("pdftoppm")):
        return []
    try:
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf",
                        "--outdir", str(out), str(pptx_path)],
                       check=True, capture_output=True, timeout=120)
        pdf = out / (Path(pptx_path).stem + ".pdf")
        subprocess.run(["pdftoppm", "-png", "-r", "110", str(pdf), str(out / "slide")],
                       check=True, capture_output=True, timeout=120)
        return sorted(str(p) for p in out.glob("slide-*.png"))
    except Exception:
        return []


class AnnaAudit(Adapter):
    """Post-assembly dylan-rules Audit mode, turned on the pipeline's own output.
    The build stages enforce rules per slide and per exhibit; the deck-emergent
    checks - L2 (do the titles alone tell the story), Q1-Q3 (consistency of title
    style, grid, number formats) - have no owner until the deck exists. This
    stage closes that loop.

    Live: the full audit against dylan-rules, flags tagged with rule codes into
    slides/*/audit_flags. Offline: a mechanical lint that still catches the
    cheap, deterministic failures (missing/label-like titles, inconsistent
    title punctuation)."""
    agent = "anna"

    def prompt(self, m, **kw):
        system = (load_skill("dylan-rules") +
                  "\n\nRun AUDIT mode on this assembled deck. Do the L2 horizontal-logic test "
                  "first (titles alone, in order - do they tell the complete story?), then "
                  "T1/L3/X2 per slide and Q1-Q3 deck-wide. Return ONLY a JSON patch writing "
                  "slides/<id>/audit_flags as an array of '<code>: <problem> -> <fix>' strings "
                  "(empty array = clean). Put deck-wide Q findings on the slide where the fix "
                  "belongs.")
        user = json.dumps({"governing_thought": m.get("governing_thought"),
                           "audience": m.get("audience"),
                           "slides": sorted(m["slides"], key=lambda s: s["order"]),
                           "exhibits": m["exhibits"]}, indent=2)
        return system, user

    def stub(self, m, **kw):
        """Deterministic lint: T1 label-titles and Q1 punctuation consistency."""
        ops = []
        content = [s for s in sorted(m["slides"], key=lambda s: s["order"])
                   if s["section"] not in ("cover", "appendix")]
        enders = {bool(re.search(r"[.!?]$", (s.get("action_title") or "").strip())) for s in content}
        mixed_punct = len(enders) > 1
        for s in content:
            flags = []
            t = (s.get("action_title") or "").strip()
            if not t:
                flags.append("T1: missing action title -> write a full-sentence assertion")
            elif len(t.split()) < 5:
                flags.append(f"T1: '{t}' reads as a label, not an assertion -> state the finding")
            if mixed_punct and t:
                flags.append("Q1: title terminal punctuation inconsistent across deck -> pick one style")
            ops.append({"op": "set", "path": f"slides/{s['slide_id']}/audit_flags", "value": flags})
        return ops


class GeorgeScrutiny(Adapter):
    """The context guy. Attacks the argument the way a detracting client would -
    missing context, weak decomposition, undefendable claims. PURELY ADVISORY:
    challenges land in the `scrutiny` collection, never block a gate, and only
    the human writes resolution ('addressed' | 'accepted_risk').

    Two passes: pass_='storyline' on the ghost deck (cheap - batches into the
    human sign-off), pass_='assembled' on the finished deck (catches flanks that
    only exist once real numbers are on the page).

    Offline stub is a mechanical heuristic: aggregate %/stat claims get the
    standard decomposition challenge; uncited content slides get a backup_gap."""
    agent = "george"

    def prompt(self, m, pass_="assembled", **kw):
        system = (load_skill("george") +
                  f"\n\nRun the {pass_} pass. For every recommendation and aggregate claim, "
                  "apply the four questions (context, extraction, decomposition, reception) "
                  "reading as the most skeptical plausible audience. Return ONLY a JSON patch "
                  "appending to 'scrutiny': {\"ops\":[{\"op\":\"append\",\"path\":\"scrutiny\","
                  "\"value\":{\"challenge_id\":\"ch_...\",\"pass\":\"" + pass_ + "\","
                  "\"severity\":\"kill_shot|exposed_flank|backup_gap\",\"target\":\"<slide_id or "
                  "governing_thought>\",\"question\":\"<the client's question, verbatim>\","
                  "\"suggested_fix\":\"...\",\"status\":\"open\",\"resolution\":null}}]}. "
                  "Do not raise X2/T1/L2 findings - those belong to the audit, not to you.")
        payload = {"governing_thought": m.get("governing_thought"), "audience": m.get("audience"),
                   "slides": sorted(m["slides"], key=lambda s: s["order"])}
        if pass_ == "assembled":
            payload.update({"exhibits": m["exhibits"], "figures": m["figures"], "sources": m["sources"]})
        return system, json.dumps(payload, indent=2)

    def stub(self, m, pass_="assembled", **kw):
        ops, n = [], len(m.get("scrutiny", []))
        def add(sev, target, q, fix):
            nonlocal n; n += 1
            ops.append({"op": "append", "path": "scrutiny", "value": {
                "challenge_id": f"ch_{n:03d}", "pass": pass_, "severity": sev,
                "target": target, "question": q, "suggested_fix": fix,
                "status": "open", "resolution": None}})
        for s in sorted(m["slides"], key=lambda s: s["order"]):
            if s["section"] in ("cover", "appendix"):
                continue
            ex = _find(m["exhibits"], "exhibit_id", s.get("exhibit_id")) if s.get("exhibit_id") else None
            text = " ".join(filter(None, [s.get("action_title"), s.get("message")]))
            if "%" in text and ex and ex["type"] in ("stat", "callout", "chart"):
                add("exposed_flank", s["slide_id"],
                    "That aggregate invites its own breakdown - by criticality, site, asset class, "
                    "and cost to remediate. Which cut changes the story, and why isn't it shown?",
                    "decompose the aggregate or pre-empt the cuts in the body")
            if pass_ == "assembled" and not s.get("citations") and (s.get("action_title") or "").strip():
                add("backup_gap", s["slide_id"],
                    "If I ask 'show me the data behind this', what do you put on screen?",
                    "add a backup slide in the appendix, or cite the source")
        return ops
