// Convert docs/index.md -> a styled Word document.
// Written for the markdown subset this tutorial actually uses.

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  PageBreak, TableOfContents, Header, Footer, PageNumber, ExternalHyperlink,
  PageOrientation, LevelFormat, convertInchesToTwip,
} = require("docx");

const SRC = process.argv[2];
const OUT = process.argv[3];
// Optional cover credit line. Defaults to this repo so the tutorial build
// needs no extra argument.
const COVER_NOTE = process.argv[4] || "github.com/hoqugr-beep/claude-code-tutorial";

// ---------- page geometry (US Letter, 1in margins) ----------
const PAGE_W = 12240, PAGE_H = 15840, MARGIN = 1440;
const CONTENT_W = PAGE_W - MARGIN * 2;   // 9360 DXA

// ---------- palette ----------
const INK = "1A2E2A";
const ACCENT = "0F5C4E";
const MUTED = "5C6B66";
const CODE_BG = "F2F5F3";
const CODE_FG = "1F2D29";
const HEAD_BG = "E4EDE9";
const RULE = "C9D6D0";

const BODY_FONT = "Calibri";
const CODE_FONT = "Consolas";

// ================= markdown parsing =================

// Split into block tokens. Fenced code is consumed first so that shell
// comments inside fences are never mistaken for headings.
function tokenize(md) {
  const lines = md.split(/\r?\n/);
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // fenced code
    const fence = line.match(/^```+\s*(\S*)/);
    if (fence) {
      const lang = fence[1] || "";
      const body = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) body.push(lines[i++]);
      i++; // closing fence
      blocks.push({ type: "code", lang, lines: body });
      continue;
    }

    if (!line.trim()) { i++; continue; }

    // heading
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) { blocks.push({ type: "heading", level: h[1].length, text: h[2].trim() }); i++; continue; }

    // horizontal rule
    if (/^(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) { blocks.push({ type: "hr" }); i++; continue; }

    // table: a header row followed by a delimiter row
    if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1])) {
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(lines[i++]);
      const cells = rows
        .filter((r) => !/^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(r))
        .map((r) => r.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim()));
      blocks.push({ type: "table", rows: cells });
      continue;
    }

    // blockquote
    if (/^>\s?/.test(line)) {
      const body = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) body.push(lines[i++].replace(/^>\s?/, ""));
      blocks.push({ type: "quote", text: body.join(" ").trim() });
      continue;
    }

    // list (unordered or ordered), possibly indented
    const li = line.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
    if (li) {
      const items = [];
      while (i < lines.length) {
        const m = lines[i].match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
        if (!m) {
          // continuation line belonging to the previous item
          if (items.length && lines[i].trim() && /^\s{2,}\S/.test(lines[i])) {
            items[items.length - 1].text += " " + lines[i].trim();
            i++; continue;
          }
          break;
        }
        items.push({
          indent: Math.floor(m[1].replace(/\t/g, "    ").length / 2),
          ordered: /\d/.test(m[2]),
          text: m[3].trim(),
        });
        i++;
      }
      blocks.push({ type: "list", items });
      continue;
    }

    // paragraph
    const body = [];
    while (i < lines.length && lines[i].trim() &&
           !/^(#{1,6}\s|```|>\s?|\s*\|)/.test(lines[i]) &&
           !/^(-{3,}|\*{3,}|_{3,})\s*$/.test(lines[i]) &&
           !/^(\s*)([-*+]|\d+[.)])\s+/.test(lines[i])) {
      body.push(lines[i++]);
    }
    if (body.length) blocks.push({ type: "para", text: body.join(" ").trim() });
    else i++;
  }
  return blocks;
}

