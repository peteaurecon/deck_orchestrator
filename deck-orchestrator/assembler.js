/*
 * assembler.js - the last stage of the deck-orchestrator loop.
 *
 * Reads a VERIFIED manifest and builds the actual .pptx with PptxGenJS, on the
 * Aurecon brand, native objects only (F4). It reproduces the cleaned chassis
 * frame - white ground, the Aurecon logo, the green divider, the footer hairline,
 * the page number - via a defined slide master, because PptxGenJS builds from
 * scratch and cannot open an existing .pptx. Brand values and the divider/footer
 * geometry were lifted from the chassis so the frame is faithful, not guessed.
 *
 * It is gated: a manifest with any unverified source or figure is refused. That
 * is the verification gate, enforced again at the point of build - nothing
 * unverifiable assembles.
 *
 * In the full loop the orchestrator hands Daniel's emphasis call and the source
 * registry through the manifest; here, chart colour follows exhibit.emphasis
 * (the one green series) and the bibliography is rendered from sources[].
 *
 * Run:  npm install pptxgenjs   then   node assembler.js [manifest.json]
 */

const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

// --- Aurecon brand (from the chassis theme) ---
const C = {
  green: "89C925", grey1: "373A36", grey2: "4E5859", grey3: "8E9C9C",
  grey4: "BBC6C3", white: "FFFFFF",
};
const FONT = "Arial";
const LOGO = path.join(__dirname, "assets", "aurecon_logo.png");

// frame geometry (inches), measured from chassis slideLayout8
const FRAME = {
  divider: { x: 0.59, y: 1.12, w: 12.17, width: 1.5 },
  hairline: { x: 0.56, y: 6.78, w: 12.20, width: 0.75 },
  title:   { x: 0.59, y: 0.42, w: 12.17, h: 0.62 },
  body:    { x: 0.59, y: 1.42, w: 12.17, h: 5.20 },
};

// --- the verification gate, re-enforced at build time ---
function guard(m) {
  const badS = (m.sources || []).filter((s) => s.verification !== "verified");
  const badF = (m.figures || []).filter((f) => f.verification !== "verified");
  if (badS.length || badF.length) {
    console.error("REFUSED: manifest is not verified - nothing unverifiable assembles.");
    badS.forEach((s) => console.error(`  source ${s.source_id}: ${s.verification}`));
    badF.forEach((f) => console.error(`  figure ${f.figure_id} (${f.shown}): ${f.verification}`));
    process.exit(2);
  }
}

function defineMaster(pptx) {
  pptx.defineSlideMaster({
    title: "AURECON",
    background: { color: C.white },
    objects: [
      { image: { path: LOGO, x: 0, y: 0, w: 13.333, h: 7.5 } }, // white ground + logo
      { line: { x: FRAME.divider.x, y: FRAME.divider.y, w: FRAME.divider.w, h: 0,
                line: { color: C.green, width: FRAME.divider.width } } },
      { line: { x: FRAME.hairline.x, y: FRAME.hairline.y, w: FRAME.hairline.w, h: 0,
                line: { color: C.grey4, width: FRAME.hairline.width } } },
    ],
    slideNumber: { x: 12.4, y: 6.95, w: 0.6, h: 0.3, fontFace: FONT, fontSize: 11,
                   color: C.grey3, align: "right" },
  });
}

const byId = (arr, key, id) => (arr || []).find((x) => x[key] === id);

function citationMap(m) {
  const map = {};
  (m.sources || []).forEach((s) => { if (s.citation) map[s.source_id] = s.citation; });
  return map;
}

function titleRuns(slide, citMap) {
  const runs = [{ text: slide.action_title || "", options: {} }];
  const nums = (slide.citations || []).map((c) => citMap[c]).filter(Boolean)
    .sort((a, b) => a - b);
  if (nums.length) {
    runs.push({ text: " [" + nums.join(",") + "]",
                options: { superscript: true, fontSize: 11, color: C.grey3 } });
  }
  return runs;
}

function addCover(pptx, m) {
  const s = pptx.addSlide({ masterName: "AURECON" });
  s.addText(m.meta.title || "Untitled", {
    x: 0.59, y: 2.7, w: 12.17, h: 1.3, fontFace: FONT, fontSize: 32, bold: true,
    color: C.grey1, align: "left", valign: "middle",
  });
  if (m.governing_thought) {
    s.addText(m.governing_thought, {
      x: 0.59, y: 4.0, w: 11.0, h: 1.0, fontFace: FONT, fontSize: 16, color: C.grey2,
    });
  }
}

