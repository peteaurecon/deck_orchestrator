---
name: dylan-rules
description: Govern the structure and narrative of a whole presentation, not just one chart. Use whenever someone is building, structuring, storylining, reworking, or reviewing a slide deck or presentation - or asks about action titles, slide order, the narrative of a deck, whether a deck "tells a story", or whether a deck is fit for a senior or skeptical audience. Trigger on "build a deck", "structure this presentation", "write the storyline", "review/audit my slides", "is this deck any good", "fix the flow", "tighten the narrative", or any request to make a presentation land with a specific audience. Runs in two modes - Build (interview to storyline to structured deck) and Audit (lint an existing deck against the rules). Either mode can ingest a .pptx or raw material to work from. Owns deck-level structure and slide-object formatting; defers chart internals to the Tufte charting skills.
---

# Dylan Rules

The deck-level skill. It sits above the chart skills: where `render-tufte-chart`
and `assess-graphical-excellence` govern a single graphic, Dylan Rules governs
the deck as an argument - the narrative, the slide sequence, the structural and
formatting rules that make a deck land.

These are Dylan's rules, supplemented with established deck-level best practice.
Apply them as hard rules, not suggestions. When a rule is broken, name it by its
code (e.g. "fails L2") and fix it.

## Two modes

Decide which one you are in before doing anything else.

- **Build** - producing or reworking a deck. Interview, set the storyline, then
  structure slides. The bulk of the work.
- **Audit** - checking an existing deck against the rules and returning ranked
  fixes. No new narrative invented unless asked.

"Rework this deck" is Build using the existing deck as input. "Is this any good"
is Audit.

## Ingesting input (either mode)

Both modes can start from material the user provides:

- **.pptx file** - extract it via the `pptx` skill (read its SKILL.md, use it to
  pull titles, slide order, tables, text, and exhibit inventory). Do not parse
  the XML by hand.
- **Raw material** - pasted findings, data, notes, a prior deck, a brief. Pull
  out the candidate message, the exhibits available, and the audience signals.

Always inventory what you were given before proposing anything: the implied
governing thought, the current title sequence, and the exhibits present.

---

## The rule catalogue

Grouped by what they govern. Codes are stable - use them in fixes.

### A - Audience matrix (the modulator)

Every rule below is tuned by four audience coordinates. Set them first; they
change what the governing thought even is. Read `references/audience-matrix.md`
for the full axes and the deck adjustments each one forces.

- **Altitude** - executive vs technical (or mixed)
- **Purpose** - decide vs persuade vs inform
- **Disposition** - friendly vs neutral vs skeptical
- **Delivery** - presented live vs sent standalone

### P - Process

- **P1 Storyline first.** Write the action-title sequence as prose and get
  sign-off *before* building a single slide. The ghost deck is the deliverable
  of the first pass. No slide construction until the storyline is agreed.

### L - Logic

- **L1 Answer first.** The deck answers one governing question, and the answer
  goes up front (slide 1 or an executive summary), never saved as a reveal.
  State the governing thought in one sentence before anything else follows.
- **L2 Horizontal logic.** Read the action titles in sequence, with nothing
  else on the slides. They must form the complete, coherent storyline on their
  own. If they don't, the deck has failed - this is the enforcement teeth for T1.
- **L3 One message per slide.** Each slide makes exactly one point; the body
  proves the title. Two ideas means two slides.

### T - Titles

- **T1 Action titles.** Every title is a full-sentence assertion that carries
  the slide's point, not a label. "Maintenance cost falls 22% by year 3", not
  "Maintenance cost". A title that names a topic instead of stating a finding
  fails T1.

### X - Exhibits

- **X1 Encoding hierarchy.** Prefer, in order: graphics/charts > tables >
  bullet points > prose text. Drop to a lower tier only when the higher one
  genuinely can't carry the point. Walls of text and gratuitous bullets are the
  default failure.
