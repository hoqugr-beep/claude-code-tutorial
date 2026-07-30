#!/usr/bin/env python3
"""Render the MkDocs-flavoured Markdown tutorial page to a styled PDF via reportlab."""
import re
import sys
import textwrap

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

PURPLE = colors.HexColor("#4527A0")
PURPLE_LT = colors.HexColor("#7E57C2")
INK = colors.HexColor("#1F2430")
MUTED = colors.HexColor("#6B7280")
CODE_BG = colors.HexColor("#F4F2F9")
CODE_FG = colors.HexColor("#2B2540")
RULE = colors.HexColor("#DDD8EA")
INLINE_CODE = colors.HexColor("#9C2D6B")

DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono%s.ttf"
try:
    pdfmetrics.registerFont(TTFont("Mono", DEJAVU % ""))
    pdfmetrics.registerFont(TTFont("Mono-Bold", DEJAVU % "-Bold"))
    pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="Mono-Bold")
    MONO, MONO_B = "Mono", "Mono-Bold"
except Exception:  # fall back to the base-14 metric font
    MONO, MONO_B = "Courier", "Courier-Bold"

ADMONITION = {
    "note": (colors.HexColor("#2E6BB8"), colors.HexColor("#EDF3FB"), "Note"),
    "tip": (colors.HexColor("#1E8E6A"), colors.HexColor("#EAF6F1"), "Tip"),
    "warning": (colors.HexColor("#C77700"), colors.HexColor("#FDF4E7"), "Warning"),
    "danger": (colors.HexColor("#C0392B"), colors.HexColor("#FBEDEB"), "Important"),
}

CODE_WRAP = 96
MARGIN = 0.8 * inch


# ---------------------------------------------------------------- inline markup
def inline(text):
    """Convert inline Markdown to reportlab intra-paragraph markup."""
    spans = []

    def stash(html):
        spans.append(html)
        return "\x00%d\x00" % (len(spans) - 1)

    # Code spans first so their contents escape further processing.
    def code_span(m):
        body = m.group(1).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return stash('<font face="%s" size="8.2" color="#%s">%s</font>'
                     % (MONO_B, INLINE_CODE.hexval()[2:], body))

    text = re.sub(r"`([^`]+)`", code_span, text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Links, then bold, then italic. Anchors that only exist inside the MkDocs site
    # can't be linked from a PDF, so they degrade to styled text or the live site URL.
    SITE = "https://hoqugr-beep.github.io/claude-code-tutorial/"

    def link(m):
        label, href = m.group(1), m.group(2)
        if href.startswith("index.md"):
            href = SITE + href[len("index.md"):]
        elif href.startswith("#"):
            return stash('<font color="#%s"><i>%s</i></font>'
                         % (PURPLE.hexval()[2:], label))
        elif not href.startswith(("http://", "https://", "mailto:")):
            return stash("<i>%s</i>" % label)
        return stash('<link href="%s" color="#%s"><u>%s</u></link>'
                     % (href, PURPLE.hexval()[2:], label))

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    # Non-greedy so bold spans may contain nested italics (**a *b* c**).
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", text)

    # Stashed spans can nest (a link label containing inline code), so restore until
    # no placeholders are left rather than in a single pass.
    while "\x00" in text:
        text = re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)
    return text


# -------------------------------------------------------------------- flowables
class Rule(Flowable):
    def __init__(self, width=None, thickness=0.6, color=RULE, pad=6):
        super().__init__()
        self._w, self.thickness, self.color, self.pad = width, thickness, color, pad
        self.height = pad * 2

    def wrap(self, aw, ah):
        self.width = self._w or aw
        return self.width, self.height

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, self.pad, self.width, self.pad)


