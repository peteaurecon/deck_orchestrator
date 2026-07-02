---
name: aureconed
description: Apply Aurecon's house visual identity to any slide deck or presentation built for an Aurecon audience or client - the brand colour scheme (Aurecon Green and the Aurecon grey scale on white), Arial typography, widescreen layout, and minimal-decoration formatting. Use this whenever building, restyling, theming, or formatting a deck, slides, or PowerPoint that will carry the Aurecon brand, or whenever the user mentions Aurecon, an Aurecon client, or wants "on-brand" slides - even if they only ask for the colours or fonts. This skill supplies the visual layer only; pair it with the deck-narrative and Tufte chart skills for storyline and chart internals.
---

# Aureconed

The Aurecon house-style layer. It owns one thing: how an Aurecon deck should
look - palette, type, layout, and the formatting rules that keep it on-brand and
uncluttered. It does not own the narrative or the chart internals.

Where this sits in the stack:

| Concern | Skill |
|---|---|
| Storyline, slide order, action titles, one-message-per-slide | the deck-narrative skill |
| Whether a chart is good / what genre to use / chartjunk | the chart-assessment skill |
| Producing a clean, honest chart | the chart-render skill |
| **How the deck looks for an Aurecon audience** | **this skill** |

Apply this skill's palette and formatting on top of those. They decide what goes
on the slide; this decides how it is dressed.

---

## Palette

Three tiers, used strictly in order. Primary and secondary carry almost every
deck. Tertiary is a release valve for data only. Colour is functional - it marks
the point, it does not decorate.

### Primary - the default deck

| Name | Hex | Where to use it |
|---|---|---|
| Aurecon Green | `89C925` | The accent. Marks, fills, ticks, the highlighted data series, shape accents, the accent word on a dark cover. **Not text on white** - it is too light to read (see accessibility). |
| Aurecon Grey | `373A36` | Primary text - titles and body on white. Also the default dark surface for full-bleed cover and closing slides. |
| White | `FFFFFF` | Content-slide background. The default. |

### Secondary - the grey scale, use freely

| Name | Hex | Where to use it |
|---|---|---|
| Aurecon Grey 2 | `4E5859` | Secondary text, supporting copy. |
| Aurecon Grey 3 | `8E9C9C` | Muted labels, captions, footers, chart axis labels. |
| Aurecon Grey 4 | `BBC6C3` | Hairlines, table rules, thin dividers, subtle neutral fills. |
| Aurecon Grey 5 | `1C1B1C` | The deepest dark - maximum-contrast text, or a deeper cover background. |

### Tertiary - graphs and infographics only

Use **only** when a chart or infographic has more categories than the primary
and secondary palette can carry. Never for slide furniture, text, or fills
outside a data graphic.

| Name | Hex |
|---|---|
| Aurecon Dark Green | `577740` |
| Aurecon Dark Blue | `3C556A` |
| Aurecon Yellow | `FCD672` |
| Aurecon Melon | `EFA693` |
| Aurecon Teal Blue | `3CB2B1` |
| Accessible Green | `6AA41E` |

**Order of use: primary first, then secondary, and reach for tertiary only once
those are exhausted.**

### Accessibility - green as text

`89C925` is too light to read as type on white. When you need **green text**, use
**Accessible Green `6AA41E`**, and only for **bold or large** fonts on white or a
very light background. Everywhere else, green stays a mark or a fill in `89C925`,
never small green type on white. On a dark cover, `89C925` reads well and is the
correct accent there.

- One green moment per slide. If two things are green, nothing is.
- Never substitute another green (e.g. sea green `2E8B57`) for Aurecon Green.
- No cream or beige backgrounds. White or a dark Aurecon grey only.

---

## Typography

Arial throughout, **minimum 11pt** anywhere on the slide.

| Element | Size | Weight | Colour |
|---|---|---|---|
| Eyebrow / kicker (caps, charSpacing ~2) | 12pt | bold | Grey 2 `4E5859` |
| Slide title (action title) | 26-30pt | bold | Aurecon Grey `373A36` |
| Section header | 18-20pt | bold | Aurecon Grey `373A36` |
| Body / table text | 13-15pt | regular | Aurecon Grey `373A36` or Grey 2 `4E5859` |
| Large stat numeral | 40-60pt | bold | Aurecon Grey `373A36`; or Accessible Green `6AA41E` if it must be green |
| Caption / footer / page number | 11pt | regular | Grey 3 `8E9C9C` |

Do not pair a second typeface. Arial carries the whole deck.

---

## Layout