- **X2 Exhibit test.** Every exhibit (chart, table, or callout) must pass three
  questions, stated explicitly:
  1. **So what?** - the takeaway it proves.
  2. **Who cares?** - why it matters to *this* audience (ties back to A).
  3. **Can it be understood simply?** - legible at a glance, no decoding.
  An exhibit that sits as data with no takeaway fails X2.

### F - Formatting (slide objects)

These extend the chart-level minimal-ink rule to every object on the slide -
tables, dividers, callout boxes, connectors. Chart internals stay with the
Tufte skills.

- **F1 No banded tables.** No zebra striping or filled row backgrounds. Use thin
  horizontal rules only where they aid reading; white rows otherwise.
- **F2 Line weights.** Rules and borders are 1/2 pt or 1/4 pt. Nothing heavier
  unless it is doing deliberate emphasis work.
- **F3 No shadows.** No drop shadows, bevels, glows, or 3-D effects on any
  object.
- **F4 Native objects, not pictures.** Every exhibit on a pptx slide is a native
  PowerPoint object - native charts, shapes, lines, and tables built with
  PptxGenJS. Do not place a chart, table, or diagram as an embedded SVG/PNG
  picture of itself. Native objects stay editable, inherit the deck theme, and
  stay crisp; flattened images do none of that. A chart that arrives as a picture
  fails F4 - hand the slot to `render-tufte-chart` and build it natively.

### Q - QA sweep (deck-wide)

Run across the whole deck, not slide by slide.

- **Q1 Consistency.** Labels, title style (tense, capitalisation, length),
  and table formatting are consistent across every slide.
- **Q2 Grid and alignment.** Consistent margins; elements aligned to a shared
  grid, not eyeballed.
- **Q3 Numbers and units.** Decimal places, units, thousands separators, and
  date formats are consistent deck-wide.

### R - References (sourcing integrity)

Deck-wide integrity rules. Every quantitative claim is traceable to its source.

- **R1 Numbered citations.** Every sourced claim, figure, or exhibit carries a
  numbered marker `[n]` at the point of use. No per-slide "Source:" footer lines
  and no source names inline in the body - the marker only. Markers run in order
  of first appearance across the deck.
- **R2 Bibliography appendix.** Every `[n]` resolves to a single numbered
  bibliography held in an appendix at the back. One entry per source; a source
  reused on several slides keeps the same number. Full source details appear only
  in the bibliography, nowhere else.
- **R3 Every figure traces to a verifiable source.** Every number that reaches a
  slide - chart datapoint, axis value, title figure, callout stat, table cell -
  traces to a citation, and that citation traces to a source that can be
  inspected. A number with no anchor, or whose source cannot be verified, fails
  R3 - unverifiable is a defect to resolve, not a footnote to leave. This is the
  rule that makes the deck's quantitative claims auditable against the source
  material.

---

## Build workflow

1. **Ingest** any provided material (see above).
2. **Set audience coordinates (A).** Interview the user for the four axes.
   Do this before narrative - altitude and purpose shape the governing thought.
   Read `references/audience-matrix.md` and state the resulting adjustments.
3. **Establish the governing thought (L1).** One question, one answer, answer
   first. Confirm it with the user.
4. **Draft the storyline (P1).** Write the action-title sequence as prose - one
   line per slide, each an assertion (T1), the sequence forming the whole story
   (L2). Get explicit sign-off. Do not build slides before this.
5. **Structure each slide.** One message (L3), pick the exhibit by the encoding
   hierarchy (X1), make it pass the exhibit test (X2). For each chart slot, hand
   off to `render-tufte-chart`, which builds it as a native pptx object (F4).
   Tables and other objects follow F1-F4.
6. **Cite and compile (R1-R3).** As each sourced claim or figure lands on a
   slide, attach its numbered marker (R1) and register the source against the
   input analysis (R3). Compile the running registry into one numbered
   bibliography in an appendix (R2).
7. **Pre-flight QA (Q1-Q3, R1-R3).** Sweep the assembled deck for consistency,
   grid, number formatting, and source integrity before declaring it done.