def code_block(lines, styles):
    """A soft-shaded, wrapped monospace block."""
    out = []
    for raw in lines:
        raw = raw.replace("\t", "    ")
        if not raw.strip():
            out.append("")
            continue
        indent = len(raw) - len(raw.lstrip())
        wrapped = textwrap.wrap(
            raw, width=CODE_WRAP, subsequent_indent=" " * (indent + 2),
            break_long_words=True, break_on_hyphens=False, replace_whitespace=False,
            drop_whitespace=False,
        ) or [raw]
        out.extend(wrapped)
    body = Preformatted("\n".join(out), styles["code"])
    tbl = Table([[body]], colWidths=["100%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return tbl


def admonition(kind, title, inner, styles):
    accent, bg, default_title = ADMONITION.get(kind, ADMONITION["note"])
    flows = [Paragraph(inline(title or default_title), styles["admon_title"])]
    flows += render_blocks(inner, styles, in_admon=True)
    tbl = Table([["", flows]], colWidths=[4, None])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), accent),
        ("BACKGROUND", (1, 0), (1, 0), bg),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 0),
        ("TOPPADDING", (0, 0), (0, 0), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 10),
        ("RIGHTPADDING", (1, 0), (1, 0), 10),
        ("TOPPADDING", (1, 0), (1, 0), 8),
        ("BOTTOMPADDING", (1, 0), (1, 0), 4),
    ]))
    return tbl


def make_table(rows, styles):
    header, body = rows[0], rows[1:]
    ncols = max(len(r) for r in rows)
    data = []
    for i, row in enumerate(rows):
        cells = list(row) + [""] * (ncols - len(row))
        style = styles["th"] if i == 0 else styles["td"]
        data.append([Paragraph(inline(c), style) for c in cells])

    avail = LETTER[0] - 2 * MARGIN
    # Two signals per column: total content length (how much room it wants) and the
    # longest unbreakable token (how much it needs before words snap mid-word).
    CH = 5.1  # generous per-char width: the bold mono face at the inline-code size
    PAD = 13
    weights, floors = [], []
    for c in range(ncols):
        cells = [r[c] if c < len(r) else "" for r in rows]
        weights.append(max(max((len(x) for x in cells), default=0), 6))
        tokens = [t.strip("`*_[]()<>.,;:") for cell in cells for t in cell.split()]
        longest = max((len(t) for t in tokens), default=4)
        floors.append(min(longest * CH + PAD, avail * 0.42))

    if sum(floors) >= avail:  # pathological: just honour the floors proportionally
        widths = [f * avail / sum(floors) for f in floors]
    else:
        widths = [None] * ncols
        while True:
            free = avail - sum(w for w in widths if w is not None)
            wsum = sum(weights[c] for c in range(ncols) if widths[c] is None)
            short = [c for c in range(ncols)
                     if widths[c] is None and free * weights[c] / wsum < floors[c]]
            if not short:
                for c in range(ncols):
                    if widths[c] is None:
                        widths[c] = free * weights[c] / wsum
                break
            for c in short:
                widths[c] = floors[c]

    tbl = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    stripes = [("BACKGROUND", (0, r), (-1, r), colors.HexColor("#FAF9FD"))
               for r in range(1, len(data)) if r % 2 == 0]
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, PURPLE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ] + stripes))
    return tbl


# ------------------------------------------------------------------ block parse
def split_table_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def is_table_divider(line):
    return bool(re.fullmatch(r"\s*\|?[\s:\-|]+\|?\s*", line)) and "-" in line


def dedent(lines, n=4):
    return [l[n:] if len(l) >= n and l[:n].isspace() else l.lstrip() if l.strip() else ""
            for l in lines]


