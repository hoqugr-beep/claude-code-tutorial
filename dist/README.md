# dist/

Packaged artifacts. Not part of the MkDocs site build.

## task-observer

The [task-observer](https://github.com/rebelytics/one-skill-to-rule-them-all)
skill has to be installed twice, because Claude's surfaces read skills from two
different places:

| Surface | Reads skills from | How it gets installed |
| --- | --- | --- |
| Desktop chat, web, mobile, **Cowork** | your Claude **account** | upload `dist/task-observer.zip` (manual, UI only) |
| Claude **Code** — this repo | `.claude/skills/` in the repo | already committed |
| Claude **Code** — every project | `~/.claude/skills/` on your machine | `./scripts/install-task-observer.sh` |

### 1. Desktop chat and Cowork

Claude → Settings → Capabilities → Skills → upload `task-observer.zip`. One
upload covers desktop chat, web, mobile, and Cowork, since all four read the
same account-level skill set. This step cannot be scripted — the account skill
API is not exposed to Claude Code.

### 2. Claude Code

```sh
./scripts/install-task-observer.sh              # install / update
./scripts/install-task-observer.sh --check      # show what's installed
./scripts/install-task-observer.sh --no-memory  # skip the CLAUDE.md edit
```

Two things happen, because availability and activation are separate problems:

1. The skill is copied to `~/.claude/skills/task-observer/`, making it
   available in every project.
2. The activation block is appended to `~/.claude/CLAUDE.md`, so every project
   invokes it — without a config-level instruction the skill falls back to
   description matching, which upstream calls unenforceable. The edit is
   idempotent (guarded by an HTML-comment marker) and backs up any existing
   file first.

Run it on the machine where you use Claude Code — a remote/web session installs
into a throwaway container, not your laptop. The script falls back to cloning
upstream if run outside this repo.

This repo's own copy at `.claude/skills/task-observer/` and its `CLAUDE.md`
block are committed already; the personal install covers everywhere else.

### Rebuilding the zip after editing the skill

```sh
STAGE=$(mktemp -d) && mkdir -p "$STAGE/task-observer"
cp -r .claude/skills/task-observer/. "$STAGE/task-observer/"
(cd "$STAGE" && zip -rq - task-observer) > dist/task-observer.zip
rm -rf "$STAGE"
```

The zip must contain a single top-level `task-observer/` folder holding
`SKILL.md` and the `references/` subfolder — the references are loaded on
demand, and the skill runs degraded without them. Re-upload it afterwards; the
account copy does not track this repo.

Skill by Eoghan Henn / rebelytics.com, CC BY 4.0 — see `LICENSE.txt` inside the
bundle and <https://github.com/rebelytics/one-skill-to-rule-them-all>.
