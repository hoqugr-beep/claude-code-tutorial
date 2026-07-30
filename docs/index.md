# Claude Code: Comprehensive Interactive Tutorial
### From Beginner to Advanced

> **Last Updated:** June 2026 | Covers Claude Code CLI, Desktop App, IDE Extensions, MCP, GitHub, and more.

---

## Table of Contents

1. [What is Claude Code?](#what-is-claude-code)
2. [Installation & Initial Setup](#2-installation--initial-setup)
3. [First Run & Basic Navigation](#3-first-run--basic-navigation)
4. [Settings & Configuration](#4-settings--configuration)
5. [CLAUDE.md — Your Project Brain](#5-claudemd--your-project-brain)
6. [Built-in Tools Reference](#6-built-in-tools-reference)
7. [Slash Commands & Skills](#7-slash-commands--skills)
8. [Keybindings Customization](#8-keybindings-customization)
9. [Hooks System](#9-hooks-system)
10. [Memory System](#10-memory-system)
11. [Plan Mode](#11-plan-mode)
12. [Worktrees (Isolated Git Workspaces)](#12-worktrees-isolated-git-workspaces)
13. [GitHub Integration](#13-github-integration)
14. [MCP — Model Context Protocol](#14-mcp--model-context-protocol)
15. [Connectors & External Tools](#15-connectors--external-tools)
16. [Multi-Agent & Parallel Tasks](#16-multi-agent--parallel-tasks)
17. [Claude API & Model Selection](#17-claude-api--model-selection)
18. [Permission Modes & Security](#18-permission-modes--security)
19. [IDE Integrations (VS Code & JetBrains)](#19-ide-integrations-vs-code--jetbrains)
20. [Advanced Patterns & Workflows](#20-advanced-patterns--workflows)
21. [Troubleshooting & FAQ](#21-troubleshooting--faq)
22. [Quick Reference Cheat Sheet](#22-quick-reference-cheat-sheet)

---

## 1. What is Claude Code?

Claude Code is Anthropic's official AI coding assistant available as:

| Interface | Best For |
|---|---|
| **CLI** (`claude`) | Terminal-native workflows, scripts, CI/CD |
| **Desktop App** | Mac/Windows GUI with full Claude Code power |
| **Web App** | `claude.ai/code` — browser-based access |
| **VS Code Extension** | Inline AI assistance inside VS Code |
| **JetBrains Plugin** | IntelliJ, PyCharm, WebStorm, etc. |

### Key Capabilities

- Read, write, and edit files across your entire project
- Run shell commands, tests, and builds
- Search code with regex (ripgrep-powered)
- Browse the web for up-to-date documentation
- Integrate with GitHub (PRs, issues, commits)
- Connect to external services via MCP servers
- Spawn parallel sub-agents for complex tasks
- Maintain persistent memory across sessions

---

## 2. Installation & Initial Setup

### 2.1 CLI Installation

```bash
# Install via npm (Node.js 18+ required)
npm install -g @anthropic-ai/claude-code

# Verify installation
claude --version
```

### 2.2 Authentication

```bash
# Option A: Interactive login (opens browser)
claude

# Option B: API key via environment variable
export ANTHROPIC_API_KEY="sk-ant-..."

# Option C: Set permanently in your shell profile
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc
source ~/.bashrc
```

### 2.3 Desktop App

1. Download from [claude.ai](https://claude.ai) — available for Mac and Windows
2. Sign in with your Anthropic account
3. The app bundles the CLI — you get both the GUI and terminal access

### 2.4 VS Code Extension

1. Open VS Code → Extensions (`Ctrl+Shift+X`)
2. Search: **Claude Code**
3. Click Install
4. Sign in via the sidebar or `Ctrl+Shift+P` → "Claude Code: Sign In"

### 2.5 JetBrains Plugin

1. Open your JetBrains IDE → Settings → Plugins
2. Search: **Claude Code**
3. Install and restart the IDE

### 2.6 Directory Structure Created on First Run

```
~/.claude/
├── settings.json          # Global user settings
├── keybindings.json       # Custom keyboard shortcuts
├── projects/              # Per-project memory and plans
│   └── <project-hash>/
│       ├── memory/        # Persistent memory files
│       │   ├── MEMORY.md  # Memory index
│       │   └── *.md       # Individual memory files
│       └── plans/         # Plan mode documents
└── scheduled_tasks.json   # Durable cron jobs
```

---

## 3. First Run & Basic Navigation

### 3.1 Starting Claude Code

```bash
# Start in current directory (recommended — gives full project context)
cd /path/to/your/project
claude

# Start with an immediate prompt
claude "explain what this project does"

# Run a one-shot command (non-interactive)
claude --print "what files are in this directory?"
```

### 3.2 The REPL Interface

Once inside Claude Code you'll see a prompt like:
```
Claude Code > _
```

Type naturally — Claude Code understands plain English requests alongside technical commands.

### 3.3 Basic Commands to Know First

| What to type | What happens |
|---|---|
| `/help` | Show all available commands |
| `/exit` or `Ctrl+C` | Exit Claude Code |
| `/clear` | Clear conversation context |
| `!ls -la` | Run a shell command directly |
| `Ctrl+R` | Search conversation history |

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

Settings live in two places — global user settings and project-level overrides.

### 4.1 Settings File Locations

| File | Scope | Priority |
|---|---|---|
| `~/.claude/settings.json` | Global (all projects) | Lower |
| `.claude/settings.json` | Project-level | Higher |
| `.claude/settings.local.json` | Local overrides (gitignored) | Highest |

### 4.2 Core settings.json Structure

```json
{
  "model": "claude-opus-4-6",
  "permissions": {
    "allow": [
      "Bash(git *)",
      "Bash(npm *)",
      "Bash(python *)",
      "Read(**)",
      "Edit(**)"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Bash(curl * | bash)"
    ]
  },
  "hooks": {
    "PreToolUse": [...],
    "PostToolUse": [...],
    "Stop": [...]
  },
  "env": {
    "NODE_ENV": "development"
  },
  "includeCoAuthored": true,
  "cleanupPeriodDays": 30
}
```

### 4.3 Model Selection in Settings

```json
{
  "model": "claude-opus-4-6",
  "smallModel": "claude-haiku-4-5-20251001"
}
```

**Available Models (June 2026):**

| Model ID | Best For |
|---|---|
| `claude-opus-4-6` | Complex reasoning, architecture, advanced tasks |
| `claude-sonnet-4-6` | Balanced speed/quality — great default |
| `claude-haiku-4-5-20251001` | Fast, lightweight tasks |

### 4.4 Permission Rules Deep Dive

Permissions use glob-style patterns to control what Claude can do without asking:

```json
{
  "permissions": {
    "allow": [
      "Bash(git log *)",          // Allow all git log variants
      "Bash(git diff *)",
      "Bash(git status)",
      "Bash(npm test)",
      "Bash(npm run *)",           // Allow all npm scripts
      "Read(**)",                  // Allow reading any file
      "Edit(src/**)",              // Allow editing files in src/
      "WebSearch(*)"               // Allow web searches
    ],
    "deny": [
      "Bash(git push --force *)", // Never force push
      "Bash(rm -rf *)",           // Never recursive delete
      "Bash(DROP TABLE *)"        // Never drop tables
    ]
  }
}
```

**Permission pattern syntax:**
- `*` — matches anything within a path segment
- `**` — matches across path segments (recursive)
- `Bash(command pattern)` — matches specific shell commands
- `Edit(path pattern)` — matches file paths for editing

### 4.5 Efficient Settings for a Developer

```json
{
  "model": "claude-sonnet-4-6",
  "permissions": {
    "allow": [
      "Bash(git *)",
      "Bash(npm *)",
      "Bash(node *)",
      "Bash(python *)",
      "Bash(pytest *)",
      "Bash(cargo *)",
      "Bash(go *)",
      "Bash(make *)",
      "Bash(docker *)",
      "Read(**)",
      "Edit(**)",
      "WebSearch(*)",
      "WebFetch(*)"
    ],
    "deny": [
      "Bash(rm -rf /)",
      "Bash(git push --force)"
    ]
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'File edited: checking for issues...'"
          }
        ]
      }
    ]
  },
  "includeCoAuthored": true,
  "env": {
    "EDITOR": "code",
    "GIT_EDITOR": "code --wait"
  }
}
```

---

## 5. CLAUDE.md — Your Project Brain

`CLAUDE.md` is a special markdown file Claude Code reads automatically when you start a session in a project. It's how you give Claude persistent, project-specific instructions.

### 5.1 Where to Place CLAUDE.md Files

```
/project-root/
├── CLAUDE.md              # Root — always loaded
├── src/
│   └── CLAUDE.md          # Loaded when working in src/
├── backend/
│   └── CLAUDE.md          # Loaded when working in backend/
└── frontend/
    └── CLAUDE.md          # Loaded when working in frontend/
```

Claude loads the CLAUDE.md nearest to the files you're working with, plus the root one.

### 5.2 What to Put in CLAUDE.md

```markdown
# Project: MyApp

## Overview
This is a React + FastAPI application for managing inventory.
Backend uses PostgreSQL with SQLAlchemy ORM.

## Development Commands
- Start backend: `cd backend && uvicorn main:app --reload`
- Start frontend: `cd frontend && npm run dev`
- Run all tests: `npm test && pytest`
- Lint: `npm run lint && ruff check .`

## Architecture Notes
- API lives in `backend/api/` — all routes use dependency injection
- Database models are in `backend/models/` — always use Alembic for migrations
- Frontend state is managed with Zustand (not Redux)
- Auth uses JWT tokens stored in httpOnly cookies

## Coding Conventions
- Python: Black formatting, type hints required, docstrings for public functions
- TypeScript: strict mode enabled, no `any` types
- Commits: conventional commits format (feat:, fix:, chore:, etc.)
- PRs: always include test coverage for new features

## Things to Avoid
- Never modify `backend/config.py` directly — use environment variables
- Don't use `console.log` in production code — use the logger utility
- Don't bypass TypeScript errors with `@ts-ignore`

## Testing
- Unit tests: pytest with fixtures in `tests/conftest.py`
- E2E tests: Playwright in `e2e/`
- Run a specific test: `pytest tests/test_auth.py -v`

## External Services
- Database: PostgreSQL on port 5432 (see .env.example)
- Redis cache on port 6379
- S3-compatible storage via MinIO in dev
```

### 5.3 CLAUDE.md Best Practices

- **Keep it up to date** — outdated instructions confuse Claude
- **Be specific** — "use Zustand" beats "use modern state management"
- **Include run commands** — Claude needs to know how to test and build
- **Document gotchas** — things that aren't obvious from code
- **Use it for team conventions** — commit the file to share with your team

---

## 6. Built-in Tools Reference

Claude Code has a rich set of built-in tools. Understanding them helps you write better prompts.

### 6.1 File System Tools

| Tool | What it does | Example prompt |
|---|---|---|
| **Read** | Read any file | "read the config file" |
| **Write** | Create or overwrite a file | "create a new component file" |
| **Edit** | Make targeted edits (efficient, shows diffs) | "fix the bug on line 42" |
| **Glob** | Find files by pattern | "find all .test.ts files" |
| **Grep** | Search file contents with regex | "find all TODO comments" |

### 6.2 Execution Tools

| Tool | What it does | Example prompt |
|---|---|---|
| **Bash** | Run shell commands | "run the tests" |
| **NotebookEdit** | Edit Jupyter notebooks | "add a cell to the notebook" |

### 6.3 Research Tools

| Tool | What it does | Example prompt |
|---|---|---|
| **WebSearch** | Search the internet | "look up the React 19 docs" |
| **WebFetch** | Fetch a specific URL | "read the content at this URL" |

### 6.4 Orchestration Tools

| Tool | What it does | Example prompt |
|---|---|---|
| **Agent** | Spawn a sub-agent for complex tasks | Automatic — Claude uses this internally |
| **Task** tools | Track todo lists | Automatic — Claude uses this internally |

### 6.5 Tool Usage Tips

**Be specific to get the right tool:**
```
# Vague (Claude must guess)
> look at the auth stuff

# Better (Claude knows to use Grep + Read)
> find where JWT tokens are generated and read that file

# Best (Claude can go straight to work)
> grep for "jwt.sign" in the backend/ directory, then read the file that contains it
```

---

## 7. Slash Commands & Skills

### 7.1 Built-in Slash Commands

| Command | Description |
|---|---|
| `/help` | Show help and all available commands |
| `/clear` | Clear conversation context (start fresh) |
| `/exit` | Exit Claude Code |
| `/fast` | Toggle fast mode (same Opus model, faster output) |
| `/tasks` | Show background tasks |
| `/memory` | View/manage memory |

### 7.2 User-Invocable Skills

Skills are extended capabilities invoked with `/skill-name`:

| Skill | What it does |
|---|---|
| `/commit` | Create a git commit with an AI-written message |
| `/review-pr` | Review a pull request |
| `/simplify` | Review changed code for quality issues and fix them |
| `/loop [interval] [command]` | Run a command on a recurring schedule |
| `/update-config` | Configure Claude Code settings interactively |
| `/keybindings-help` | Help customizing keyboard shortcuts |
| `/claude-api` | Build/debug Claude API applications |

### 7.3 Running Shell Commands Inline

Prefix any command with `!` to run it directly:

```
> !git status
> !npm test
> !docker ps
> !ls -la src/
```

### 7.4 Creating Custom Skills

Create a custom skill file at `.claude/commands/my-skill.md`:

```markdown
# My Custom Deploy Skill

Run the full deployment pipeline:

1. Run tests: `npm test`
2. Build: `npm run build`
3. Deploy to staging: `./deploy.sh staging`
4. Verify deployment: `curl https://staging.myapp.com/health`

Report results and any failures.
```

Then invoke it with `/my-skill`.

---

## 8. Keybindings Customization

### 8.1 Default Keybindings

| Key | Action |
|---|---|
| `Enter` | Submit message |
| `Shift+Enter` | Add newline |
| `Ctrl+C` | Cancel / Exit |
| `Ctrl+R` | Search history |
| `Up/Down arrows` | Navigate history |
| `Ctrl+L` | Clear screen |

### 8.2 Customizing Keybindings

Edit `~/.claude/keybindings.json`:

```json
[
  {
    "key": "ctrl+shift+c",
    "command": "claude.commit",
    "description": "Quick commit"
  },
  {
    "key": "ctrl+shift+t",
    "command": "claude.runTests",
    "description": "Run tests"
  },
  {
    "key": "ctrl+shift+r",
    "command": "claude.reviewChanges",
    "description": "Review current changes"
  }
]
```

### 8.3 Chord Bindings

Chord bindings require pressing two key combinations in sequence:

```json
[
  {
    "key": "ctrl+k ctrl+c",
    "command": "claude.commit",
    "description": "Chord: commit"
  },
  {
    "key": "ctrl+k ctrl+p",
    "command": "claude.createPR",
    "description": "Chord: create PR"
  }
]
```

Use the `/keybindings-help` skill to get guided setup assistance.

---

## 9. Hooks System

Hooks let you run shell commands automatically at specific points in Claude Code's operation. This is powerful for auditing, validation, and automation.

### 9.1 Hook Types

| Hook | When it fires |
|---|---|
| `PreToolUse` | Before Claude uses any tool |
| `PostToolUse` | After Claude uses any tool |
| `Notification` | When Claude sends a notification |
| `Stop` | When Claude finishes a response |

### 9.2 Hook Configuration in settings.json

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "echo \"[AUDIT] About to run bash command: $CLAUDE_TOOL_INPUT\" >> ~/.claude/audit.log"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "cd $CLAUDE_PROJECT_DIR && npm run lint --fix 2>/dev/null || true"
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

### 9.3 Hook Environment Variables

Hooks receive these environment variables:

| Variable | Value |
|---|---|
| `CLAUDE_TOOL_NAME` | Name of the tool being used (e.g., "Bash", "Edit") |
| `CLAUDE_TOOL_INPUT` | JSON input to the tool |
| `CLAUDE_PROJECT_DIR` | Current project directory |
| `CLAUDE_SESSION_ID` | Unique session identifier |

### 9.4 Practical Hook Examples

**Auto-format on save:**
```json
{
  "PostToolUse": [
    {
      "matcher": "Edit",
      "hooks": [
        {
          "type": "command",
          "command": "prettier --write \"$CLAUDE_TOOL_INPUT_PATH\" 2>/dev/null || true"
        }
      ]
    }
  ]
}
```

**Block dangerous commands:**
```json
{
  "PreToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "command": "echo \"$CLAUDE_TOOL_INPUT\" | grep -q 'DROP TABLE' && exit 1 || exit 0"
        }
      ]
    }
  ]
}
```

**Log all file edits:**
```json
{
  "PostToolUse": [
    {
      "matcher": "Edit",
      "hooks": [
        {
          "type": "command",
          "command": "echo \"$(date): Edited $CLAUDE_TOOL_INPUT\" >> ~/claude-edits.log"
        }
      ]
    }
  ]
}
```

Use the `/update-config` skill to configure hooks interactively.

---

## 10. Memory System

Claude Code has a persistent file-based memory system that survives across sessions.

### 10.1 Memory Types

| Type | Purpose | Example |
|---|---|---|
| **user** | Who you are, your role, preferences | "I'm a senior Go developer new to React" |
| **feedback** | How Claude should behave | "Don't add trailing summaries to responses" |
| **project** | Project context, goals, decisions | "We're migrating from MongoDB to Postgres by Q3" |
| **reference** | Pointers to external resources | "Bug tracker is in Linear project MYAPP" |

### 10.2 Memory File Location

```
~/.claude/projects/<project-hash>/memory/
├── MEMORY.md          # Index file (always loaded)
├── user_role.md       # Your role/background
├── feedback_style.md  # Communication preferences
├── project_goals.md   # Current project context
└── reference_tools.md # External resource pointers
```

### 10.3 Asking Claude to Remember Things

```
> Remember that I prefer concise responses without trailing summaries

> Remember that this project uses pnpm, not npm

> Remember that I'm a backend developer — explain frontend concepts in backend terms

> Remember that our staging environment is at staging.internal.mycompany.com

> Forget what you remembered about the old auth system — we've migrated to OAuth
```

### 10.4 Memory Best Practices

- **Be specific** about what to remember — vague memories don't help
- **Update stale memories** — things change, tell Claude when they do
- **Use it for preferences** — coding style, communication style, expertise level
- **Don't use it for code** — code lives in the repo, not memory

---

## 11. Plan Mode

Plan mode lets Claude explore your codebase and design an implementation approach before writing any code. It's a safety net for complex changes.

### 11.1 When Plan Mode Activates

Claude automatically enters plan mode for:
- New feature implementations
- Multi-file changes
- Tasks with multiple valid approaches
- Architectural decisions
- Unclear requirements

### 11.2 Working with Plan Mode

```
> add OAuth2 authentication to the API
# Claude enters plan mode, explores codebase, then presents:
# - What files need to change
# - Proposed approach (e.g., which OAuth library to use)
# - Risks and trade-offs
# - Questions for you to answer

> Yes, proceed with the plan
# Claude exits plan mode and implements

> Use Passport.js instead of jose, and add Google as the only provider
# Claude updates the plan and asks again before implementing
```

### 11.3 Plan Mode Tips

- **Ask questions before approving** — this is your chance to redirect
- **Request alternatives** — "show me a simpler approach" or "what if we used X instead"
- **Plans are saved** to `.claude/plans/` — you can review them
- **Force plan mode** by starting your prompt with "Plan how to..."

---

## 12. Worktrees (Isolated Git Workspaces)

Worktrees create isolated copies of your repo for parallel work — perfect for experimenting without affecting your main branch.

### 12.1 Starting a Worktree

```
> start a worktree
# Claude creates a new git worktree in .claude/worktrees/<name>/
# Claude switches the session to work in that worktree

> start a worktree named oauth-experiment
# Named worktree
```

### 12.2 Working in a Worktree

```
# Inside a worktree session, all your work is isolated:
> refactor the auth module to use JWT
# Changes only affect the worktree, not your main branch

> exit the worktree and keep my changes
# Exits worktree, keeps the branch for later

> exit the worktree and discard everything
# Exits and deletes the worktree — clean slate
```

### 12.3 Worktree Use Cases

- **Risky refactors** — experiment without fear
- **Parallel features** — work on multiple features simultaneously across sessions
- **Reproducing bugs** — isolate the bug-reproduction environment
- **Code review** — check out a PR branch in a worktree without disturbing your work

---

## 13. GitHub Integration

Claude Code integrates deeply with GitHub via the `gh` CLI tool.

### 13.1 Prerequisites

```bash
# Install GitHub CLI
# macOS
brew install gh

# Windows
winget install GitHub.cli

# Linux
sudo apt install gh

# Authenticate
gh auth login
```

### 13.2 Common GitHub Workflows

**Create a PR:**
```
> create a pull request for these changes
# Claude will:
# 1. Check git status and diff
# 2. Review all commits since branching
# 3. Write a PR title and description
# 4. Push the branch
# 5. Open the PR with gh pr create
```

**Review an existing PR:**
```
> review PR #142
> /review-pr 142
# Claude fetches the PR, reads all changed files, and provides a thorough review
```

**Commit with a good message:**
```
> /commit
# Claude:
# 1. Runs git status and git diff
# 2. Reads recent commit messages to match your style
# 3. Writes a meaningful commit message
# 4. Creates the commit
```

**Work with Issues:**
```
> list open issues labeled "bug"
> create an issue for the authentication timeout bug I just found
> close issue #89 — we fixed it in the last commit
```

### 13.3 GitHub Actions Integration

```
> look at the failing CI run and tell me what's wrong
# Claude fetches the workflow run output via gh run view

> add a GitHub Actions workflow for running tests on every PR
# Claude creates .github/workflows/test.yml

> fix the flaky test that's causing CI failures
# Claude reads the test, analyzes the failure pattern, and fixes it
```

### 13.4 Useful gh Commands to Know

```bash
# These work directly via ! prefix in Claude Code:
!gh pr list                    # List open PRs
!gh pr view 142                # View PR details
!gh pr checkout 142            # Check out a PR branch
!gh run list                   # List CI runs
!gh run view <run-id>          # View CI run output
!gh issue list --label bug     # List bug issues
!gh release create v1.2.3      # Create a release
```

---

## 14. MCP — Model Context Protocol

MCP (Model Context Protocol) is a standard protocol that lets Claude connect to external data sources, tools, and services. Think of MCP servers as plugins that extend what Claude can access.

### 14.1 What MCP Servers Do

MCP servers give Claude access to:
- **Databases** — query Postgres, MySQL, SQLite directly
- **APIs** — Slack, Jira, Linear, Notion, etc.
- **File systems** — remote files, cloud storage
- **Custom tools** — anything your team builds

### 14.2 Configuring MCP Servers

Add MCP server configuration to `settings.json` or `.claude/settings.json`:

```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost/mydb"],
      "description": "Local development database"
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}",
        "SLACK_TEAM_ID": "T0123456"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"],
      "description": "Extended filesystem access"
    }
  }
}
```

### 14.3 Popular MCP Servers

| MCP Server | npm Package | What it enables |
|---|---|---|
| **PostgreSQL** | `@modelcontextprotocol/server-postgres` | SQL queries on Postgres |
| **SQLite** | `@modelcontextprotocol/server-sqlite` | SQLite database access |
| **GitHub** | `@modelcontextprotocol/server-github` | Advanced GitHub operations |
| **Filesystem** | `@modelcontextprotocol/server-filesystem` | Extended file access |
| **Brave Search** | `@modelcontextprotocol/server-brave-search` | Web search via Brave |
| **Slack** | `@modelcontextprotocol/server-slack` | Read/post Slack messages |
| **Puppeteer** | `@modelcontextprotocol/server-puppeteer` | Browser automation |
| **Memory** | `@modelcontextprotocol/server-memory` | Persistent knowledge graph |

### 14.4 Using MCP Tools in Conversation

Once an MCP server is configured, Claude uses its tools automatically:

```
# With postgres MCP configured:
> show me the 10 most recent users who signed up
# Claude queries: SELECT * FROM users ORDER BY created_at DESC LIMIT 10;

# With Slack MCP configured:
> what did the #engineering channel discuss today?
# Claude reads recent Slack messages

# With GitHub MCP configured:
> list all open PRs in the myorg/myrepo repository
# Claude uses the GitHub MCP to fetch PRs
```

### 14.5 Building a Custom MCP Server

```typescript
// minimal-mcp-server.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";

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
    // Your custom logic here
    const status = await checkMyDeploymentSystem(service);
    return { content: [{ type: "text", text: JSON.stringify(status) }] };
  }
  throw new Error("Unknown tool");
});

const transport = new StdioServerTransport();
await server.connect(transport);
```

Register it in settings.json:
```json
{
  "mcpServers": {
    "my-deploy-tool": {
      "command": "node",
      "args": ["path/to/minimal-mcp-server.js"]
    }
  }
}
```

---

## 15. Connectors & External Tools

Beyond MCP, Claude Code connects to external systems through several mechanisms.

### 15.1 Shell Commands as Connectors

Any CLI tool becomes a connector via Bash:

```
> check the current Kubernetes pod status
# Claude runs: kubectl get pods --all-namespaces

> deploy to staging
# Claude runs your deploy script

> query the database for active sessions
# Claude runs: psql $DATABASE_URL -c "SELECT count(*) FROM sessions WHERE active=true"
```

### 15.2 Environment Variables for Secrets

Never hardcode secrets. Use environment variables:

```bash
# In your shell profile (~/.bashrc or ~/.zshrc):
export DATABASE_URL="postgresql://..."
export SLACK_WEBHOOK_URL="https://hooks.slack.com/..."
export JIRA_API_TOKEN="..."
```

Reference them in settings.json:
```json
{
  "env": {
    "DATABASE_URL": "${DATABASE_URL}"
  }
}
```

### 15.3 Docker & Container Integration

```
> build and run the Docker container for local testing
> check the logs from the auth service container
> run the database migration inside the postgres container
> inspect the network between the API and database containers
```

### 15.4 Cloud Provider CLIs

```bash
# AWS — Claude can use awscli
> list all running EC2 instances in us-east-1
> check the CloudWatch logs for the API lambda

# Azure — Claude can use az cli
> show the resource group for the production environment

# GCP — Claude can use gcloud (requires interactive login first)
# ! gcloud auth login
> list all Cloud Run services in the project
```

---

## 16. Multi-Agent & Parallel Tasks

For complex tasks, Claude Code can spawn multiple sub-agents working in parallel.

### 16.1 How Multi-Agent Works

Claude automatically uses sub-agents for:
- Open-ended research that spans many files
- Tasks that need isolated exploration
- Parallel code generation across multiple modules
- Background monitoring tasks

### 16.2 Spawning Work in Background

```
> in the background, run the full test suite and tell me when it's done
# Claude starts a background Bash task and continues being responsive

> keep checking the CI status every 5 minutes until it passes
# Use /loop for this:
> /loop 5m check the latest CI run status and report results
```

### 16.3 The /loop Skill

`/loop` runs a prompt or command on a recurring schedule:

```
# Basic usage
> /loop 10m check if any new error logs appeared

# With a slash command
> /loop 5m /review-pr

# Check deployment
> /loop 2m check if the deployment to staging completed successfully

# Loop self-terminates after 7 days
```

### 16.4 Parallel Agent Patterns

```
> analyze both the frontend and backend performance simultaneously and give me a combined report
# Claude spawns parallel agents to analyze both, merges the results

> review all the changed files in this PR in parallel
# Claude spawns one agent per file for speed
```

### 16.5 Scheduled Tasks (Cron)

```
# Session-only (disappears when Claude Code exits):
> remind me in 30 minutes to push my changes

# Durable (persists across sessions, 7-day max):
> every day at 9am, summarize any new GitHub issues and PRs
```

### 16.6 Defining Your Own Reusable Agents

Beyond the built-in sub-agents, you can define your own in `.claude/agents/*.md` — with a custom
system prompt, a locked-down tool list, and its own model — then commit it so your team gets it
too. See **[Reusable Agents](reusable-agents.md)** for the full walkthrough, including how to
invoke one and how to package it as an installable plugin.

---

## 17. Claude API & Model Selection

### 17.1 API Key Management

```bash
# Set your API key
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# Verify it works
claude --print "hello" 
```

### 17.2 Choosing the Right Model

| Task | Recommended Model | Why |
|---|---|---|
| Complex architecture decisions | `claude-opus-4-6` | Best reasoning |
| Day-to-day coding | `claude-sonnet-4-6` | Best balance |
| Quick lookups, simple edits | `claude-haiku-4-5-20251001` | Fastest, cheapest |
| Code review | `claude-opus-4-6` | Thoroughness |
| Generating boilerplate | `claude-haiku-4-5-20251001` | Speed |

### 17.3 Fast Mode

Fast mode uses the same Opus model with optimized output:

```
> /fast
# Toggles fast mode on/off
```

### 17.4 Building Applications with the Claude API

Use the `/claude-api` skill when building Claude-powered applications:

```
> /claude-api
# Opens guided Claude API development mode
```

**Example API usage with prompt caching:**

```typescript
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

// Always use prompt caching for large system prompts
const response = await client.messages.create({
  model: "claude-sonnet-4-6",
  max_tokens: 4096,
  system: [
    {
      type: "text",
      text: "You are a helpful coding assistant...",
      cache_control: { type: "ephemeral" }  // Cache this system prompt
    }
  ],
  messages: [
    { role: "user", content: "Explain how to implement rate limiting" }
  ]
});

console.log(response.content[0].text);
```

### 17.5 Model IDs Quick Reference

```
claude-opus-4-6                    # Most capable
claude-sonnet-4-6                  # Best for most tasks  
claude-haiku-4-5-20251001          # Fastest/cheapest
```

---

## 18. Permission Modes & Security

### 18.1 The Permission System Explained

Every tool call goes through a permission check:

```
User request → Claude decides tool to use → Permission check → Tool executes (or prompts user)
```

**Permission decision flow:**
1. Check `deny` list — if matched, BLOCK
2. Check `allow` list — if matched, ALLOW silently
3. If neither — PROMPT the user to approve or deny

### 18.2 Interactive Permission Approvals

When Claude encounters a command not in your allow list:
```
Claude wants to run: git push origin main
[A]llow once | [D]eny | [L] Allow for this session | [P] Allow permanently
```

### 18.3 Security Best Practices

**DO:**
```json
{
  "permissions": {
    "allow": [
      "Bash(git log *)",
      "Bash(git diff *)",
      "Bash(git status)",
      "Bash(npm test)",
      "Read(**)"
    ]
  }
}
```

**DON'T (too permissive):**
```json
{
  "permissions": {
    "allow": [
      "Bash(*)"    // Allows ANYTHING — dangerous!
    ]
  }
}
```

### 18.4 Audit Logging with Hooks

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "echo \"$(date -u +%Y-%m-%dT%H:%M:%SZ) BASH: $CLAUDE_TOOL_INPUT\" >> ~/.claude/audit.log"
          }
        ]
      }
    ]
  }
}
```

### 18.5 Project-Level vs Global Permissions

```
# Global settings (~/.claude/settings.json):
# - Safe defaults for all projects
# - Minimal allow list

# Project settings (.claude/settings.json):  
# - Project-specific tools
# - Committed to the repo — shared with team

# Local settings (.claude/settings.local.json):
# - Your personal overrides
# - Add to .gitignore — never commit this
```

---

## 19. IDE Integrations (VS Code & JetBrains)

### 19.1 VS Code Extension Features

- **Inline chat** — select code, press shortcut, ask a question
- **Ghost text** — AI-powered completions as you type
- **Panel chat** — full Claude Code experience in a sidebar
- **File references** — drag files into the chat
- **Terminal integration** — run Claude commands from the terminal panel

**Key VS Code shortcuts:**
| Shortcut | Action |
|---|---|
| `Ctrl+Shift+I` | Open Claude Code panel |
| `Ctrl+I` | Inline edit selected code |
| `Ctrl+Shift+L` | Ask about selected code |

### 19.2 JetBrains Plugin Features

- Same core capabilities as VS Code
- Works in: IntelliJ IDEA, PyCharm, WebStorm, GoLand, Rider, CLion
- **Project-aware** — understands your IDE's project structure
- **Refactoring support** — works with IDE refactoring tools

### 19.3 IDE vs CLI — When to Use Which

| Scenario | Use |
|---|---|
| Writing code in a specific file | IDE extension |
| Complex multi-file refactors | CLI |
| Understanding a codebase | CLI |
| Quick edits, simple questions | IDE extension |
| Git operations, CI/CD | CLI |
| Automation scripts | CLI |
| PR reviews | CLI |

---

## 20. Advanced Patterns & Workflows

### 20.1 The Exploration-Plan-Execute Pattern

For complex tasks, break into phases:

```
Phase 1 - Explore:
> how is authentication currently implemented? map out all the files involved

Phase 2 - Plan:
> Plan how to migrate this auth system from JWT to OAuth2 using Auth0

Phase 3 - Execute (after reviewing and approving the plan):
> proceed with the plan

Phase 4 - Verify:
> run all the auth tests and verify nothing is broken
> create a PR for these changes
```

### 20.2 Context Management

Claude Code has a context window — manage it:

```
> /clear              # Clear context when changing topics entirely
> /compact            # Summarize and compress context (if available)

# Start with context already loaded:
claude "fix the failing test in auth.test.ts"
```

**Tips:**
- Clear context between unrelated tasks
- Reference specific files rather than asking Claude to explore broadly
- Use sub-agents for large explorations (they don't consume your context)

### 20.3 The "Rubber Duck" Pattern

Use Claude Code to think through problems:

```
> I need to implement rate limiting for our API. I'm considering two approaches:
  1. Redis-based sliding window
  2. In-memory fixed window per instance
  
  We have 5 API servers. Which would you recommend and why?

> Now plan the implementation of option 1 using our existing Redis connection
```

### 20.4 Code Review Workflow

```
# Before pushing a PR:
> review my changes since the last commit — look for bugs, security issues, and style problems
> /simplify
> /commit

# After pushing:
> create a PR for these changes and request review from the @backend-team
```

### 20.5 Test-Driven Development with Claude

```
> write failing tests for a user authentication service that doesn't exist yet
> now implement the minimum code to make those tests pass
> refactor the implementation for clarity without breaking any tests
> add edge case tests I might have missed
```

### 20.6 Debugging Production Issues

```
> we're getting this error in production: [paste error/stack trace]
> reproduce this locally and find the root cause
> fix it and add a regression test
> write a postmortem summary of what happened and how we fixed it
```

### 20.7 Documentation Generation

```
> generate API documentation for all the endpoints in routes/
> update the README with the current setup instructions based on what you see in the code
> create a changelog entry for the changes in this PR
```

### 20.8 Database Operations (with MCP)

```
# With PostgreSQL MCP configured:
> show me the schema for the users table
> find any N+1 query problems in the API code
> write a migration to add an index on users.email
> explain the query plan for this slow query: SELECT ...
```

---

## 21. Troubleshooting & FAQ

### 21.1 Common Issues

**"Claude is not allowed to run this command"**
- Add the command to your `permissions.allow` list in settings.json
- Or approve it interactively when prompted

**"Context window is getting large"**
- Use `/clear` to start fresh
- Be more specific in your requests to avoid broad exploration
- Use sub-agents for research-heavy tasks

**"Claude keeps repeating the same mistake"**
- Tell Claude explicitly: "Remember that you should X, not Y"
- Check if a CLAUDE.md instruction is contradicting you
- Use memory: "remember for future sessions that..."

**"MCP server isn't connecting"**
```bash
# Test your MCP server manually:
npx @modelcontextprotocol/server-postgres postgresql://localhost/mydb
```

**"GitHub operations failing"**
```bash
# Re-authenticate:
gh auth login
gh auth status
```

**"Hooks aren't firing"**
- Check the `matcher` field — it's case-sensitive
- Verify the command runs correctly in your shell manually
- Check the `CLAUDE_TOOL_NAME` value matches what you expect

### 21.2 Performance Tips

| Tip | Impact |
|---|---|
| Use `claude-haiku` for simple tasks | Faster, cheaper |
| Pre-approve common commands in settings | No approval delays |
| Use CLAUDE.md to avoid re-explaining context | Fewer round-trips |
| Reference specific files instead of asking Claude to search | More focused responses |
| Use `/clear` between unrelated tasks | Fresher context, better focus |
| Enable prompt caching in API applications | Significant cost savings |

### 21.3 Best Practices Summary

**DO:**
- Write a good CLAUDE.md before starting a project
- Configure sensible permissions upfront
- Use plan mode for significant changes
- Commit regularly and use meaningful commit messages
- Run tests after Claude makes changes
- Keep memory updated with current project state

**DON'T:**
- Give Claude overly broad `Bash(*)` permissions
- Let Claude make database schema changes without review
- Trust Claude's output without running tests
- Let context grow stale — use `/clear` between topics
- Store secrets in settings.json — use environment variables

---

## 22. Quick Reference Cheat Sheet

### Essential Commands
```bash
claude                          # Start Claude Code in current directory
claude "fix the bug in auth.py" # Start with an immediate task
claude --print "explain this"   # Non-interactive, print output only
/help                           # Show all commands
/clear                          # Clear conversation context
/fast                           # Toggle fast mode
/commit                         # AI-assisted git commit
/review-pr <number>             # Review a GitHub PR
/loop <interval> <command>      # Recurring task
!<command>                      # Run shell command directly
```

### Key Files
```
~/.claude/settings.json          # Global settings
~/.claude/keybindings.json       # Keyboard shortcuts
.claude/settings.json            # Project settings (commit this)
.claude/settings.local.json      # Local overrides (gitignore this)
CLAUDE.md                        # Project instructions for Claude
.claude/commands/*.md            # Custom skills
```

### Settings.json Template
```json
{
  "model": "claude-sonnet-4-6",
  "permissions": {
    "allow": ["Bash(git *)", "Bash(npm *)", "Read(**)", "Edit(**)", "WebSearch(*)"],
    "deny": ["Bash(rm -rf *)", "Bash(git push --force)"]
  },
  "mcpServers": {},
  "hooks": {},
  "includeCoAuthored": true
}
```

### MCP Servers Quick Setup
```bash
# Add to settings.json mcpServers:
# PostgreSQL:   "@modelcontextprotocol/server-postgres"
# GitHub:       "@modelcontextprotocol/server-github"  
# Filesystem:   "@modelcontextprotocol/server-filesystem"
# SQLite:       "@modelcontextprotocol/server-sqlite"
# Slack:        "@modelcontextprotocol/server-slack"
```

### GitHub Workflow
```bash
# Complete PR workflow:
!git checkout -b feature/my-feature
# ... make changes ...
/commit
# Claude writes commit message and commits

> create a PR for these changes with a description of what I built
# Claude creates the PR via gh CLI
```

### Models Quick Reference
```
claude-opus-4-6            → Complex tasks, architecture
claude-sonnet-4-6          → Daily coding (recommended default)
claude-haiku-4-5-20251001  → Fast, lightweight tasks
```

---

## What's Next?

Now that you have a solid foundation, explore these areas:

1. **Build a custom MCP server** for your internal tools
2. **Set up team-wide CLAUDE.md** to standardize AI assistance across your org
3. **Integrate Claude Code into CI/CD** — automated PR reviews, test generation
4. **Explore the Claude API** for building your own AI-powered tools with `/claude-api`
5. **Create a custom skills library** for your team's common workflows

---

*Tutorial written for Claude Code as of June 2026. Powered by Claude Sonnet 4.6.*
*Report issues or contribute: [anthropics/claude-code](https://github.com/anthropics/claude-code/issues)*
