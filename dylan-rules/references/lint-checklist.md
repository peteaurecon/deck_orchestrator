# Lint checklist (Audit mode + Build pre-flight)

A mechanical walk of every enforceable rule. Use it as the main event in Audit
mode and as the pre-flight sweep at the end of Build. Each item is pass/fail with
its rule code; on fail, write the fix.

Run the deck-wide checks first (they are highest-signal), then the per-slide pass.

---

## Deck-wide (do these first)

**L2 - Horizontal logic (the single most important check).**
Strip everything off the slides except the titles. Read the titles in order.
- Do they form a complete, coherent argument on their own?
- Does the answer appear at the top, not the bottom (L1)?
- Are there gaps in the logic, or titles that don't advance the story?
A deck that fails the title-only read fails, full stop. This is where most decks
break.

**L1 - Answer first.**
Is the governing thought stated up front (slide 1 or exec summary)? Or is the
conclusion buried at the end as a reveal? If buried, the fix is to move it.

**Q1 - Consistency.**
- Title style uniform: tense, capitalisation, length, full-sentence form.
- Labels consistent across slides (same entity called the same thing).
- Table formatting identical slide to slide.

**Q2 - Grid and alignment.**
- Consistent margins on every slide.
- Elements aligned to a shared grid, not eyeballed.
- Repeated elements (logos, footers, page numbers) in the same place every time.

**Q3 - Numbers and units.**
- Decimal places consistent within a measure.
- Units stated and consistent.
- Thousands separators and date formats uniform.

**R2 - Bibliography appendix.**
- Does every citation marker `[n]` in the deck resolve to an entry in a single
  numbered bibliography held in an appendix?
- One entry per source, reused sources sharing one number? Orphan markers (no
  entry) and orphan entries (no marker) both fail.

**R3 - Every figure traces to a verifiable source.**
- Does every number on every slide - chart datapoint, axis value, title figure,
  callout, table cell - trace to a citation? An unsourced figure fails R3.
- Does each citation resolve to a source that can actually be inspected? A claim
  whose source cannot be verified fails - unverifiable is a defect to fix, not to
  footnote.

---

## Per-slide pass

For each slide, check in order:

**T1 - Action title.**
Is the title a full-sentence assertion that states the slide's finding? Or is it
a topic label ("Maintenance costs", "Background", "Approach")? A label fails -
rewrite it as the point the slide makes.

**L3 - One message per slide.**
Does the slide make exactly one point? If it carries two ideas, split it. If the
body wanders from the title, the title or the body is wrong.

**X1 - Encoding hierarchy.**
Is the content in the highest-justified tier - graphic > table > bullets > text?
A slide of bullets or prose that could have been a chart or table fails. Walls of
text are the default offender.

**X2 - Exhibit test.**
For every chart, table, or callout on the slide:
- **So what?** Is the takeaway explicit, or does the exhibit just sit there as
  data?
- **Who cares?** Is it relevant to this audience (per the matrix)?
- **Understood simply?** Legible at a glance, or does it need decoding?
An exhibit failing any of the three fails X2.

**F1 - No banded tables.**
Any zebra striping or filled row backgrounds? Strip to white rows with thin
rules only where needed.

**F2 - Line weights.**
Any rule or border heavier than 1/2 pt (or 1/4 pt)? Reduce.

**F3 - No shadows.**
Any drop shadows, bevels, glows, or 3-D? Remove.

**F4 - Native objects, not pictures.**
Is any chart, table, or diagram an embedded SVG/PNG picture of itself instead of
a native PowerPoint object (PptxGenJS native chart/shape/table)? Flatten-to-image
fails F4 - the object isn't editable, ignores the deck theme, and softens on
zoom. Hand the slot to `render-tufte-chart` to rebuild it natively.

**R1 - Numbered citation.**
Are sourced claims and figures marked with a numbered `[n]` at the point of use,
rather than a "Source:" footer line or a source name inline in the body? Bare or
missing markers fail.

---

## Routing chart problems down

When the exhibit test (X2) flags a chart as weak at the deck level, do not
diagnose the chart internals here. Route it to `assess-graphical-excellence`,
which owns chartjunk species, lie factor, genre choice, and the specific Tufte
remedies. Dylan Rules' job ends at "this exhibit fails X1/X2" - name it and hand
it down.

## Writing the fixes

Order by impact, not by slide number. A broken horizontal logic (L2) outranks a
shadow (F3). Each fix:

```
[<rule code>] slide <n> - <the problem> -> <the fix>
```

Lead the output with the L2 verdict, because if the storyline doesn't hold,
fixing formatting is rearranging deck chairs.