- **Canvas**: 13.333" x 7.5" widescreen (PptxGenJS `LAYOUT_WIDE`, or a custom
  layout of those exact dimensions).
- **Margins**: 0.5" minimum; 0.5-0.65" is the working range. Keep them identical
  on every slide so elements sit on a shared grid.
- **Lines**: every rule, border, divider and axis line is **1/2 pt or 1/4 pt** -
  nothing else. Half point for visible structure; quarter point for the quietest
  hairlines.
- **Footer**: a short deck label left, slide number right, 11pt Grey 3, in the
  same position on every slide. Cover and closer can omit it.
- **Sandwich (recommended)**: an Aurecon Grey `373A36` (or Grey 5 `1C1B1C`) cover
  and closer, white content slides between them.

---

## Formatting rules

These keep the deck minimal and on-brand. Build everything as **native PptxGenJS
objects** - charts, tables, shapes, lines. Never paste a screenshot or exported
image of a chart or table; a flattened picture cannot be edited, ignores the
theme, and blurs on zoom.

**Tables**
- White rows. No zebra striping, no filled row backgrounds.
- Horizontal hairlines only, Grey 4 `BBC6C3` at 1/2 pt (or 1/4 pt). Drop vertical
  rules.
- Header row bold in Aurecon Grey `373A36`.
- Minimum 11pt text.

**Charts**
- The series that matters: Aurecon Green `89C925`. Other series: the grey scale,
  `4E5859` then `8E9C9C` then `BBC6C3`. Only once primary and secondary are
  exhausted, draw from the tertiary palette - in its listed order.
- No gridlines, or a single faint Grey 4 `BBC6C3` hairline at major ticks only.
- No legend where a direct end-label works. No chart border. Thin line weights
  (1/2 pt or 1/4 pt).
- No 3-D, no shadows, no gradients - on data or any other object.

**Citations and bibliography**
- Citation markers are superscript `[n]` in Aurecon Grey `373A36` (body colour) -
  never green, never boxed. Inline at the point of use, never a per-slide
  "Source:" footer line.
- The bibliography is an appendix slide: a plain numbered list, Arial 11pt
  minimum, Aurecon Grey `373A36` on white, no banding, hairlines and margins as
  any other content slide.

**Decoration - what to never add**
- No accent line or underline beneath titles. Use whitespace instead.
- No decorative colour bars, sidebar stripes, or card-edge accent strips. To set a
  card apart, use a subtle Grey 4 fill - never a shadow, never an edge stripe.
- No drop shadows, bevels, glows, or 3-D on any object - no exceptions. A flat
  Grey 4 (or near-white) fill is the only way to lift a card off the page.

---

## Build tokens (PptxGenJS)

A ready-to-paste colour token block and helper snippets - title block with no
underline, hairline table options, on-brand native chart options - are in
`references/pptxgenjs-tokens.md`. Read that file when generating the actual deck
so the build matches this spec exactly.

---

## Brand lint (machine-checkable)

For an automated QA pass over a rendered or built deck, these are the brand
rules that can be verified as concrete assertions - no judgement required.
Each failure names its check:

- **BL1 One green moment** - at most one `89C925`/`6AA41E` element per content
  slide.
- **BL2 No off-brand green** - no green hex outside `89C925`, `6AA41E`,
  `577740` (tertiary, charts only). `2E8B57` is an automatic fail.
- **BL3 Green never small type on white** - `89C925` appears only as mark/fill;
  green text is `6AA41E`, bold or ≥18pt, on white/light only.
- **BL4 Line weights** - every rule, border, divider, and axis line is 0.5pt or
  0.25pt exactly.
- **BL5 Type floor** - no text below 11pt; Arial only.
- **BL6 No decoration** - zero shadows, bevels, glows, 3-D, gradients, title
  underlines, or edge stripes anywhere in the XML.
- **BL7 Tables** - no cell fills except header treatments; horizontal rules
  only, `BBC6C3`.
- **BL8 Backgrounds** - white content slides; covers/closers only in `373A36`
  or `1C1B1C`; nothing cream or beige.

A visual-QA agent should walk BL1-BL8 against the rendered slides and report
each violation with its code, slide, and object.

## What good looks like

A white deck in Arial, anchored by Aurecon Grey text and Grey 4 hairlines, with
Aurecon Green appearing once per slide on the thing that matters - and a dark
Aurecon Grey cover and closer to frame it. Green type only ever appears as
Accessible Green, bold or large, on white; tertiary colours only inside a chart
that needed them. No stripes, no shadows, no banded tables, no second
font, no off-brand green, and every line at 1/2 pt or 1/4 pt.