def render_blocks(lines, styles, in_admon=False):
    flows = []
    i = 0
    n = len(lines)
    body_style = styles["body_sm"] if in_admon else styles["body"]

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Fenced code
        if stripped.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            flows += [code_block(buf, styles), Spacer(1, 7)]
            continue

        # Admonition
        m = re.match(r'^!!!\s+(\w+)(?:\s+"([^"]*)")?\s*$', stripped)
        if m and not in_admon:
            kind, title = m.group(1).lower(), m.group(2)
            i += 1
            inner = []
            while i < n and (not lines[i].strip() or lines[i].startswith("    ")):
                inner.append(lines[i])
                i += 1
            while inner and not inner[-1].strip():
                inner.pop()
            flows += [admonition(kind, title, dedent(inner), styles), Spacer(1, 9)]
            continue

        # Headings
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            text = m.group(2)
            key = {1: "h1", 2: "h2", 3: "h3", 4: "h4"}[level]
            if level == 2:
                flows.append(Spacer(1, 6))
            flows.append(Paragraph(inline(text), styles[key]))
            if level <= 2:
                flows.append(Rule(thickness=1.0 if level == 1 else 0.6,
                                  color=PURPLE_LT if level <= 2 else RULE, pad=3))
            i += 1
            continue

        # Horizontal rule
        if re.fullmatch(r"-{3,}|\*{3,}", stripped):
            flows += [Spacer(1, 4), Rule(), Spacer(1, 4)]
            i += 1
            continue

        # Table
        if stripped.startswith("|") and i + 1 < n and is_table_divider(lines[i + 1]):
            rows = [split_table_row(lines[i])]
            i += 2
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_table_row(lines[i]))
                i += 1
            flows += [make_table(rows, styles), Spacer(1, 9)]
            continue

        # Lists (bullet or ordered), including indented continuation lines
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if m:
            ordered = not m.group(2) in ("-", "*")
            items = []
            while i < n:
                m2 = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if not m2:
                    break
                chunk = [m2.group(3)]
                i += 1
                # continuation / nested lines belong to this item
                while i < n and lines[i].strip() and not re.match(
                        r"^(\s*)([-*]|\d+\.)\s+", lines[i]) and lines[i].startswith(" "):
                    chunk.append(lines[i].strip())
                    i += 1
                kw = {"value": len(items) + 1} if ordered else {}
                items.append(ListItem(Paragraph(inline(" ".join(chunk)), body_style),
                                      leftIndent=16, **kw))
                if i < n and not lines[i].strip():
                    # blank line ends the list unless another item follows immediately
                    if i + 1 < n and re.match(r"^(\s*)([-*]|\d+\.)\s+", lines[i + 1]):
                        i += 1
                        continue
                    break
            list_kw = {"start": 1} if ordered else {"bulletFontName": "Helvetica-Bold"}
            flows.append(ListFlowable(
                items, bulletType="1" if ordered else "bullet",
                bulletFontSize=8.5, bulletColor=PURPLE_LT, leftIndent=16, **list_kw,
            ))
            flows.append(Spacer(1, 7))
            continue

        # Paragraph: gather until blank line or a new block starter
        buf = []
        while i < n and lines[i].strip():
            s = lines[i].strip()
            if (s.startswith("```") or s.startswith("!!!") or s.startswith("|")
                    or re.match(r"^#{1,4}\s", s) or re.fullmatch(r"-{3,}", s)
                    or re.match(r"^(\s*)([-*]|\d+\.)\s+", lines[i])):
                break
            buf.append(s)
            i += 1
        if buf:
            flows += [Paragraph(inline(" ".join(buf)), body_style), Spacer(1, 5)]

    return flows


def bind_headings(flows):
    """Keep each heading with its rule and first following block, so no heading is
    stranded at the foot of a page and short trailing lists don't split off alone."""
    out = []
    i = 0
    while i < len(flows):
        f = flows[i]
        style = getattr(f, "style", None)
        if style is not None and getattr(style, "name", "") in ("h2", "h3", "h4"):
            group = [f]
            i += 1
            while i < len(flows) and isinstance(flows[i], (Rule, Spacer)):
                group.append(flows[i])
                i += 1
            if i < len(flows):
                nxt = flows[i]
                # Don't drag a tall block onto a fresh page just to follow its heading.
                if isinstance(nxt, (Paragraph, ListFlowable)):
                    group.append(nxt)
                    i += 1
            out.append(KeepTogether(group))
            continue
        out.append(f)
        i += 1
    return out


