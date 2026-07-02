---
name: deck-orchestrator
description: Coordinate a complete, end-to-end Aurecon deck build by running the deck skills as staged role-agents over one shared manifest. Use whenever someone wants the *whole* pipeline rather than a single stage - "build the whole deck from this analysis", "run the deck pipeline", "orchestrate the deck", "take this analysis and produce a finished on-brand Aurecon deck", "stand up the deck build". Takes completed analysis in and drives it through storyline, charting, chart assessment, narrative reconciliation, source verification, branding and assembly, with one human sign-off gate and the rest autonomous. This is the coordinator that sequences dylan-rules, render-tufte-chart, assess-graphical-excellence and aureconed with gates between them - not any one of those skills. Defer to each of those for its own domain; this skill owns coordination, the manifest, the gates, and the single write path.
---

# Deck Orchestrator

The top of the deck stack. Where `dylan-rules` governs the narrative, the Tufte
skills govern charts, and `aureconed` governs brand, this skill runs all of them
as staged subagents over one shared manifest - taking completed analysis in and
producing a verified, on-brand Aurecon deck out.

It exists because the pipeline has real control structure: a human gate, two
auto-correcting loops, a verification gate, escalation caps, and a freeze rule.
That logic lives here, in `orchestrator.py`, not in any single deck skill.

## The cast

| Role | Skill it runs | Owns |
|---|---|---|
| **Orchestrator** | this skill | the manifest, the only write path, all gates |
| **Anna** | `dylan-rules` | structure, storyline, action titles, exhibit briefs, the emphasis call |
| **Ben** | `render-tufte-chart` | builds charts as native PptxGenJS objects, grey and minimal, brand-blind |
| **Cooper** | `assess-graphical-excellence` | genre pre-flight, then scores charts |
| **Edward** | `dylan-rules` R-rules + the verification gate | the number ledger and reference registry |
| **Daniel** | `aureconed` | brand and the whole visual layer |
| **Fiona** | visual QA (vision pass over rendered slides) | what the reader actually sees - legibility, collisions, clipping, F-rule violations in the render |
| **George** | `george` | adversarial scrutiny - context gaps, decomposition, backup defensibility; how the most detracting client receives the argument. Purely advisory |

Edward has no standalone skill - he enforces the **R - References** family in
`dylan-rules` plus the verification gate below. Build (the chassis, the actual
.pptx) reads/writes via the `pptx` skill.

## The flow

Completed analysis in any form (messy deck, xlsx, notes) is the input, alongside
the source materials behind it. Build target is the cleaned Aurecon chassis.

```
0. Inputs           analysis + source_materials (in_hand gates verification)
1. Anna  ingest     pull findings/exhibits, map to the answer-first section pyramid,
                    write storyline (title + message + exhibit brief per slide),
                    set exhibit type and the emphasis series for charts
2. Cooper pre-flight pick the Tufte genre per chart from data shape; flag multi-render
2b. George challenge George red-teams the ghost deck (kill shots / exposed flanks /
                    backup gaps) while the storyline is still cheap to change; his
                    challenges batch into the sign-off so the human approves the
                    narrative AND sees its known weaknesses in one sitting
3. HUMAN GATE       the only stop. Approve storyline (P1) + make every judgment call -
                    chart-vs-table, multi-render picks, George's storyline challenges
                    (address or accept as risk). Decisions batch here.
   --- back half runs unattended ---
4. route by type    chart -> Ben+Cooper ; table/stat -> dylan+Daniel ; diagram -> assembler+Daniel
5. Ben  build       native PptxGenJS chart, genre locked, grey, Tufte-correct.
                    Ben designs TO the message: the slide's action title, message, and
                    emphasis travel into his brief - the asserted figure must be the most
                    prominent thing on the graphic. Live, Ben proposes N candidates and
                    the rubric picks the best (selection + iteration, not iteration alone)
6. Cooper score     hybrid. Mechanical rubric is the hard gate (encodable rules, real
                    arithmetic); a model pass scores the perceptual criteria the rubric
                    can't encode (understood simply, direct-label fit, default-challenge).
                    Final = min(mechanical, perceptual) - judgement can demand better,
                    never excuse worse. >=8 passes; below -> ranked fixes -> Ben rebuilds
                    WITH the fixes and slide context (directed, never blind; cap 5;
                    early-escalate the moment a rebuild fails to improve the score)
7. Anna reconcile   chart still proves the message? title numbers match computed values?
                    contradiction -> human
8. Edward verify    every figure traces to a verifiable source (mechanical arithmetic);
                    relevance is the judgement half - does the document actually support
                    the claim? An irrelevant source escalates like an unverifiable one
9. Daniel brand     Aurecon Green on Anna's emphasis, everything else grey; audit all visual
10. Orchestrator    assemble into the chassis (single writer), assign [n], render bibliography,
                    one ground-truth render
11. Fiona visual QA render every slide to an image and inspect the ARTEFACT, not the spec -
                    clipped text, overlapping direct labels, collisions, off-canvas
                    elements, F1-F4 in the render, two green moments. Blocking defects
                    reopen the exhibit (beats the freeze - a chart that can't be read is
                    broken, not cosmetic); rebuild loop capped at 2 passes. Covers every
                    exhibit type, closing the gap where tables and diagrams skip Cooper
12. Anna audit      dylan-rules Audit mode turned on the pipeline's own output: L2
                    titles-only read, T1 per slide, Q1-Q3 deck-wide - the deck-emergent
                    checks no per-exhibit stage can own. Flags batch into the delivery
                    pack alongside open decisions
13. George scrutiny the assembled pass: attack the finished argument as a skeptical
                    client reading it standalone. Everything upstream verified the deck
                    is CORRECT; George asks whether the argument survives a hostile
                    room. Advisory only - challenges land in `scrutiny`, appear in the
                    delivery pack, and NEVER block. Only the human resolves them:
                    'addressed' or 'accepted_risk' - both legitimate, both recorded
```