// ---------- inline formatting -> TextRun[] ----------
// Code spans are matched first so ** inside backticks stays literal.
const INLINE = /(`[^`]+`)|(\*\*\*[^*]+\*\*\*)|(\*\*[^*]+\*\*)|(\[[^\]]*\]\([^)]*\))|(\*[^*\n]+\*)|(_[^_\n]+_)/g;

function runs(text, base = {}) {
  const out = [];
  let last = 0;
  let m;
  INLINE.lastIndex = 0;
  while ((m = INLINE.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const tok = m[0];

    if (tok.startsWith("`")) {
      out.push(new TextRun({
        text: tok.slice(1, -1), font: CODE_FONT, size: 19,
        color: CODE_FG, shading: { type: ShadingType.CLEAR, fill: CODE_BG },
        ...base,
      }));
    } else if (tok.startsWith("***")) {
      out.push(new TextRun({ text: tok.slice(3, -3), bold: true, italics: true, ...base }));
    } else if (tok.startsWith("**")) {
      out.push(new TextRun({ text: tok.slice(2, -2), bold: true, ...base }));
    } else if (tok.startsWith("[")) {
      const lm = tok.match(/^\[([^\]]*)\]\(([^)]*)\)$/);
      const label = lm[1] || lm[2];
      const href = lm[2];
      if (/^https?:\/\//.test(href)) {
        out.push(new ExternalHyperlink({
          link: href,
          children: [new TextRun({ text: label, style: "Hyperlink", ...base })],
        }));
      } else {
        // in-document anchor from the source markdown — keep the words, drop the link
        out.push(new TextRun({ text: label, ...base }));
      }
    } else {
      out.push(new TextRun({ text: tok.slice(1, -1), italics: true, ...base }));
    }
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out.length ? out : [new TextRun({ text: "", ...base })];
}

