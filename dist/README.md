# dist/

Packaged artifacts. Not part of the MkDocs site build.

## task-observer.zip

The `task-observer` skill (`.claude/skills/task-observer/`) packaged for
upload to Claude apps that take skills as a zip — the desktop app, web, mobile,
and Cowork.

**Install:** Claude → Settings → Capabilities → Skills → upload this zip. The
skill then applies to all chats and Cowork tasks, independent of this repo's
project-level copy (which is what Claude Code uses).

**Rebuild after editing the skill:**

```sh
STAGE=$(mktemp -d) && mkdir -p "$STAGE/task-observer"
cp -r .claude/skills/task-observer/. "$STAGE/task-observer/"
(cd "$STAGE" && zip -rq - task-observer) > dist/task-observer.zip
rm -rf "$STAGE"
```

The zip must contain a single top-level `task-observer/` folder holding
`SKILL.md` and the `references/` subfolder — the references are loaded on
demand, and the skill runs degraded without them.

Skill by Eoghan Henn / rebelytics.com, CC BY 4.0 — see
`LICENSE.txt` inside the bundle and
<https://github.com/rebelytics/one-skill-to-rule-them-all>.