# ----------------------------------------------------------------------- styles
def build_styles():
    ss = getSampleStyleSheet()
    s = {}
    s["h1"] = ParagraphStyle("h1", parent=ss["Title"], fontName="Helvetica-Bold",
                             fontSize=25, leading=29, textColor=PURPLE,
                             alignment=TA_LEFT, spaceBefore=0, spaceAfter=4)
    s["h2"] = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=16.5, leading=20,
                             textColor=PURPLE, spaceBefore=10, spaceAfter=2)
    s["h3"] = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=12.5, leading=16,
                             textColor=colors.HexColor("#33285C"), spaceBefore=9,
                             spaceAfter=3)
    s["h4"] = ParagraphStyle("h4", fontName="Helvetica-BoldOblique", fontSize=11,
                             leading=14, textColor=INK, spaceBefore=7, spaceAfter=2)
    s["body"] = ParagraphStyle("body", fontName="Helvetica", fontSize=9.8, leading=14,
                               textColor=INK, spaceAfter=0)
    s["body_sm"] = ParagraphStyle("body_sm", parent=s["body"], fontSize=9.2, leading=13)
    s["code"] = ParagraphStyle("code", fontName=MONO, fontSize=7.9, leading=10.6,
                               textColor=CODE_FG)
    s["th"] = ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=8.8, leading=11.5,
                             textColor=colors.white)
    s["td"] = ParagraphStyle("td", fontName="Helvetica", fontSize=8.8, leading=11.5,
                             textColor=INK)
    s["admon_title"] = ParagraphStyle("admon_title", fontName="Helvetica-Bold",
                                      fontSize=9.6, leading=12.5, textColor=INK,
                                      spaceAfter=4)
    s["meta"] = ParagraphStyle("meta", fontName="Helvetica-Oblique", fontSize=9,
                               leading=12.5, textColor=MUTED, spaceAfter=2)
    return s


def decorate(canv, doc):
    canv.saveState()
    canv.setFont("Helvetica", 7.6)
    canv.setFillColor(MUTED)
    canv.drawString(MARGIN, 0.5 * inch, "Claude Code Tutorial — Reusable Agents")
    canv.drawRightString(LETTER[0] - MARGIN, 0.5 * inch, "Page %d" % canv.getPageNumber())
    canv.setStrokeColor(RULE)
    canv.setLineWidth(0.5)
    canv.line(MARGIN, 0.62 * inch, LETTER[0] - MARGIN, 0.62 * inch)
    canv.restoreState()


def main(src, dest):
    with open(src) as fh:
        text = fh.read()
    lines = text.split("\n")

    styles = build_styles()
    story = []

    # Cover header, then drop the source's own H1/subtitle lines.
    story.append(Paragraph("Reusable Agents in Claude Code", styles["h1"]))
    story.append(Paragraph("Build one once, invoke it forever, share it via GitHub",
                           ParagraphStyle("sub", fontName="Helvetica", fontSize=12.5,
                                          leading=16, textColor=PURPLE_LT,
                                          spaceAfter=6)))
    story.append(Rule(thickness=1.2, color=PURPLE, pad=4))
    story.append(Paragraph(
        "From the Claude Code Comprehensive Tutorial &nbsp;·&nbsp; "
        '<link href="https://github.com/hoqugr-beep/claude-code-tutorial" color="#%s">'
        "github.com/hoqugr-beep/claude-code-tutorial</link>" % PURPLE.hexval()[2:],
        styles["meta"]))
    story.append(Spacer(1, 12))

    # Skip the leading H1 + subtitle + first rule from the Markdown source.
    start = 0
    for idx, l in enumerate(lines[:12]):
        if l.strip() == "---":
            start = idx + 1
            break
    story += bind_headings(render_blocks(lines[start:], styles))

    doc = BaseDocTemplate(dest, pagesize=LETTER,
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=0.75 * inch, bottomMargin=0.8 * inch,
                          title="Reusable Agents in Claude Code",
                          author="Claude Code Tutorial",
                          subject="Creating, invoking, and sharing custom subagents")
    frame = Frame(MARGIN, 0.8 * inch, LETTER[0] - 2 * MARGIN,
                  LETTER[1] - 1.55 * inch, id="body")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=decorate)])
    doc.build(story)
    print("wrote %s" % dest)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