## Routing by exhibit type

One flag Anna sets per exhibit. `chart` -> Ben + Cooper. `table` / `stat` /
`callout` -> built straight to the `dylan-rules` F-rules and `aureconed`, skips
Cooper. `diagram` (rare) -> assembler builds from native shapes, Daniel brands,
skips Cooper. Ben and Cooper are chart-only; running Tufte criteria on a table is
a category error. **Every** exhibit type, Cooper-scored or not, passes through
Fiona's visual QA at the end - the render is inspected regardless of route.

## The gates (enforced in `orchestrator.py`)

- **One human gate** - storyline sign-off, at the front. Everything needing the
  human batches into `decisions`.
- **Cooper-Ben loop** - cap 5 rebuilds, pass threshold 8, and rebuilds are
  *directed*: Cooper's ranked fixes (mechanical + perceptual, B/C-tagged) go
  into Ben's rebuild brief. **Early exit** - a rebuild that fails to improve
  the score escalates immediately rather than burning the cap; a non-converging
  loop is information, not something to retry blindly. Freeze flips on at
  `branded`.
- **Freeze override** - a frozen chart reopens to `needs_rebuild` the moment
  Edward flags an integrity failure, Anna flags a contradiction, or Fiona logs
  a **blocking** visual defect. Cosmetic passes cannot break a freeze; factual
  and legibility failures always do - a chart that cannot be read is a broken
  chart, not a styling preference. Fiona's `minor` defects never break a
  freeze; they batch into the delivery pack.
- **George is not a gate** - by design. His challenges are the questions the
  client will ask in the room; the pipeline surfaces them, the human answers
  them. An open challenge never blocks assembly or delivery, george cannot
  write `resolution`, and `accepted_risk` is a first-class outcome - a
  judgement call recorded in the manifest rather than an oversight.
- **Relevance gate** - Edward's check is "legitimate + relevant", and relevance
  is judgement, not arithmetic: does the document actually support the claim,
  or merely mention the topic? An irrelevant source escalates exactly like an
  unverifiable one.
- **Verification gate** - nothing assembles while any source is not `verified`
  or any figure is not `verified`. **Unverifiable is a blocking defect, not a
  footnote** - a claim whose source cannot be inspected must be sourced or pulled.
- **Escalation caps** - a figure mismatch/unanchored or an unverifiable source
  routes back to Anna; at 2 rounds it becomes a `hard_stop` and the stage blocks
  until the human resolves it.

## The manifest

Single source of truth. Normalised, not nested: `slides`, `exhibits`, `figures`,
`sources` are flat collections cross-referenced by id, so each agent patches only
its own rows. Shape and enums are in `manifest.schema.json`; cross-reference
integrity and the gates are enforced by the orchestrator.

Two integrity structures Edward owns:
- **Number ledger** (`figures[]`) - `shown -> anchor -> transform -> source_value
  -> verification`. Provenance is captured upstream by Anna/Ben so Edward
  verifies a specific claim against a specific location, never re-derives.
- **Reference registry** (`sources[]`) - `claim -> source -> [n] -> bibliography
  entry -> verification + relevance`. The orchestrator assigns `[n]`
  deterministically (order of first appearance) and renders the bibliography
  appendix from this. Edward is its auditor.

