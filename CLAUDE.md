# claude-code-tutorial

An interactive Claude Code tutorial published as a MkDocs Material site.
Content lives in `docs/`, configuration in `mkdocs.yml`. The site is built to
`site/`, which is git-ignored — never commit build output.

## Skills

### task-observer (activation)

At the start of any task-oriented session — any interaction where you will
use tools and produce deliverables — invoke the task-observer skill before
beginning work. This ensures skill improvement opportunities are captured
throughout the session.

When loading any skill, check the observation log for OPEN observations
tagged to that skill. Apply their insights to the current work, even if
the skill file hasn't been updated yet. This enables immediate application
of observations before they're permanently integrated during the weekly
review.

The skill is installed at `.claude/skills/task-observer/`. Load its
`references/` files on demand rather than up front. Do not chain its
activation through another skill — a broken chain silences all observation
activity.