If producing the actual .pptx, follow the user's house slide standards and use
the relevant build skill; Dylan Rules governs what goes on the slides, not the
rendering engine. Charts, tables, and diagrams go in as native PowerPoint
objects (PptxGenJS), never as embedded SVG/PNG pictures (F4).

## Audit workflow

1. **Ingest** the deck (.pptx via the `pptx` skill, or whatever was provided).
2. **Run the lint pass.** Read `references/lint-checklist.md` and walk every
   rule. The horizontal-logic test (L2) - reading the titles alone - is the
   single highest-signal check; do it first.
3. **Per slide**, flag failures of L3, T1, X1, X2, F1-F4 with the rule code.
4. **Deck-wide**, run Q1-Q3 and R1-R3 (source integrity).
5. **Hand chart-level problems down.** When a specific graphic is weak, route it
   to `assess-graphical-excellence` rather than diagnosing it here - that skill
   owns chartjunk, lie factor, and genre choice. Dylan Rules only flags that the
   exhibit fails X1/X2 at the deck level.
6. **Return ranked fixes**, highest impact first, each tagged with its rule code
   (see output format below).

---

## Orchestration (how it fits the toolkit)

Dylan Rules is the top of a three-skill stack. Keep the boundaries clean - do
not duplicate what the others own.

| Concern | Skill |
|---|---|
| Deck narrative, slide order, action titles, slide-object formatting | **Dylan Rules** (this skill) |
| Whether a specific chart is good, what's wrong, what genre to use | `assess-graphical-excellence` |
| Producing an actual Tufte-correct chart file | `render-tufte-chart` |
| Reading/parsing/writing the .pptx itself | `pptx` |
| Whether the argument survives a hostile reader (context, decomposition, backup defensibility) | `george` |

The X2 boundary with `george`: X2 asks "does this exhibit have a takeaway?";
George asks "does the takeaway survive scrutiny?" A slide can pass X2 cleanly
and still be an exposed flank. Dylan Rules never runs George's adversarial
questions, and George never re-litigates X2, T1, or L2.

Build mode sends chart slots *down* to `render-tufte-chart`. Audit mode sends
weak charts *down* to `assess-graphical-excellence`. Either mode reads a deck
*in* via `pptx`. Dylan Rules never assesses chart internals or emits chart files
itself.

**In an orchestrated build, run Audit mode on the pipeline's own output.** The
build stages enforce rules per slide and per exhibit as they go, but the
deck-emergent checks - L2 (do the titles alone tell the story), Q1-Q3
(consistency of title style, grid, and number formats) - can only be judged
once the whole deck exists. An assembled deck that has never been through the
Audit workflow is unreviewed by the very rules that built it; auditing your own
output is not optional polish, it is the closing of the loop.

## Output format

### Build - storyline draft (the P1 gate)
```
Audience: <altitude / purpose / disposition / delivery>
Governing thought: <one sentence, answer-first>

Storyline (action titles, in order):
1. <assertion>
2. <assertion>
...

Read top to bottom, these alone should tell the whole story (L2 check).
```

### Audit - ranked fixes
```
## Dylan Rules audit: <deck>
Audience read: <inferred coordinates, or stated assumption>
Horizontal-logic test (L2): <pass / fail - what the title-only read reveals>

### Fixes (highest impact first)
1. [<rule code>] slide <n> - <the problem> -> <the fix>
2. ...

### Deck-wide (Q)
- <consistency / grid / number issues>

### Routed to chart skills
- slide <n>: <chart> -> assess-graphical-excellence (fails X1/X2)
```

## What good looks like

A deck whose action titles, read alone, tell the complete story; one message per
slide; the answer up front; every exhibit earning its place against So what /
Who cares / understood simply; formatting clean and consistent; and the whole
thing pitched correctly for its audience. In Audit mode, every fix names its
rule and is ordered by impact, with chart-internal problems handed down rather
than guessed at.