## Running it

`python orchestrator.py` runs a worked example through every gate (ownership
rejection, freeze override, the verification gate, the escalation cap, then
resolution and assembly).

Agents are **stateless**: each receives a read-only manifest view and returns a
**patch** - a list of `{op, path, value}`. The orchestrator validates the agent
is allowed to write each path (the `OWNERSHIP` map), applies the patch atomically,
logs it, and runs the gate hooks. Only the orchestrator mutates the manifest -
that is what makes the autonomous back half safe. The `OWNERSHIP` map is the
policy; edit it to change who-writes-what.

## Inputs

At t=0 the orchestrator expects completed analysis plus the **source materials**
behind it. `inputs.source_materials[].in_hand` gates verification: a source with
the document attached can be checked for legitimacy and relevance; a source
that's only a citation can only be checked for well-formedness and is flagged
unverifiable. For real legitimacy checking, hand over the documents, not just
citations pointing at them.

## What's built, and what's next

Built and tested end to end, offline:
- the **control spine** - the manifest, the schema, the single writer, every gate
- the **assembler** (`assembler.js`) - reads a verified manifest and builds the
  actual .pptx with PptxGenJS, on the Aurecon brand, native objects only (F4),
  reproducing the chassis frame from a defined master and rendering the numbered
  bibliography from the source registry. It refuses an unverified manifest.
- the **agent adapters** (`adapters.py`) and the **runner** (`run_pipeline.py`) -
  each role returns a patch the orchestrator validates and applies. The hard
  gates stay mechanical: **Cooper's** rubric and **Edward's** arithmetic never
  run on a model. Their judgement halves do - Cooper's perceptual pass
  (understood simply, direct-label fit, default-challenge) and Edward's
  relevance check both wire to the model and fail safe to the mechanical gate
  if the pass errors. The generative roles - **Anna** (storyline, reconcile,
  audit), **Ben**, **Daniel**, **Fiona** - each carry their real SKILL.md or
  QA brief as the system prompt with an offline stub, so the loop runs without
  an API key. `python run_pipeline.py` drives a signed-off seed through
  build -> score -> reconcile -> verify -> brand -> assemble -> visual QA ->
  audit to a built deck, including the escalation and resolution when a source
  is not yet in hand. Fiona's render step uses LibreOffice + pdftoppm when
  present and degrades gracefully when not.

To go live: set `MODEL = ClaudeModel()` in `run_pipeline.py`. The three generative
adapters then execute their skills against Claude instead of stubbing; the wiring
(system prompt = the skill's SKILL.md, return a JSON `{op, path, value}` patch) is
already in `adapters.py`. The mechanical adapters do not change - you never want a
model doing the arithmetic or the score.

The one remaining manual stage is the interactive front half - Anna's audience
interview and the human storyline sign-off - which by design needs a person.
`AnnaStoryline` carries that prompt; everything after the gate is automated.

## Boundaries

This skill owns coordination, the manifest, the gates, and the write. It defers
every domain to its skill - narrative and structure to `dylan-rules`, chart
internals to `render-tufte-chart` and `assess-graphical-excellence`, brand to
`aureconed`, the .pptx itself to `pptx`. It never re-implements their rules; it
calls them in order and enforces what happens between them.

## Running

```
python orchestrator.py     # runs the gate demo; emits example_manifest_verified.json
npm install                # once - pulls pptxgenjs
node assembler.js          # builds deck.pptx from the verified manifest

python run_pipeline.py     # drives the whole back half through the adapters to a deck
```

`assembler.js [manifest.json] [out.pptx]` takes optional paths; it defaults to the
verified example and `deck.pptx`. Visual-QA the result by rendering to images
(see the `pptx` skill).

## Files

- `orchestrator.py` - the control spine and the worked gate demo
- `adapters.py` - the role adapters (incl. Fiona visual QA, Anna audit, George
  scrutiny) + the pluggable model backend (stub / Claude) + `render_deck_to_images`
- `run_pipeline.py` - drives the back half through the adapters to a built deck
- `assembler.js` - builds a verified manifest into a branded .pptx (PptxGenJS)
- `manifest.schema.json` - the manifest contract (JSON Schema 2020-12)
- `example_manifest.json` / `example_manifest_verified.json` - gate-demo input / output
- `example_seed.json` - a signed-off seed the runner starts from
- `example_sources.json` - stands in for the source documents Edward reads
- `assets/aurecon_logo.png` - the brand frame lifted from the cleaned chassis
- `package.json` - declares the pptxgenjs dependency
