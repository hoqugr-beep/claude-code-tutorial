# claude-code-tutorial

Interactive Claude Code tutorial, published as a MkDocs Material site.
Never commit build output: `site/` is generated and git-ignored.

## task-observer activation

- At the start of any task-oriented session (one where you will use tools and
  produce deliverables), invoke the task-observer skill before beginning work.
- When loading any skill, check the observation log for OPEN observations
  tagged to that skill and apply them now, even before the skill file is
  updated.
- Invoke task-observer directly, never via another skill: a broken chain
  silences all observation activity.
