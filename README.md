# Claude Code Tutorial

A beginner-to-advanced Claude Code tutorial, built with MkDocs Material and
published at <https://hoqugr-beep.github.io/claude-code-tutorial/>.

The content is in [`docs/index.md`](docs/index.md). It's checked against the
[official Claude Code docs](https://code.claude.com/docs/en/overview), which
win whenever the two disagree.

## Preview locally

```sh
pip install mkdocs-material
mkdocs serve            # http://127.0.0.1:8000
mkdocs build --strict   # fails on warnings, including broken in-page links
```
