# Claude Code: Comprehensive Interactive Tutorial
### From Beginner to Advanced

> **Last Updated:** November 2026 | Checked against the [official Claude Code docs](https://code.claude.com/docs/en/overview). Covers the CLI, Desktop app, IDE extensions, MCP, GitHub, and more.

!!! note "Claude Code changes quickly"
    Commands, settings, and model names change between releases. When something here doesn't match what you see, trust the [official documentation](https://code.claude.com/docs/en/overview) and your own `claude --help`, `/help`, and `/model` output.

---

## Table of Contents

1. [What is Claude Code?](#1-what-is-claude-code)
2. [Installation & Initial Setup](#2-installation-initial-setup)
3. [First Run & Basic Navigation](#3-first-run-basic-navigation)
4. [Settings & Configuration](#4-settings-configuration)
5. [CLAUDE.md — Your Project Brain](#5-claudemd-your-project-brain)
6. [Built-in Tools Reference](#6-built-in-tools-reference)
7. [Slash Commands & Skills](#7-slash-commands-skills)
8. [Keybindings Customization](#8-keybindings-customization)
9. [Hooks System](#9-hooks-system)
10. [Memory System](#10-memory-system)
11. [Plan Mode](#11-plan-mode)
12. [Worktrees (Isolated Git Workspaces)](#12-worktrees-isolated-git-workspaces)
13. [GitHub Integration](#13-github-integration)
14. [MCP — Model Context Protocol](#14-mcp-model-context-protocol)
15. [Connectors & External Tools](#15-connectors-external-tools)
16. [Multi-Agent & Parallel Tasks](#16-multi-agent-parallel-tasks)
17. [Claude API & Model Selection](#17-claude-api-model-selection)
18. [Permission Modes & Security](#18-permission-modes-security)
19. [IDE Integrations (VS Code & JetBrains)](#19-ide-integrations-vs-code-jetbrains)
20. [Advanced Patterns & Workflows](#20-advanced-patterns-workflows)
21. [Troubleshooting & FAQ](#21-troubleshooting-faq)
22. [Quick Reference Cheat Sheet](#22-quick-reference-cheat-sheet)

---

## 1. What is Claude Code?

Claude Code is Anthropic's agentic coding tool. It reads your code, runs commands, and makes changes for you. You can use it from:

| Interface | Best For |
|---|---|
| **CLI** (`claude`) | Terminal-native workflows, scripts, CI/CD |
| **Desktop app** | The **Code** tab in Claude Desktop (macOS, Windows, Linux) |
| **Web** | `claude.ai/code`: cloud sessions in your browser |
| **VS Code extension** | A Claude panel inside VS Code, with inline diffs |
| **JetBrains plugin** | IntelliJ IDEA, PyCharm, WebStorm, and other JetBrains IDEs |

### Key Capabilities

- Read, write, and edit files across your project
- Run shell commands, tests, and builds
- Search the web and fetch documentation pages
- Work with GitHub (PRs, issues, commits) through `gh` or MCP
- Connect to external services through MCP servers
- Delegate work to subagents that run with their own context
- Remember project instructions (`CLAUDE.md`) and learnings (auto memory) across sessions

---

## 2. Installation & Initial Setup

### 2.1 CLI Installation

The native installer is the recommended route, and it updates itself in the background:

```bash
# macOS, Linux, WSL
curl -fsSL https://claude.ai/install.sh | bash
```

```bash
# Windows (CMD)
curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
```

Package managers also work, but they don't auto-update by default:

```bash
brew install --cask claude-code        # Homebrew; upgrade with: brew upgrade claude-code
winget install Anthropic.ClaudeCode    # WinGet;  upgrade with: winget upgrade Anthropic.ClaudeCode
npm install -g @anthropic-ai/claude-code   # npm; needs Node.js 22+. Never use sudo
```

Check the install:

```bash
claude --version
```

### 2.2 Authentication

```bash
# Option A: sign in with your Claude account (opens a browser on first run)
claude
# or explicitly:
claude auth login
claude auth status      # check who you're signed in as

# Option B: use an API key from the Claude Console
export ANTHROPIC_API_KEY="sk-ant-..."
```

To keep the key across shells, add the `export` line to your shell profile (`~/.bashrc`, `~/.zshrc`). Never commit it.

### 2.3 Desktop App

1. Download Claude Desktop from [claude.com/download](https://claude.com/download) (macOS, Windows; Linux installs through apt)
2. Sign in with your Claude account
3. Open the **Code** tab. That's Claude Code. The app's other tabs are chat and Cowork.

### 2.4 VS Code Extension

1. Open VS Code → Extensions (`Ctrl+Shift+X` / `Cmd+Shift+X`)
2. Search for **Claude Code** and install the extension published by Anthropic
3. Open the Claude panel and sign in when prompted

### 2.5 JetBrains Plugin

1. Install the CLI first (section 2.1). The plugin runs `claude` in the IDE's terminal and doesn't bundle its own copy.
2. In your IDE: Settings → Plugins → search **Claude Code** → install, then restart the IDE

### 2.6 Where Claude Code Keeps Its Files

Some of the files under `~/.claude/` (Windows: `%USERPROFILE%\.claude\`):

```
~/.claude/
├── settings.json          # Your user settings (all projects)
├── keybindings.json       # Custom keyboard shortcuts (open with /keybindings)
├── CLAUDE.md              # Your personal instructions for every project
├── skills/<name>/SKILL.md # Your personal skills
├── agents/                # Your personal subagent definitions
├── plans/                 # Plan files written in plan mode (default location)
└── projects/<project>/
    └── memory/            # Auto memory for that project
        └── MEMORY.md      # Memory index, loaded at session start
~/.claude.json             # App state, including MCP servers you added at local or user scope
```

In a project, the same ideas live under `.claude/`: `settings.json`, `settings.local.json`, `skills/`, `agents/`, plus `CLAUDE.md` at the repo root and `.mcp.json` for shared MCP servers.

---

## 3. First Run & Basic Navigation

### 3.1 Starting Claude Code

```bash
# Start in your project directory, so Claude sees the right files
cd /path/to/your/project
claude

# Start with an initial prompt
claude "explain what this project does"

# Non-interactive: print one answer and exit (good for scripts)
claude -p "what files are in this directory?"

# Pick up where you left off
claude -c                 # continue the most recent conversation here
claude -r                 # choose a past session to resume
```

### 3.2 The Interactive Interface

You type requests in plain language at the prompt. Claude explains what it's going to do, asks permission for actions that need it, and shows diffs for file changes.

### 3.3 Basic Commands to Know First

| What to type | What happens |
|---|---|
| `/help` | Show available commands |
| `/clear` | Start a fresh conversation |
| `/exit`, or `Ctrl+D` twice | Exit Claude Code |
| `Esc` | Stop Claude mid-response so you can redirect it |
| `Ctrl+C` | Interrupt a running operation; when idle, press twice to exit |
| `Shift+Tab` | Cycle permission modes (for example, into plan mode) |
| `!ls -la` | Run a shell command directly |
| `Ctrl+R` | Search your prompt history |

### 3.4 Your First Interactions

**Try these beginner prompts:**

```
> what does this project do?
> list all the TypeScript files in src/
> find where the authentication logic lives
> read the README and summarize it
> what tests exist and how do I run them?
```

---

## 4. Settings & Configuration

Settings are JSON files at several levels. The `/config` command opens a settings UI, and `/permissions` manages permission rules interactively.

### 4.1 Settings File Locations

| File | Scope | Shared? |
|---|---|---|
| `~/.claude/settings.json` | User: all your projects | Only you |
| `.claude/settings.json` | Project | Commit it to share with your team |
| `.claude/settings.local.json` | Project, just for you | Keep it out of git |
| `managed-settings.json` (and other managed sources) | Set by your organization | Everyone it's deployed to |

When the same key is set in more than one place, the highest level wins: **managed > command line (`--settings`) > project local > shared project > user**. Permission rules work differently: a `deny` rule from any level beats an `allow` rule from any level (see 4.4).

### 4.2 A Typical settings.json

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "model": "sonnet",
  "permissions": {
    "allow": [
      "Bash(npm run *)",
      "Bash(git status)",
      "Bash(git diff *)"
    ],
    "deny": [
      "Read(./.env)",
      "Bash(git push --force *)"
    ]
  },
  "env": {
    "NODE_ENV": "development"
  },
  "cleanupPeriodDays": 30
}
```

- `$schema` gives you autocomplete and validation in editors like VS Code.
- `cleanupPeriodDays` controls how long session transcripts are kept (default 30).
- Commit and PR attribution is set with `attribution`. The older `includeCoAuthoredBy` key is deprecated.
- The full key list is in the [settings reference](https://code.claude.com/docs/en/settings-reference).

### 4.3 Model Selection

Use a **model alias** rather than a full model ID, so you get the recommended version automatically:

| Alias | What it selects (Anthropic API, November 2026) |
|---|---|
| `opus` | Claude Opus 5.5: strongest Opus, for complex reasoning |
| `sonnet` | Claude Sonnet 5.5: balanced speed and quality |
| `haiku` | Claude Haiku 5.5: fastest and cheapest |
| `fable` | Claude Fable 5.1: for the hardest, longest-running tasks |
| `best` | Fable where it's available to you, otherwise Opus |
| `opusplan` | Opus while planning, Sonnet while executing |

```bash
/model sonnet              # switch in a session (also saved as your default)
claude --model opus        # choose for one session
```

To pin an exact version, use the full ID, for example `"model": "claude-opus-5-5"`. On Amazon Bedrock, Google Cloud, or Microsoft Foundry, the aliases can resolve to older models. See [model configuration](https://code.claude.com/docs/en/model-config).

### 4.4 Permission Rules Deep Dive

Rules have the form `Tool` or `Tool(specifier)`:

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run *)",
      "Bash(git log *)",
      "Bash(git status)",
      "Edit(src/**)",
      "WebFetch(domain:docs.python.org)",
      "WebSearch"
    ],
    "ask": [
      "Bash(git push *)"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./secrets/**)",
      "Bash(git push --force *)"
    ]
  }
}
```

**How rules are evaluated:** deny first, then ask, then allow. The first match decides. An allow rule can't make an exception to a deny rule.

**Pattern syntax:**

- `Bash(npm run build)` matches only that exact command.
- `Bash(npm run *)` matches `npm run`, `npm run test`, and so on. The space before `*` matters: `Bash(ls *)` doesn't match `lsof`, but `Bash(ls*)` does.
- Claude Code understands shell operators, so `Bash(safe-cmd *)` doesn't allow `safe-cmd && other-cmd`.
- `Read(...)` and `Edit(...)` take gitignore-style paths: `src/**`, `./.env`.
- `WebFetch(domain:example.com)` matches fetches to one domain. `WebSearch` takes no specifier.
- `Bash` on its own (or `Bash(*)`) matches every command. As a deny rule, it removes the tool entirely.

JSON doesn't allow comments, so don't add `//` notes inside a settings file.

### 4.5 A Starter Configuration for a Developer

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "model": "sonnet",
  "permissions": {
    "allow": [
      "Bash(npm run *)",
      "Bash(npm test)",
      "Bash(pytest *)",
      "Bash(git status)",
      "Bash(git diff *)",
      "Bash(git log *)",
      "WebSearch"
    ],
    "deny": [
      "Read(./.env)",
      "Bash(git push --force *)"
    ]
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | xargs npx prettier --write 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

The hook formats every file Claude edits. Hooks are explained in section 9.

---

## 5. CLAUDE.md — Your Project Brain

`CLAUDE.md` is a Markdown file of instructions that Claude Code loads into every session. It's how you give Claude persistent, project-specific guidance. Run `/init` to generate a first version from your codebase.

### 5.1 Where to Place CLAUDE.md Files

| Location | Scope | Shared with |
|---|---|---|
| `~/.claude/CLAUDE.md` | Your personal preferences for all projects | Only you |
| `./CLAUDE.md` or `./.claude/CLAUDE.md` | The project | Your team, via git |
| `./CLAUDE.local.md` | Your private notes for this project | Only you (add it to `.gitignore`) |
| `<subdir>/CLAUDE.md` | One part of the codebase | Your team |

`CLAUDE.md` files in the directory you start in and its parent directories load at launch. Files in **subdirectories** load on demand, when Claude works with files there. Organizations can also deploy a managed `CLAUDE.md`.

A `CLAUDE.md` can pull in other files with `@path/to/file` (for example `@docs/architecture.md`). Use `/memory` to open and edit the loaded files.

### 5.2 What to Put in CLAUDE.md

```markdown
# Project: MyApp

## Overview
React + FastAPI app for managing inventory. Backend uses PostgreSQL with SQLAlchemy.

## Development Commands
- Start backend: `cd backend && uvicorn main:app --reload`
- Start frontend: `cd frontend && npm run dev`
- Run all tests: `npm test && pytest`
- Lint: `npm run lint && ruff check .`

## Architecture Notes
- API routes live in `backend/api/` and use dependency injection
- Database models are in `backend/models/`; always use Alembic for migrations
- Frontend state uses Zustand, not Redux

## Conventions
- Python: Black, type hints required
- TypeScript: strict mode, no `any`
- Commits: conventional commits (feat:, fix:, chore:)

## Things to Avoid
- Never edit `backend/config.py` directly; use environment variables
- Don't silence TypeScript errors with `@ts-ignore`
```

### 5.3 CLAUDE.md Best Practices

- **Keep it short.** Aim for under 200 lines per file. Long files use more context and are followed less reliably.
- **Be specific.** "Use Zustand" beats "use modern state management".
- **Include run commands.** Claude needs to know how to build and test.
- **Document gotchas.** Write down what isn't obvious from the code.
- **Remove contradictions.** If two instructions conflict, Claude may follow either one.
- **Commit it.** That shares your conventions with the team.

---

## 6. Built-in Tools Reference

Claude chooses tools on its own, but knowing them helps you write better prompts. These are the common ones. The [tools reference](https://code.claude.com/docs/en/tools-reference) has the full list.

### 6.1 File System Tools

| Tool | What it does | Example prompt |
|---|---|---|
| **Read** | Read a file | "read the config file" |
| **Write** | Create or overwrite a file | "create a new component file" |
| **Edit** | Make targeted edits to a file | "fix the bug in the login handler" |
| **Glob** / **Grep** | Find files by name pattern / search file contents | "find all TODO comments" |
| **NotebookEdit** | Edit Jupyter notebook cells | "add a cell to the notebook" |

Note: according to the tools reference, Glob and Grep are absent by default on macOS, Linux, and WSL. Claude searches through shell commands there instead.

### 6.2 Execution Tools

| Tool | What it does | Example prompt |
|---|---|---|
| **Bash** | Run shell commands | "run the tests" |
| **PowerShell** | Run PowerShell commands (Windows) | "list running services" |
| **Monitor** | Watch a background command's output and react to it | "tail the dev server log and tell me about errors" |

### 6.3 Research Tools

| Tool | What it does | Example prompt |
|---|---|---|
| **WebSearch** | Search the web | "look up the React 19 release notes" |
| **WebFetch** | Fetch a specific URL | "read the content at this URL" |

### 6.4 Orchestration Tools

| Tool | What it does |
|---|---|
| **Agent** | Starts a subagent with its own context window |
| **TaskCreate / TaskUpdate / TaskList** | Keep a task checklist for multi-step work (`Ctrl+T` shows it) |
| **AskUserQuestion** | Asks you multiple-choice questions to clarify a request |
| **EnterPlanMode / ExitPlanMode** | Switch into plan mode, and present a plan for approval |
| **EnterWorktree / ExitWorktree** | Create, or leave, an isolated git worktree |
| **Skill** | Runs a skill |

### 6.5 Tool Usage Tips

**Be specific to get the right tool:**
```
# Vague (Claude must guess)
> look at the auth stuff

# Better
> find where JWT tokens are generated and read that file

# Best (Claude can go straight to work)
> search backend/ for "jwt.sign", then read the file that contains it
```

---

## 7. Slash Commands & Skills

Type `/` to see every command and skill available in your session.

### 7.1 Built-in Slash Commands

| Command | Description |
|---|---|
| `/help` | Show help and available commands |
| `/clear` | Start a fresh conversation |
| `/compact [focus]` | Summarize the conversation to free up context |
| `/context` | Show what's using your context window |
| `/model [model]` | Switch models |
| `/fast [on\|off]` | Toggle fast mode (Opus at higher speed and higher cost) |
| `/plan [task]` | Enter plan mode |
| `/init` | Generate a `CLAUDE.md` for the project |
| `/memory` | Edit `CLAUDE.md` files and manage auto memory |
| `/permissions` | Manage allow, ask, and deny rules |
| `/hooks` | View hook configuration |
| `/mcp` | Manage MCP servers and their sign-in |
| `/review [pr#\|branch\|path]` | Review your current diff or a PR (alias of `/code-review`) |
| `/resume`, `/rewind` | Resume a past session / roll back to an earlier point |
| `/tasks` | View background work, including subagents |
| `/config` | Open the settings UI |
| `/keybindings` | Open your keybindings file |
| `/doctor` | Check your installation and configuration |
| `/exit` | Exit Claude Code |

### 7.2 Bundled Skills

Some `/` entries are **skills**: packaged instructions Claude Code ships with. Examples:

| Skill | What it does |
|---|---|
| `/simplify [target]` | Review changed code for cleanup opportunities and apply fixes |
| `/loop [interval] [prompt]` | Re-run a prompt on an interval while the session stays open |
| `/update-config [request]` | Describe a settings change in plain words and let Claude make it |
| `/claude-api` | Reference for building with the Claude API and SDKs |

There's no built-in `/commit` command. Just ask, for example "commit these changes with a good message".

### 7.3 Running Shell Commands Inline

Prefix a command with `!` to run it directly, without Claude interpreting it:

```
> !git status
> !npm test
```

### 7.4 Creating Custom Skills

Create `.claude/skills/deploy/SKILL.md` in your project, or `~/.claude/skills/deploy/SKILL.md` for all your projects:

```markdown
---
description: Run the deployment pipeline to staging. Use when the user asks to deploy or ship to staging.
disable-model-invocation: true
---

Run the full deployment pipeline:

1. Run tests: `npm test`
2. Build: `npm run build`
3. Deploy to staging: `./deploy.sh staging`
4. Verify: `curl https://staging.myapp.com/health`

Report results and any failures.
```

Invoke it with `/deploy`. The `description` tells Claude when the skill applies. `disable-model-invocation: true` means only you can trigger it, which suits actions with side effects like deployment.

Older `.claude/commands/<name>.md` files still work. Custom commands have been merged into skills.

---

## 8. Keybindings Customization

### 8.1 Default Keybindings

| Key | Action |
|---|---|
| `Enter` | Submit message |
| `Esc` | Interrupt Claude, or close a dialog |
| `Esc` `Esc` | Clear the input, or rewind when the input is empty |
| `Ctrl+C` | Interrupt; when idle, clears input, and a second press exits |
| `Ctrl+R` | Reverse-search prompt history |
| `Up` / `Down` | Move through history |
| `Shift+Tab` | Cycle permission modes |
| `Ctrl+G` | Edit your prompt in your text editor |
| `Ctrl+O` | Toggle the transcript viewer |
| `Ctrl+B` | Send running commands and agents to the background |
| `Ctrl+T` | Show or hide Claude's task checklist |
| `Ctrl+L` | Redraw the screen (doesn't clear the conversation; use `/clear` for that) |
| `Option+P` / `Alt+P` | Switch model |

For a newline in your prompt, `Shift+Enter` works in many terminals. Run `/terminal-setup` if it doesn't. The full list is in [interactive mode](https://code.claude.com/docs/en/interactive-mode).

### 8.2 Customizing Keybindings

Run `/keybindings` to open `~/.claude/keybindings.json`. Bindings are grouped by **context**, such as `Global`, `Chat`, or `Confirmation`, and map a key to an **action**:

```json
{
  "$schema": "https://www.schemastore.org/claude-code-keybindings.json",
  "bindings": [
    {
      "context": "Chat",
      "bindings": {
        "ctrl+e": "chat:externalEditor",
        "ctrl+s": null
      }
    }
  ]
}
```

Setting a key to `null` removes its default binding. The schema gives you autocomplete for context and action names in editors that support it.

### 8.3 Chord Bindings

A chord is a sequence of keystrokes separated by spaces, for example `"ctrl+x ctrl+e": "chat:externalEditor"`. Press each keystroke within 3 seconds of the previous one.

---

## 9. Hooks System

Hooks run your own commands automatically at specific points in a session. Use them to enforce rules that must always happen, like formatting, blocking, or logging, rather than relying on Claude to remember.

### 9.1 Common Hook Events

| Event | When it fires |
|---|---|
| `SessionStart` / `SessionEnd` | A session begins / ends |
| `UserPromptSubmit` | You submit a prompt, before Claude sees it |
| `PreToolUse` | Before a tool runs (can block it) |
| `PostToolUse` | After a tool succeeds |
| `Notification` | Claude Code sends a notification |
| `Stop` | Claude finishes responding |
| `PreCompact` | Before the context is compacted |

There are many more events, including `SubagentStop`, `PermissionRequest`, and `FileChanged`. See the [hooks reference](https://code.claude.com/docs/en/hooks).

### 9.2 How a Hook Receives Data and Responds

- **Input:** a command hook gets a JSON description of the event on **stdin**. For tool events this includes `tool_name` and `tool_input`, for example `{"tool_name": "Bash", "tool_input": {"command": "npm test"}, ...}`. Parse it with `jq`.
- **Exit code 0:** carry on normally.
- **Exit code 2:** block the action. Your stderr is shown to Claude as the reason. On `PreToolUse` this stops the tool call.
- **`CLAUDE_PROJECT_DIR`** holds the project root, which is handy for pointing at scripts in `.claude/hooks/`.

Hooks are configured in any settings file. `/hooks` shows what's active.

### 9.3 Hook Configuration Example

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-bash.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | xargs npx prettier --write 2>/dev/null || true"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "notify-send 'Claude Code' 'Task completed' 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

`matcher` is matched against the tool name, and `Edit|Write` matches either tool.

### 9.4 Example: Block Dangerous Commands

`.claude/hooks/check-bash.sh` (make it executable with `chmod +x`):

```bash
#!/usr/bin/env bash
cmd=$(jq -r '.tool_input.command')
if echo "$cmd" | grep -qiE 'drop table|rm -rf /'; then
  echo "Blocked by project policy: $cmd" >&2
  exit 2
fi
exit 0
```

### 9.5 Example: Log Every Command

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '\"\\(now | todate) \\(.tool_input.command)\"' >> ~/.claude/bash-audit.log"
          }
        ]
      }
    ]
  }
}
```

You can also ask `/update-config` to write hooks for you, for example: "/update-config run the linter after every edit".

---

## 10. Memory System

Claude Code carries knowledge across sessions in two ways:

| | `CLAUDE.md` files | Auto memory |
|---|---|---|
| **Who writes it** | You (or Claude, at your request) | Claude, as it learns about your project |
| **What goes in** | Instructions and rules | Learnings: build quirks, preferences, decisions |
| **Loaded** | Every session, in full | Every session: the first 200 lines or 25KB of `MEMORY.md` |

### 10.1 Auto Memory Location

```
~/.claude/projects/<project>/memory/
├── MEMORY.md          # Index, one line per memory, loaded at session start
└── *.md               # Topic files Claude reads when relevant
```

`<project>` is derived from the git repository, so every worktree and subdirectory of one repo shares a memory directory. Use `/memory` to view entries or switch auto memory on and off.

### 10.2 Asking Claude to Remember Things

```
> remember that this project uses pnpm, not npm
> remember that the staging environment is at staging.internal.example.com
> forget what you saved about the old auth system — we've moved to OAuth
```

For a rule the whole team should follow, put it in `CLAUDE.md` instead, so it's in git and reviewed.

### 10.3 Memory Best Practices

- **Be specific.** Vague memories don't help.
- **Correct stale memories.** Tell Claude when things change.
- **Choose the right home.** Team rules go in `CLAUDE.md`, personal project notes in `CLAUDE.local.md`, and learned details in auto memory.
- **Don't store code or secrets** in memory.

---

## 11. Plan Mode

In plan mode Claude explores your codebase and proposes an approach, but doesn't edit files until you approve a plan. Use it for complex or risky changes.

### 11.1 Entering Plan Mode

- Press `Shift+Tab` to cycle permission modes until the status bar shows plan mode
- Type `/plan` or `/plan add OAuth2 to the API`
- Start a session in it: `claude --permission-mode plan`

Claude can also switch into plan mode itself when a task calls for it.

### 11.2 Working with Plan Mode

```
> /plan add OAuth2 authentication to the API
# Claude explores, then presents a plan:
# - which files change
# - the proposed approach (e.g. which OAuth library)
# - risks and open questions

# You can approve the plan, or keep refining it:
> use Passport.js instead, and only support Google as a provider
```

### 11.3 Plan Mode Tips

- **Push back before approving.** This is your chance to redirect.
- **Ask for alternatives**, for example "show me a simpler approach".
- **Plans are saved as files**, by default in `~/.claude/plans/`. The `plansDirectory` setting changes that.
- **The `opusplan` model alias** uses Opus while planning and Sonnet while executing.

---

## 12. Worktrees (Isolated Git Workspaces)

A git worktree is a separate checkout of your repository on its own branch. Claude can work in one without touching your main working copy, and you can run several sessions in parallel.

### 12.1 Starting in a Worktree

```bash
claude --worktree feature-auth     # or: claude -w feature-auth
```

This creates `.claude/worktrees/feature-auth/` on a new branch and starts Claude there. During a session you can also ask Claude to "work in a worktree", and it creates one.

Add `.claude/worktrees/` to your `.gitignore` so worktree contents don't show up as untracked files.

### 12.2 Working in a Worktree

A worktree is a fresh checkout, so install dependencies there before running anything. Changes stay on the worktree's branch until you merge them. When you're done, ask Claude to leave the worktree. You can keep the branch for later or remove it.

### 12.3 Worktree Use Cases

- **Risky refactors**: experiment without disturbing your main checkout
- **Parallel features**: one session per worktree
- **Reproducing bugs**: isolate the reproduction environment
- **Code review**: check out a PR branch without stashing your own work

---

## 13. GitHub Integration

Claude Code works with GitHub through the `gh` CLI, through a GitHub MCP server (section 14), and through GitHub Actions.

### 13.1 Prerequisites

```bash
# Install the GitHub CLI
brew install gh            # macOS
winget install GitHub.cli  # Windows
# Linux: see https://cli.github.com for your distribution's package

gh auth login
```

### 13.2 Common GitHub Workflows

**Create a PR:**
```
> create a pull request for these changes
# Claude checks the diff and commits, writes a title and description,
# pushes the branch, and opens the PR with gh pr create
```

**Review a PR:**
```
> /review 142
# or in plain words:
> review PR #142 and point out bugs and risky changes
```

**Commit with a good message:**
```
> commit these changes
# Claude reads git status and the diff, matches your repo's commit style,
# and creates the commit
```

**Work with issues:**
```
> list open issues labeled "bug"
> create an issue for the authentication timeout bug I just found
```

### 13.3 GitHub Actions Integration

Run `/install-github-app` to install the Claude GitHub App for a repository and, optionally, set up a GitHub Actions workflow. Then you can mention `@claude` in issues and PRs. See [GitHub Actions](https://code.claude.com/docs/en/github-actions).

In a normal session, Claude can also use `gh` to investigate CI:

```
> look at the failing CI run on this branch and tell me what's wrong
```

### 13.4 Useful gh Commands to Know

```bash
!gh pr list                    # List open PRs
!gh pr view 142                # View PR details
!gh pr checkout 142            # Check out a PR branch
!gh run list                   # List CI runs
!gh run view <run-id> --log    # View a CI run's logs
!gh issue list --label bug     # List bug issues
```

---

## 14. MCP — Model Context Protocol

MCP (Model Context Protocol) is an open standard for connecting Claude to external tools and data: issue trackers, databases, design tools, monitoring, and more. An MCP server exposes tools, and Claude calls them when they're relevant.

### 14.1 What MCP Servers Do

- **Services:** GitHub, Notion, Sentry, Linear, Slack, and others
- **Data:** databases and internal APIs
- **Custom tools:** anything your team builds

Browse reviewed servers in the [Anthropic Directory](https://claude.ai/directory).

### 14.2 Adding MCP Servers

Add servers with `claude mcp add`, not by editing `settings.json`:

```bash
# Remote (HTTP) server
claude mcp add --transport http notion https://mcp.notion.com/mcp
claude mcp add --transport http sentry https://mcp.sentry.dev/mcp

# Local (stdio) server: everything after -- is the command that starts it
claude mcp add filesystem -- npx -y @modelcontextprotocol/server-filesystem /path/to/allowed/dir

# Manage servers
claude mcp list
claude mcp remove notion
```

Inside a session, `/mcp` shows server status and handles OAuth sign-in for servers that need it.

### 14.3 Scopes: Who Gets the Server

| Scope | Flag | Stored in | Who gets it |
|---|---|---|---|
| Local (default) | `--scope local` | `~/.claude.json`, under this project | Only you, only this project |
| Project | `--scope project` | `.mcp.json` in the repo | Everyone who clones the repo (each person approves it) |
| User | `--scope user` | `~/.claude.json` | Only you, all your projects |

A project-scoped `.mcp.json` looks like this. `${VAR}` references are expanded from the environment, so secrets stay out of git:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./docs"]
    }
  }
}
```

!!! warning "Many early reference servers are archived"
    Several `@modelcontextprotocol/server-*` npm packages that older tutorials list, including `server-postgres`, `server-github`, `server-slack`, `server-puppeteer`, and `server-brave-search`, are marked deprecated on npm ("archived and unmaintained" or "no longer supported"). `server-sqlite` isn't published on npm. Before you install any MCP server, check that it's maintained. For GitHub, the docs use GitHub's hosted server, `https://api.githubcopilot.com/mcp/`.

### 14.4 Using MCP Tools in Conversation

Once a server is connected, ask for what you want and Claude picks the tool:

```
# With Sentry connected:
> what are the most frequent errors in the last 24 hours?

# With Notion connected:
> summarize the "Q3 roadmap" page

# With GitHub's MCP server connected:
> list open PRs in myorg/myrepo that are waiting on review
```

### 14.5 Building a Custom MCP Server

This minimal TypeScript server uses the low-level `Server` class from `@modelcontextprotocol/sdk`. It typechecks against SDK version 1.32. The SDK also offers a higher-level `McpServer` API; see the SDK's README.

```typescript
// minimal-mcp-server.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";

// Placeholder: replace with a call to your real deployment system.
async function checkMyDeploymentSystem(service: string) {
  return { service, status: "healthy" };
}

const server = new Server(
  { name: "my-custom-server", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "get_deployment_status",
      description: "Check the deployment status of a service",
      inputSchema: {
        type: "object",
        properties: {
          service: { type: "string", description: "Service name" }
        },
        required: ["service"]
      }
    }
  ]
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "get_deployment_status") {
    const { service } = request.params.arguments as { service: string };
    const status = await checkMyDeploymentSystem(service);
    return { content: [{ type: "text", text: JSON.stringify(status) }] };
  }
  throw new Error("Unknown tool");
});

const transport = new StdioServerTransport();
await server.connect(transport);
```

Compile it, then register it:

```bash
claude mcp add my-deploy-tool -- node path/to/minimal-mcp-server.js
```

---

## 15. Connectors & External Tools

Beyond MCP, Claude Code can reach external systems through any command-line tool on your machine.

### 15.1 Shell Commands as Connectors

Any CLI tool becomes a connector through Bash:

```
> check the current Kubernetes pod status
# Claude runs: kubectl get pods --all-namespaces

> deploy to staging
# Claude runs your deploy script

> how many active sessions are in the database?
# Claude runs: psql "$DATABASE_URL" -c "SELECT count(*) FROM sessions WHERE active"
```

Pre-approve the commands you trust (section 4.4) so you aren't asked every time.

### 15.2 Environment Variables for Secrets

Never hardcode secrets in files you commit. Keep them in your shell environment or a secrets manager:

```bash
# In ~/.bashrc or ~/.zshrc, or loaded by a tool like direnv:
export DATABASE_URL="postgresql://..."
export JIRA_API_TOKEN="..."
```

Claude Code passes your environment through to the commands it runs. The `env` block in `settings.json` sets fixed values for every session. Don't put secrets there if the file is committed. Also deny Claude read access to secret files, for example `"deny": ["Read(./.env)"]`.

### 15.3 Docker & Container Integration

```
> build and run the Docker container for local testing
> check the logs from the auth service container
> run the database migration inside the postgres container
```

### 15.4 Cloud Provider CLIs

```
# AWS (aws CLI)
> list all running EC2 instances in us-east-1

# Azure (az CLI)
> show the resource groups for the production subscription

# Google Cloud (gcloud). Sign in yourself first: ! gcloud auth login
> list all Cloud Run services in the project
```

---

## 16. Multi-Agent & Parallel Tasks

### 16.1 Subagents

A **subagent** is a separate Claude instance with its own context window. Claude delegates to one and gets back only a summary, so a large search doesn't fill your main conversation. Claude Code includes built-in subagents, such as one for read-only exploration, and you can define your own as Markdown files in `.claude/agents/` (project) or `~/.claude/agents/` (personal). See [subagents](https://code.claude.com/docs/en/sub-agents).

```
> use a subagent to find every place we read the DATABASE_URL variable
```

### 16.2 Background Work

```
> run the full test suite in the background and tell me when it's done
```

Press `Ctrl+B` to send a running command or agent to the background, and use `/tasks` to see background work.

### 16.3 The /loop Skill

`/loop` re-runs a prompt on an interval while the session stays open:

```
> /loop 5m check the latest CI run on this branch and report status
> /loop 10m check whether any new errors appeared in logs/app.log
> /loop check the deploy     # no interval: Claude decides how often to check
```

Recurring tasks expire automatically **7 days** after creation.

### 16.4 Parallel Agent Patterns

```
> analyze the frontend and backend performance in parallel and give me a combined report
# Claude can start several subagents at once and merge their results
```

For fully separate parallel sessions, run Claude in several worktrees (section 12).

### 16.5 Scheduled Tasks

| Option | Runs where | Survives restarts? |
|---|---|---|
| `/loop`, or "remind me in 30 minutes…" | In your current session | Restored with `--resume` / `--continue`, with some exceptions |
| Desktop scheduled tasks | Claude Desktop on your machine | Yes |
| Cloud scheduled tasks (`/schedule`) | Anthropic's cloud | Yes |

```
> /schedule every weekday at 9am, summarize new GitHub issues and PRs
```

---

## 17. Claude API & Model Selection

### 17.1 API Key Management

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
claude -p "hello"      # quick check that it works
```

### 17.2 Choosing the Right Model

| Task | Alias | Why |
|---|---|---|
| Hard, long-running problems | `fable` or `best` | The most capable models |
| Complex architecture and debugging | `opus` | Strong reasoning |
| Day-to-day coding | `sonnet` | Good balance of speed and quality |
| Quick lookups, simple edits | `haiku` | Fastest and cheapest |
| Plan with Opus, build with Sonnet | `opusplan` | Mixes the two |

### 17.3 Fast Mode

Fast mode runs Claude Opus with an API configuration that favors speed: up to 2.5x faster, at a higher cost per token. It's the same model, not a smaller one. It works on supported Opus versions only, not Sonnet or Haiku.

```
> /fast        # toggle; or /fast on, /fast off
```

### 17.4 Building Applications with the Claude API

The `/claude-api` skill gives Claude reference material for the Claude API and SDKs while you build.

**Example with prompt caching (TypeScript):**

```typescript
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

const response = await client.messages.create({
  model: "claude-sonnet-5-5",
  max_tokens: 4096,
  system: [
    {
      type: "text",
      text: "You are a helpful coding assistant...",
      cache_control: { type: "ephemeral" }  // cache this prefix for reuse
    }
  ],
  messages: [
    { role: "user", content: "Explain how to implement rate limiting" }
  ]
});

// A response can contain several kinds of content block; print the text ones.
for (const block of response.content) {
  if (block.type === "text") console.log(block.text);
}
```

Caching pays off for long system prompts that you reuse across many requests. Very short prompts fall below the minimum cacheable length and aren't cached. Check current [models](https://platform.claude.com/docs/en/about-claude/models/overview) and [pricing](https://platform.claude.com/docs/en/about-claude/pricing) in the Claude API docs.

### 17.5 Model IDs Quick Reference

Prefer aliases in Claude Code. Use full IDs only when you need to pin a version:

```
opus    → claude-opus-5-5      (Anthropic API, November 2026)
sonnet  → claude-sonnet-5-5
haiku   → claude-haiku-5-5
fable   → claude-fable-5-1
```

---

## 18. Permission Modes & Security

### 18.1 The Permission System Explained

Every tool call that needs permission goes through your rules first:

1. A matching **deny** rule blocks it.
2. A matching **ask** rule prompts you.
3. A matching **allow** rule runs it without asking.
4. If nothing matches, the current **permission mode** decides.

### 18.2 Permission Modes

| Mode | What runs without asking | Best for |
|---|---|---|
| `default` (shown as **Manual**) | Reads only | Reviewing every action yourself |
| `acceptEdits` | Reads, file edits, common filesystem commands | Iterating on code you're reviewing |
| `plan` | Reads; no edits until you approve a plan | Exploring before changing anything |
| `auto` | Everything, with background safety checks | Long tasks, fewer prompts |
| `dontAsk` | Only pre-approved tools; everything else is denied | Locked-down automation |
| `bypassPermissions` | Everything, with no checks | Isolated containers and VMs only |

Switch modes with `Shift+Tab`, or start in one with `claude --permission-mode <mode>`. In recent versions, interactive terminal and VS Code sessions start in `auto` by default. The [permission modes docs](https://code.claude.com/docs/en/permission-modes) explain which mode applies when.

When Claude asks, you can approve once, or choose "Yes, and don't ask again", which saves an allow rule.

### 18.3 Security Best Practices

**Do:** allow narrow, specific commands.

```json
{
  "permissions": {
    "allow": ["Bash(git log *)", "Bash(git diff *)", "Bash(git status)", "Bash(npm test)"],
    "deny": ["Read(./.env)", "Read(./secrets/**)"]
  }
}
```

**Don't:** allow every shell command. `Bash(*)` is the same as `Bash`.

```json
{
  "permissions": {
    "allow": ["Bash(*)"]
  }
}
```

Use `bypassPermissions` only inside a disposable container or VM.

### 18.4 Audit Logging with Hooks

See the logging hook in section 9.5. Hooks run regardless of what Claude decides, which makes them a reliable audit trail.

### 18.5 Project-Level vs Global Permissions

- **User** (`~/.claude/settings.json`): your safe defaults for every project
- **Project** (`.claude/settings.json`): project tools, committed and shared with the team. Teammates' allow rules apply only after they trust the folder, while deny and ask rules apply right away.
- **Local** (`.claude/settings.local.json`): your personal overrides, kept out of git

A deny rule at any level blocks the action, even if another level allows it.

---

## 19. IDE Integrations (VS Code & JetBrains)

### 19.1 VS Code Extension Features

- **Claude panel**: chat with Claude in the sidebar, an editor tab, or a new window
- **Inline diffs**: review Claude's proposed edits and accept or reject them change by change
- **Selection awareness**: Claude sees your selected text automatically
- **@-mentions**: reference files and line ranges, such as `@app.ts#5-10`
- **Plan review** and permission mode controls in the panel

**Key VS Code shortcuts:**

| Shortcut (Mac / Windows & Linux) | Action |
|---|---|
| `Cmd+Esc` / `Ctrl+Esc` | Toggle focus between the editor and Claude |
| `Cmd+Shift+Esc` / `Ctrl+Shift+Esc` | Open a new conversation in an editor tab |
| `Option+K` / `Alt+K` | Insert an @-mention of the current file and selection |

Type "Claude Code" in the Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`) to see every extension command.

### 19.2 JetBrains Plugin Features

- Works with most JetBrains IDEs: IntelliJ IDEA, PyCharm, WebStorm, GoLand, and others
- Runs the `claude` CLI in the IDE's terminal and connects it to the editor
- Shows Claude's proposed changes in the IDE's diff viewer

### 19.3 IDE vs CLI — When to Use Which

| Scenario | Good fit |
|---|---|
| Changes you want to review visually, diff by diff | IDE extension |
| Questions about the code you're looking at | IDE extension |
| Multi-file refactors, long tasks | Either |
| Scripts, CI, `claude -p` automation | CLI |
| Parallel sessions in worktrees | CLI |

---

## 20. Advanced Patterns & Workflows

### 20.1 The Explore-Plan-Execute Pattern

```
Phase 1 - Explore:
> how is authentication currently implemented? map out all the files involved

Phase 2 - Plan:
> /plan migrate this auth system from JWT sessions to OAuth2 using Auth0

Phase 3 - Execute (after you approve the plan)

Phase 4 - Verify:
> run all the auth tests and verify nothing is broken
> create a PR for these changes
```

### 20.2 Context Management

The context window holds your conversation, the files Claude has read, and tool output. Manage it:

```
> /context            # see what's using space
> /compact            # summarize the conversation so far, keeping the essentials
> /compact focus on the auth refactor
> /clear              # start fresh when you switch to an unrelated task
```

**Tips:**

- Clear context between unrelated tasks
- Point Claude at specific files rather than asking it to explore broadly
- Use subagents for big searches. Their exploration stays out of your main context, and only their summary comes back.

### 20.3 The "Rubber Duck" Pattern

```
> I need rate limiting for our API. Options:
  1. Redis-based sliding window
  2. In-memory fixed window per instance
  We run 5 API servers. Which would you recommend and why?

> now plan option 1 using our existing Redis connection
```

### 20.4 Code Review Workflow

```
# Before pushing:
> /review             # review your current diff for bugs
> /simplify           # clean up the changed code
> commit these changes

# After pushing:
> create a PR for these changes
```

### 20.5 Test-Driven Development with Claude

```
> write failing tests for a user authentication service that doesn't exist yet
> now implement the minimum code to make those tests pass
> refactor for clarity without breaking any tests
> add edge-case tests I might have missed
```

### 20.6 Debugging Production Issues

```
> we're getting this error in production: [paste error/stack trace]
> reproduce this locally and find the root cause
> fix it and add a regression test
> write a short postmortem of what happened and how we fixed it
```

### 20.7 Documentation Generation

```
> generate API documentation for all the endpoints in routes/
> update the README setup instructions to match what the code actually does
> write a changelog entry for the changes on this branch
```

### 20.8 Database Work

```
# With a database MCP server or psql available:
> show me the schema for the users table
> find N+1 query problems in the API code
> write a migration to add an index on users.email
> explain the query plan for this slow query: SELECT ...
```

Review schema changes and migrations yourself before you run them.

---

## 21. Troubleshooting & FAQ

### 21.1 Common Issues

**Claude keeps asking permission for the same command**

- Choose "Yes, and don't ask again", or add an allow rule with `/permissions`
- Check that no deny or ask rule matches. Those win over allow.

**The context window is filling up**

- `/context` shows what's using it, and `/compact` summarizes
- `/clear` when you change topics
- Delegate large searches to subagents

**Claude keeps repeating the same mistake**

- Add a clear rule to `CLAUDE.md`
- Check that no `CLAUDE.md` instruction contradicts what you're asking
- For something that must always happen, use a hook

**An MCP server won't connect**

```bash
claude mcp list          # shows each server's status
```

Inside a session, `/mcp` lets you reconnect or sign in. For a stdio server, run its command yourself in a terminal to see the error.

**GitHub operations fail**

```bash
gh auth status
gh auth login
```

**Hooks aren't firing**

- Run `/hooks` to confirm the hook is loaded
- Check the `matcher`: it's case-sensitive and matches tool names like `Bash`, `Edit|Write`
- Remember that input arrives as JSON on stdin. Test your script by piping sample JSON into it.
- Only exit code 2 blocks an action

**Something else is off**

Run `/doctor` to check your installation and configuration.

### 21.2 Performance Tips

| Tip | Impact |
|---|---|
| Use `haiku` or `sonnet` for simple tasks | Faster, cheaper |
| Pre-approve common commands | Fewer interruptions |
| Keep `CLAUDE.md` short and accurate | Less re-explaining, better adherence |
| Reference specific files | More focused work |
| `/clear` between unrelated tasks | Fresher context |
| Use prompt caching in API apps | Lower cost for repeated long prompts |

### 21.3 Best Practices Summary

**Do:**

- Write a good `CLAUDE.md` early
- Configure narrow permissions up front
- Use plan mode for significant changes
- Commit regularly and review diffs
- Run tests after Claude makes changes

**Don't:**

- Allow `Bash(*)`
- Let Claude change database schemas without review
- Trust output without running tests
- Put secrets in committed settings files
- Use `bypassPermissions` outside an isolated container or VM

---

## 22. Quick Reference Cheat Sheet

### Essential Commands
```bash
claude                          # Start in the current directory
claude "fix the bug in auth.py" # Start with an initial prompt
claude -p "explain this"        # Non-interactive: print and exit
claude -c                       # Continue the last conversation
claude -w my-feature            # Start in a new git worktree
claude --permission-mode plan   # Start in plan mode
/help                           # Show commands
/clear  /compact  /context      # Manage context
/model  /fast                   # Choose model / toggle fast mode
/plan                           # Plan before editing
/review                         # Review your diff or a PR
/loop 5m <prompt>               # Repeat a prompt on an interval
!<command>                      # Run a shell command directly
```

### Key Files
```
~/.claude/settings.json          # User settings
~/.claude/CLAUDE.md              # Personal instructions for all projects
~/.claude/keybindings.json       # Keyboard shortcuts
.claude/settings.json            # Project settings (commit this)
.claude/settings.local.json      # Personal project overrides (don't commit)
CLAUDE.md                        # Project instructions (commit this)
CLAUDE.local.md                  # Personal project instructions (don't commit)
.claude/skills/<name>/SKILL.md   # Project skills
.mcp.json                        # Project MCP servers (commit this)
```

### settings.json Template
```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "model": "sonnet",
  "permissions": {
    "allow": ["Bash(npm run *)", "Bash(git status)", "Bash(git diff *)", "WebSearch"],
    "deny": ["Read(./.env)", "Bash(git push --force *)"]
  }
}
```

### MCP Quick Setup
```bash
claude mcp add --transport http <name> <url>          # remote server
claude mcp add <name> -- <command> [args...]          # local stdio server
claude mcp add --scope project ...                    # share via .mcp.json
claude mcp list                                       # check status
```

### GitHub Workflow
```
!git checkout -b feature/my-feature
# ... work with Claude ...
> commit these changes
> create a PR for these changes with a description of what I built
```

### Models Quick Reference
```
fable / best   → hardest, longest-running tasks
opus           → complex reasoning and architecture
sonnet         → daily coding (good default)
haiku          → fast, lightweight tasks
opusplan       → Opus to plan, Sonnet to build
```

---

## What's Next?

1. **Connect an MCP server** for a tool your team uses every day
2. **Write a team `CLAUDE.md`** and commit it
3. **Turn a repeated workflow into a skill** in `.claude/skills/`
4. **Add a hook** for something that must always happen, such as formatting or blocking
5. **Automate PR review** with `/install-github-app` and GitHub Actions
6. **Read the official docs** at [code.claude.com/docs](https://code.claude.com/docs/en/overview)

---

*Tutorial checked against the Claude Code documentation as of November 2026.*
*Report issues with Claude Code itself: [anthropics/claude-code](https://github.com/anthropics/claude-code/issues). Report problems with this tutorial: [hoqugr-beep/claude-code-tutorial](https://github.com/hoqugr-beep/claude-code-tutorial/issues).*
