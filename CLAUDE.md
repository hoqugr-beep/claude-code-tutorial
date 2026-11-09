# claude-code-tutorial

A beginner-to-advanced Claude Code tutorial, published as a MkDocs Material
site (GitHub Pages URL in `mkdocs.yml` → `site_url`).

## Layout

- `docs/index.md`: the whole tutorial, one page with 22 numbered sections and a
  table of contents. `nav` in `mkdocs.yml` lists only this page, so a new page
  needs a `nav` entry.
- `mkdocs.yml`: theme, Markdown extensions, nav.
- `.claude/skills/task-observer/`: vendored third-party skill (CC BY 4.0).
  `dist/` and `scripts/` package and install it. See `dist/README.md`.
- `site/`: build output. Git-ignored. Never commit it.

## Build and check

```sh
pip install mkdocs-material   # no requirements file; this pulls in mkdocs and pymdown-extensions
mkdocs serve                  # live preview at http://127.0.0.1:8000
mkdocs build --strict         # run before every commit that touches docs/ or mkdocs.yml
```

`--strict` fails on warnings only. Broken in-page anchors are reported at INFO
level and still pass, so read the build output for `no such anchor` lines.
Heading slugs come from the `toc` extension. Derive TOC links from the built
page's heading ids, not by hand.

## Writing tutorial content

The tutorial documents a product that changes often. Accuracy comes before
coverage:

- Check every command, flag, slash command, settings key, keybinding, hook
  event, and model ID against the current official Claude Code docs before you
  add or change it. If you can't verify something, leave it out or mark it as
  unverified. Never invent it.
- Don't present version-specific behaviour as permanent. When a section's facts
  change, update the `Last Updated` line at the top of `docs/index.md`.
- Example output and config snippets must be things the tool could really
  produce. Label illustrative examples as illustrative.
- Use the existing style: numbered `##` sections, `###` subsections, tables for
  reference material, fenced code blocks with a language tag.

## task-observer skill (activation)

At the start of any task-oriented session (one where you will use tools and
produce deliverables), invoke the task-observer skill before beginning work, so
skill-improvement opportunities are captured for the whole session.

When you load any skill, check the observation log for OPEN observations tagged
to that skill and apply them now, even if the skill file hasn't been updated
yet.

Load the skill's `references/` files on demand, not up front. Invoke it
directly. Never chain its activation through another skill, because a broken
chain silences all observation activity.

`scripts/install-task-observer.sh` writes a copy of this activation block to
`~/.claude/CLAUDE.md`. Keep the two in sync when you edit either one.