// horizontal bars as native shapes: per-bar colour, direct value labels, no axes
function renderBars(pptx, s, ex) {
  const series = (ex.data_ref && ex.data_ref.plotted_series) || [];
  if (!series.length) return;
  const max = Math.max(...series.map((d) => d.value));
  const labelW = 2.0, valW = 1.1, barTrack = 6.0;
  const x0 = FRAME.body.x, top = FRAME.body.y + 0.2;
  const rowH = Math.min(0.66, (FRAME.body.h - 0.4) / series.length);
  const barH = rowH * 0.5;
  series.forEach((d, i) => {
    const y = top + i * rowH;
    const isEmph = ex.emphasis != null &&
      String(d.label).toLowerCase() === String(ex.emphasis).toLowerCase();
    const barW = Math.max(0.04, (d.value / max) * barTrack);
    s.addText(d.label, { x: x0, y, w: labelW, h: rowH, fontFace: FONT, fontSize: 12,
      color: C.grey1, align: "left", valign: "middle" });
    s.addShape(pptx.ShapeType.rect, { x: x0 + labelW, y: y + (rowH - barH) / 2,
      w: barW, h: barH, fill: { color: isEmph ? C.green : C.grey3 }, line: { type: "none" } });
    const val = d.value <= 1 ? Math.round(d.value * 100) + "%" : d.value;
    s.addText(String(val), { x: x0 + labelW + barW + 0.1, y, w: valW, h: rowH,
      fontFace: FONT, fontSize: 12, bold: isEmph, color: isEmph ? C.green : C.grey1,
      align: "left", valign: "middle" });
  });
}

function renderStat(pptx, s, ex, m) {
  const fig = byId(m.figures, "figure_id", (ex.figure_ids || [])[0]);
  const big = fig ? String(fig.shown) : "";
  const emph = ex.emphasis != null;
  s.addText(big, { x: FRAME.body.x + 0.3, y: 2.1, w: 7.0, h: 1.6, fontFace: FONT,
    fontSize: 54, bold: true, color: emph ? C.green : C.grey1, align: "left", valign: "middle" });
  if (ex.so_what) {
    s.addText(ex.so_what, { x: FRAME.body.x + 0.32, y: 3.6, w: 8.0, h: 0.8,
      fontFace: FONT, fontSize: 14, color: C.grey2 });
  }
}

function renderExhibit(pptx, s, ex, m) {
  if (!ex) return;
  if (ex.type === "chart") renderBars(pptx, s, ex);
  else if (ex.type === "stat") renderStat(pptx, s, ex, m);
  else {
    s.addText("[" + ex.type + " exhibit - " + (ex.so_what || "") + "]",
      { x: FRAME.body.x, y: FRAME.body.y, w: FRAME.body.w, h: 1.0, fontFace: FONT,
        fontSize: 12, italic: true, color: C.grey3 });
  }
}

function renderBody(s, lines) {
  const items = lines.map((t) => ({
    text: t,
    options: { fontFace: FONT, fontSize: 14, color: C.grey1, bullet: { code: "2022" },
               paraSpaceAfter: 12, breakLine: true },
  }));
  s.addText(items, { x: FRAME.body.x, y: FRAME.body.y, w: FRAME.body.w - 1.5,
    h: FRAME.body.h, valign: "top" });
}

function addContentSlide(pptx, slide, m, citMap) {
  const s = pptx.addSlide({ masterName: "AURECON" });
  s.addText(titleRuns(slide, citMap), {
    x: FRAME.title.x, y: FRAME.title.y, w: FRAME.title.w, h: FRAME.title.h,
    fontFace: FONT, fontSize: 18, bold: true, color: C.grey1, valign: "middle",
  });
  const ex = byId(m.exhibits, "exhibit_id", slide.exhibit_id);
  if (ex) renderExhibit(pptx, s, ex, m);
  else if (slide.body && slide.body.length) renderBody(s, slide.body);
}

function addBibliography(pptx, m) {
  const s = pptx.addSlide({ masterName: "AURECON" });
  s.addText("References", { x: FRAME.title.x, y: FRAME.title.y, w: FRAME.title.w,
    h: FRAME.title.h, fontFace: FONT, fontSize: 18, bold: true, color: C.grey1, valign: "middle" });
  const items = (m.sources || []).filter((x) => x.citation)
    .sort((a, b) => a.citation - b.citation)
    .map((x) => ({
      text: "[" + x.citation + "]  " + (x.bibliography_entry || x.claim || x.source_id),
      options: { fontFace: FONT, fontSize: 11, color: C.grey1, paraSpaceAfter: 8,
                 bullet: false, breakLine: true },
    }));
  s.addText(items, { x: FRAME.body.x, y: FRAME.body.y, w: FRAME.body.w, h: 5.0, valign: "top" });
}

async function build(manifestPath, outPath) {
  const m = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  guard(m);
  const citMap = citationMap(m);

  const pptx = new pptxgen();
  pptx.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
  pptx.author = "Aurecon";
  pptx.company = "Aurecon";
  pptx.title = m.meta.title || "";
  defineMaster(pptx);

  const slides = (m.slides || []).slice().sort((a, b) => a.order - b.order);
  for (const sl of slides) {
    if (sl.section === "cover") { addCover(pptx, m); continue; }
    if (sl.section === "appendix") { addBibliography(pptx, m); continue; }
    addContentSlide(pptx, sl, m, citMap);
  }

  await pptx.writeFile({ fileName: outPath });
  console.log(`built ${outPath}  (${slides.length} slides, stage=${m.meta.stage})`);
}

const manifestPath = process.argv[2] ||
  path.join(__dirname, "example_manifest_verified.json");
const outPath = process.argv[3] || path.join(__dirname, "deck.pptx");
build(manifestPath, outPath).catch((e) => { console.error(e); process.exit(1); });