const plain = (t) => t.replace(/[`*_]/g, "").replace(/\[([^\]]*)\]\([^)]*\)/g, "$1");

// ================= docx emission =================

const HEADING_FOR = {
  1: HeadingLevel.HEADING_1,
  2: HeadingLevel.HEADING_1, // markdown "##" sections are the document's chapters
  3: HeadingLevel.HEADING_2,
  4: HeadingLevel.HEADING_3,
  5: HeadingLevel.HEADING_4,
  6: HeadingLevel.HEADING_4,
};

function codeBlock(block) {
  const out = [];
  const lines = block.lines.length ? block.lines : [""];
  lines.forEach((line, idx) => {
    // Left edge only. pBdr children are order-enforced by the schema
    // (top, left, bottom, right), but docx-js serialises them top, bottom,
    // left — so any combination including bottom produces an invalid document
    // that strict readers refuse to open. The shading already delimits the
    // block, so the accent rail alone is enough.
    const border = { left: { style: BorderStyle.SINGLE, size: 18, color: ACCENT, space: 8 } };

    out.push(new Paragraph({
      spacing: { before: idx === 0 ? 120 : 0, after: idx === lines.length - 1 ? 160 : 0, line: 240 },
      shading: { type: ShadingType.CLEAR, fill: CODE_BG },
      border,
      indent: { left: 120, right: 120 },
      children: [new TextRun({
        // leading spaces collapse in Word unless made non-breaking
        text: line.replace(/^ +/, (s) => " ".repeat(s.length)) || " ",
        font: CODE_FONT, size: 17, color: CODE_FG,
      })],
    }));
  });
  return out;
}

function tableBlock(block) {
  const rows = block.rows;
  if (!rows.length) return [];
  const colCount = Math.max(...rows.map((r) => r.length));

  // Weight columns by longest cell so narrow columns don't get equal space.
  const weights = Array.from({ length: colCount }, (_, c) =>
    Math.max(6, ...rows.map((r) => plain(r[c] || "").length)));
  const totalWeight = weights.reduce((a, b) => a + b, 0);
  let widths = weights.map((w) => Math.max(900, Math.round((w / totalWeight) * CONTENT_W)));
  // normalise so the columns sum exactly to the table width
  const drift = CONTENT_W - widths.reduce((a, b) => a + b, 0);
  widths[widths.length - 1] += drift;

  const border = { style: BorderStyle.SINGLE, size: 2, color: RULE };
  const tableRows = rows.map((cells, rowIdx) => new TableRow({
    tableHeader: rowIdx === 0,
    children: Array.from({ length: colCount }, (_, c) => new TableCell({
      width: { size: widths[c], type: WidthType.DXA },
      shading: rowIdx === 0 ? { type: ShadingType.CLEAR, fill: HEAD_BG } : undefined,
      margins: { top: 60, bottom: 60, left: 110, right: 110 },
      children: [new Paragraph({
        spacing: { before: 0, after: 0, line: 240 },
        children: runs(cells[c] || "", rowIdx === 0 ? { bold: true, color: INK } : {}),
      })],
    })),
  }));

  return [
    new Table({
      columnWidths: widths,
      width: { size: CONTENT_W, type: WidthType.DXA },
      borders: { top: border, bottom: border, left: border, right: border,
                 insideHorizontal: border, insideVertical: border },
      rows: tableRows,
    }),
    new Paragraph({ spacing: { after: 160 }, children: [] }),
  ];
}

function render(blocks) {
  const out = [];
  let seenFirstSection = false;

  blocks.forEach((b, idx) => {
    switch (b.type) {
      case "heading": {
        const isChapter = b.level <= 2;
        // Start each chapter on a fresh page, but don't leave a blank first page.
        const children = [];
        if (isChapter && seenFirstSection) children.push(new PageBreak());
        if (isChapter) seenFirstSection = true;
        children.push(...runs(b.text));
        out.push(new Paragraph({
          heading: HEADING_FOR[b.level],
          spacing: { before: isChapter ? 0 : 260, after: 140 },
          keepNext: true,
          children,
        }));
        break;
      }
      case "para":
        out.push(new Paragraph({
          spacing: { after: 140, line: 276 },
          children: runs(b.text),
        }));
        break;
      case "code":
        out.push(...codeBlock(b));
        break;
      case "table":
        out.push(...tableBlock(b));
        break;
      case "quote":
        out.push(new Paragraph({
          spacing: { before: 120, after: 160, line: 276 },
          indent: { left: 240, right: 240 },
          border: { left: { style: BorderStyle.SINGLE, size: 18, color: ACCENT, space: 10 } },
          shading: { type: ShadingType.CLEAR, fill: CODE_BG },
          children: runs(b.text, { color: MUTED }),
        }));
        break;
      case "list":
        b.items.forEach((item) => {
          out.push(new Paragraph({
            numbering: {
              reference: item.ordered ? "ordered" : "bullets",
              level: Math.min(item.indent, 2),
            },
            spacing: { after: 60, line: 276 },
            children: runs(item.text),
          }));
        });
        out.push(new Paragraph({ spacing: { after: 80 }, children: [] }));
        break;
      case "hr": {
        // A rule immediately before a chapter heading is redundant with the
        // page break that heading already carries.
        const next = blocks[idx + 1];
        if (next && next.type === "heading" && next.level <= 2) break;
        out.push(new Paragraph({
          spacing: { before: 100, after: 160 },
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE, space: 4 } },
          children: [],
        }));
        break;
      }
    }
  });
  return out;
}

// ================= assemble =================

const raw = fs.readFileSync(SRC, "utf8");
let blocks = tokenize(raw);

// Drop the hand-written contents list — Word gets a real, page-numbered TOC.
const tocStart = blocks.findIndex((b) => b.type === "heading" && /table of contents/i.test(b.text));
if (tocStart !== -1) {
  let end = tocStart + 1;
  while (end < blocks.length && !(blocks[end].type === "heading" && blocks[end].level <= 2)) end++;
  blocks.splice(tocStart, end - tocStart);
}

// Title and the "Last Updated" line become the cover; drop them from the flow.
const titleBlock = blocks.find((b) => b.type === "heading" && b.level === 1);
const title = titleBlock ? titleBlock.text : "Untitled";
// Remove the title before anything else looks for "the first chapter" — the
// H1 is itself a level-1 heading, so leaving it in makes that search match at
// index 0 and swallow the front matter that follows.
blocks = blocks.filter((b) => b !== titleBlock);

let subtitle = "";
const subIdx = blocks.findIndex((b) => b.type === "heading" && b.level === 3);
if (subIdx !== -1 && subIdx < 3) { subtitle = blocks[subIdx].text; blocks.splice(subIdx, 1); }

// Any blockquote ahead of the first chapter is front matter, not body text —
// it belongs on the cover rather than stranded after the contents page.
const firstChapter = blocks.findIndex((b) => b.type === "heading" && b.level <= 2);
const metaIdx = blocks.findIndex(
  (b, i) => b.type === "quote" && (firstChapter === -1 || i < firstChapter));
let meta = "";
if (metaIdx !== -1) { meta = plain(blocks[metaIdx].text); blocks.splice(metaIdx, 1); }
// leading rules left over from the front matter
while (blocks.length && blocks[0].type === "hr") blocks.shift();

const cover = [
  new Paragraph({ spacing: { before: 2600, after: 0 }, children: [
    new TextRun({ text: title, bold: true, size: 56, color: INK, font: BODY_FONT }),
  ]}),
  new Paragraph({ spacing: { before: 160, after: 0 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 10 } },
    children: [new TextRun({ text: subtitle || "From Beginner to Advanced", size: 28, color: ACCENT, font: BODY_FONT })],
  }),
  ...(meta ? [new Paragraph({ spacing: { before: 300 }, children: [
    new TextRun({ text: meta, size: 19, color: MUTED, font: BODY_FONT }),
  ]})] : []),
  new Paragraph({ spacing: { before: 120 }, children: [
    new TextRun({ text: COVER_NOTE, size: 19, color: MUTED, font: BODY_FONT }),
  ]}),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ spacing: { after: 200 }, heading: HeadingLevel.HEADING_1,
    children: [new TextRun("Contents")] }),
  new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-3" }),
  new Paragraph({ children: [new PageBreak()] }),
];

const doc = new Document({
  creator: "Claude Code Tutorial",
  title,
  description: subtitle,
  // Tells Word to populate the TOC when the document opens.
  features: { updateFields: true },
  styles: {
    default: {
      document: { run: { font: BODY_FONT, size: 21, color: INK } },
      heading1: { run: { font: BODY_FONT, size: 34, bold: true, color: ACCENT },
                  paragraph: { spacing: { before: 0, after: 160 } } },
      heading2: { run: { font: BODY_FONT, size: 26, bold: true, color: INK },
                  paragraph: { spacing: { before: 280, after: 120 } } },
      heading3: { run: { font: BODY_FONT, size: 23, bold: true, color: MUTED },
                  paragraph: { spacing: { before: 220, after: 100 } } },
      heading4: { run: { font: BODY_FONT, size: 21, bold: true, color: MUTED },
                  paragraph: { spacing: { before: 180, after: 80 } } },
    },
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [0, 1, 2].map((l) => ({
          level: l, format: LevelFormat.BULLET, text: ["•", "◦", "▪"][l],
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 380 + l * 340, hanging: 240 } } },
        })) },
      { reference: "ordered", levels: [0, 1, 2].map((l) => ({
          level: l, format: [LevelFormat.DECIMAL, LevelFormat.LOWER_LETTER, LevelFormat.LOWER_ROMAN][l],
          text: `%${l + 1}.`, alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 380 + l * 340, hanging: 240 } } },
        })) },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: PAGE_H, orientation: PageOrientation.PORTRAIT },
        margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
      },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        border: { bottom: { style: BorderStyle.SINGLE, size: 2, color: RULE, space: 6 } },
        children: [new TextRun({ text: title, size: 16, color: MUTED, font: BODY_FONT })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ children: [PageNumber.CURRENT], size: 16, color: MUTED, font: BODY_FONT })],
      })] }),
    },
    children: [...cover, ...render(blocks)],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  const counts = blocks.reduce((a, b) => ((a[b.type] = (a[b.type] || 0) + 1), a), {});
  console.log(`wrote ${OUT} (${(buf.length / 1024).toFixed(0)} KB)`);
  console.log("blocks:", JSON.stringify(counts));
});
