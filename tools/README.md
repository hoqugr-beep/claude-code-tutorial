# tools/

## `md2pdf.py`

Renders a tutorial page from `docs/` into a styled, printable PDF. Written for the subset of
MkDocs-Material Markdown this site actually uses: headings, tables, fenced code, `!!!`
admonitions, lists, rules, and inline bold/italic/code/links.

```bash
pip install reportlab
python3 tools/md2pdf.py docs/reusable-agents.md docs/reusable-agents.pdf
```

Regenerate the PDF whenever you edit the corresponding Markdown page, then commit both.

Notes:

- Everything above the page's first `---` is treated as web-only front matter (the title block
  and the "Download as PDF" button) and replaced with the PDF's own cover header.
- Code blocks use DejaVu Sans Mono when present at
  `/usr/share/fonts/truetype/dejavu/`, so box-drawing characters in directory trees render
  properly. It falls back to Courier, which lacks those glyphs.
- Links to anchors inside the site are rewritten to the published GitHub Pages URL; same-page
  anchors degrade to styled text, since a PDF can't resolve them.
