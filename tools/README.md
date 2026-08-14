# tools

## build-docx.js

Renders `docs/index.md` into a styled Word document — cover page, an
auto-updating table of contents, real Word tables, and shaded code blocks.

```bash
npm install docx
node tools/build-docx.js docs/index.md "Claude Code Tutorial.docx"
```

Re-run it whenever the tutorial changes; the output is fully regenerated, so
there is nothing to keep in sync by hand.

### Notes

- The table of contents is a Word field. Word populates it on open (the
  document sets `updateFields`), so it looks empty until then in some
  third-party viewers.
- Code blocks carry a left accent rule only. `w:pBdr` children are
  order-enforced by the OOXML schema (`top, left, bottom, right`) but docx-js
  serialises them `top, bottom, left`, so any combination including a bottom
  border produces a document strict readers reject.
- Validate changes with the OOXML schema before shipping a build.
