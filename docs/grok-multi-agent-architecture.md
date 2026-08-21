# Building a Grok-Style Multi-Agent Architecture with Claude

> A step-by-step guide to standing up a team of named Claude agents — each
> with a role and an icon — coordinated by a "Chief of Staff" agent that
> the user talks to directly. Agents can message each other peer-to-peer
> and pass data back and forth, not just report up a chain of command.

---

## Table of Contents

1. [What We're Building](#1-what-were-building)
2. [The Two Ways to Build This in Claude Code](#2-the-two-ways-to-build-this-in-claude-code)
3. [Step 1 — Design the Org Chart](#3-step-1--design-the-org-chart)
4. [Step 2 — Define Each Agent](#4-step-2--define-each-agent)
5. [Step 3 — Write the Chief of Staff's Brain](#5-step-3--write-the-chief-of-staffs-brain)
6. [Step 4 — Give Every Agent an Icon](#6-step-4--give-every-agent-an-icon)
7. [Step 5 — Enable True Peer-to-Peer Messaging](#7-step-5--enable-true-peer-to-peer-messaging)
8. [Step 6 — Pass Data In and Out of Agents](#8-step-6--pass-data-in-and-out-of-agents)
9. [Step 7 — The Oversight Loop (Chief of Staff Checks In)](#9-step-7--the-oversight-loop-chief-of-staff-checks-in)
10. [Step 8 — The User Only Talks to the Chief of Staff](#10-step-8--the-user-only-talks-to-the-chief-of-staff)
11. [Step 9 — Test-Drive the Team](#11-step-9--test-drive-the-team)
12. [Lightweight Alternative: Single-Session Subagents](#12-lightweight-alternative-single-session-subagents)
13. [Best Practices & Pitfalls](#13-best-practices--pitfalls)
14. [Full Reference Example](#14-full-reference-example)

---

## 1. What We're Building

Think of a Grok/"agentic team" style assistant: a roster of named
specialists — a Researcher, an Engineer, a Reviewer, a Writer — each with
its own identity and icon, all reachable from one another, orchestrated by
a single "front door" agent the user actually talks to.

```
                         ┌─────────────────┐
                         │       You        │
                         └────────┬─────────┘
                                  │  (only interface)
                                  ▼
                    ┌──────────────────────────┐
                    │  🧭 Chief of Staff         │
                    │  delegates · tracks ·      │
                    │  checks agents stay on     │
                    │  track · reports back      │
                    └───┬─────────┬─────────┬────┘
             spawns/msgs│  msgs   │  msgs   │msgs
                        ▼         ▼         ▼
                 ┌───────────┐ ┌─────────┐ ┌───────────┐
                 │ 🔎 Research│ │ 🛠️ Eng   │ │ ✍️ Writer  │
                 └─────┬─────┘ └────┬────┘ └─────┬─────┘
                       │            │             │
                       └──── every agent can ─────┘
                              message every
                              other agent directly
```

The two properties that make this "Grok-bot-like" rather than a plain
tool-calling chain:

- **Named identity per agent** — each one has a name, a role, and an icon,
  not just an anonymous "sub-task."
- **Full mesh, not a tree** — any agent can message any other agent
  directly (Researcher → Engineer without going back through the Chief of
  Staff), while the Chief of Staff still owns oversight and is the only
  one the user talks to.

---

## 2. The Two Ways to Build This in Claude Code

Claude Code gives you two different primitives for multi-agent work, and
they have a real capability difference you should pick deliberately:

| | **Subagents** (`Agent` tool) | **Sessions** (Claude Code Remote / claude.ai/code) |
|---|---|---|
| Created with | `.claude/agents/*.md` definitions, spawned via the `Agent` tool | `create_session` (or the New Session button) |
| Relationship | **Hierarchical** — a spawned subagent reports back only to whoever spawned it | **Peer** — any session can `SendMessage` any other session it knows about |
| Lifetime | Lives for the task, then returns a final report | Persistent — keeps running, has its own identity, can be resumed |
| Identity in UI | A role name in the transcript | A real session with a **title** (your icon!) in the sessions list |
| Best for | Fast, disposable fan-out work (research, parallel file review) | A durable "team" that talks to each other and to you over time |

**For a genuine Grok-style architecture — full mesh messaging, individual
persistent identities, a Chief of Staff that checks on agents over
time — build it on Sessions.** Steps 3–11 below use that model. If you only
need short-lived helpers that report back to one coordinator and don't need
to talk to each other, the lighter subagent version in
[Section 12](#12-lightweight-alternative-single-session-subagents) is
enough and much cheaper to run.

---

## 3. Step 1 — Design the Org Chart

Before touching config, write down the roster. Keep it small — 3-5
specialists is plenty; a bigger mesh gets noisy fast.

| Name | Icon | Role | Owns |
|---|---|---|---|
| **Chief of Staff** | 🧭 | Orchestrator | Talks to the user, delegates, tracks status, reports back |
| **Scout** | 🔎 | Researcher | Web/codebase research, fact-finding, competitive analysis |
| **Forge** | 🛠️ | Engineer | Writes and tests code |
| **Sentinel** | 🛡️ | Reviewer/QA | Reviews Forge's work, runs tests, flags risks |
| **Quill** | ✍️ | Writer | Turns findings into docs, summaries, PR descriptions |

Write a one-line **charter** for each — what it owns, what it must never
do (e.g. "Forge never merges its own PRs — Sentinel signs off first"). This
charter becomes that agent's system prompt in the next step.

---

## 4. Step 2 — Define Each Agent

Each named agent is its own session with its own persistent instructions.
The instructions live in that agent's project as a `CLAUDE.md` (or, if all
agents share one repo, as a role file each agent is told to read first).

**`agents/scout/CLAUDE.md`:**

```markdown
# Role: Scout 🔎 — Researcher

You are Scout, the research specialist on this team. Your Chief of Staff
is 🧭 Chief of Staff — you take assignments from them and report findings
back to them, but you may also be messaged directly by other named agents
(🛠️ Forge, 🛡️ Sentinel, ✍️ Quill) and should answer their questions too.

## What you own
- Web research, competitive analysis, fact-checking
- Reading and summarizing large codebases or docs before Forge builds anything

## Rules
- Always cite sources for factual claims.
- Never write production code — hand findings to Forge.
- When you finish an assignment, message the requester back with a
  structured summary (see "Data handoff format" below) — do not wait to
  be asked.

## Data handoff format
When you complete research, reply with:
  SUMMARY: <2-3 sentence takeaway>
  KEY FACTS: <bulleted list>
  SOURCES: <links or file:line references>
  OPEN QUESTIONS: <anything unresolved>
```

Repeat this pattern for each agent (`agents/forge/CLAUDE.md`,
`agents/sentinel/CLAUDE.md`, `agents/quill/CLAUDE.md`), swapping in that
agent's charter from Step 1. Keep every agent's file aware of **who else
is on the team and what they own** — that's what makes "any agent can talk
to any agent" actually work in practice, rather than agents not knowing
who to ask.

Create the sessions, one per agent, each pointed at its own working
directory (or its own git worktree/branch if they share a repo):

```
create_session(
  title: "🔎 Scout — Researcher",
  prompt: "Read CLAUDE.md in this directory and confirm you understand
           your role before taking any assignment.",
  source_url: "<repo>", 
  source_revision: "agent/scout"
)
```

Do the same for Forge, Sentinel, and Quill. Keep a note of each returned
`session_id` — the Chief of Staff needs them to address messages.

---

## 5. Step 3 — Write the Chief of Staff's Brain

The Chief of Staff is the one agent the user actually talks to, so its
system prompt (its `CLAUDE.md`) is the most important file in the whole
architecture. It needs three things: the **roster**, the **delegation
policy**, and the **oversight policy**.

**`agents/chief-of-staff/CLAUDE.md`:**

```markdown
# Role: Chief of Staff 🧭

You are the Chief of Staff for a small team of named Claude agents. The
user only talks to you — you never expose raw agent chatter to them
unless they ask to see it. Your job: understand the user's request,
delegate it to the right specialist(s), keep everyone on track, and
report back a clean summary.

## Your team
| Name | Icon | Role | Session ID |
|---|---|---|---|
| Scout    | 🔎 | Research      | <session_id_scout> |
| Forge    | 🛠️ | Engineering   | <session_id_forge> |
| Sentinel | 🛡️ | Review/QA     | <session_id_sentinel> |
| Quill    | ✍️ | Writing/docs  | <session_id_quill> |

## Delegation policy
1. Break the user's request into role-shaped chunks.
2. Message each relevant agent directly with a clear, self-contained
   assignment (they don't see this conversation — give them full context).
3. Tell agents explicitly when they should message EACH OTHER instead of
   coming back through you (e.g. "Forge, once you're done, send your diff
   straight to Sentinel for review — don't wait for me").
4. Track every open assignment. Nothing gets marked done until the owning
   agent confirms.

## Oversight policy — you are responsible for keeping agents on track
- After delegating, schedule a check-in (do not just wait silently).
- If an agent goes quiet or drifts off-brief, message them directly and
  ask for a status update before re-escalating to the user.
- If two agents disagree or block each other, you resolve it or bring a
  crisp decision to the user — never relay the raw disagreement.
- Before reporting "done" to the user, confirm Sentinel has signed off on
  anything Forge produced.

## Reporting to the user
Always summarize in plain language: what was asked, what each agent did,
what's still open. Only show raw agent output if asked.
```

---

## 6. Step 4 — Give Every Agent an Icon

Claude Code doesn't render custom image avatars per agent, but there is a
real, visible slot for an icon: the **session title**, set with
`set_session_title` (or at creation time via `create_session`'s `title`
field). Titles show up in the sessions list in the web/desktop UI and in
`list_sessions` output — that list *is* your roster view, icon and all.

**Convention:** `"<emoji> <Name> — <Role>"`, e.g. `"🔎 Scout — Researcher"`.
Use the same emoji everywhere that agent is referenced — in its own
`CLAUDE.md`, in the Chief of Staff's roster table, and in every message
sent to or about it. Consistency is what makes the emoji function as an
icon rather than decoration: the user learns "🔎 = Scout" the same way they
learn a favicon.

```
set_session_title(session_id: "<scout_id>", title: "🔎 Scout — Researcher")
set_session_title(session_id: "<forge_id>", title: "🛠️ Forge — Engineer")
set_session_title(session_id: "<sentinel_id>", title: "🛡️ Sentinel — Reviewer")
set_session_title(session_id: "<quill_id>", title: "✍️ Quill — Writer")
set_session_title(session_id: "<cos_id>", title: "🧭 Chief of Staff")
```

If you also publish status dashboards or summaries as an Artifact (HTML),
carry the same emoji + name pairing into that page's agent cards — now the
icon shows up visually too, not just as a text glyph.

---

## 7. Step 5 — Enable True Peer-to-Peer Messaging

This is what separates a Grok-style *mesh* from a plain hub-and-spoke
delegation chain. Session-based agents can message each other directly:

- `ListAgents` — any agent can look up who else is reachable (teammates,
  other local sessions, cloud sessions) to find the right name/ID to
  address.
- `SendMessage` — send a message straight to another named agent's
  session, with its context intact. The receiving agent wakes up, reads
  the message as a new turn, and can reply the same way.

**The key design move:** tell every agent, in its `CLAUDE.md`, that it is
allowed and expected to message peers directly for anything that doesn't
need the Chief of Staff's judgment call. For example, Forge's file should
say:

```markdown
## Talking to teammates
When your code change is ready, use SendMessage to send it straight to
🛡️ Sentinel for review — do not route it through 🧭 Chief of Staff first.
Only escalate to Chief of Staff if Sentinel blocks you or you're unsure
which agent owns something.
```

This keeps the Chief of Staff from becoming a bottleneck (every message
does not need to round-trip through it) while it still retains oversight
— because Step 7 has every agent report status back to it on a cadence,
regardless of who else they talked to.

**Discovery pattern:** rather than hardcoding every session ID everywhere,
have each agent call `ListAgents` when it needs to reach a peer it doesn't
have an ID for yet, and cross-reference by the name/title convention from
Step 4 (`"🛡️ Sentinel — Reviewer"`). The Chief of Staff's roster table is
the source of truth for names; `ListAgents` is the source of truth for
current session IDs.

---

## 8. Step 6 — Pass Data In and Out of Agents

"Data in and out" means every agent needs a predictable way to (a) receive
a well-formed assignment and (b) hand back a well-formed result — not free
text the receiving agent has to guess how to parse.

**Three handoff mechanisms, pick based on payload size:**

| Payload | Mechanism |
|---|---|
| Small (a decision, a status, a short answer) | Inline in the `SendMessage` text, using a structured format (see below) |
| Medium (a research summary, a code diff, a draft doc) | Same, but as a fenced block within the message |
| Large (datasets, generated files, many-file diffs) | Write to a shared file/artifact, message the *path or URL*, not the content |

**Structured message format** — have every agent use the same envelope so
recipients (human or agent) can parse it at a glance:

```
FROM: 🔎 Scout
TO: 🛠️ Forge
TASK: <what was asked>
STATUS: complete | blocked | partial
PAYLOAD:
  <the actual data — findings, diff, draft, etc.>
NEXT: <what the recipient should do with this>
```

**For large payloads**, use a shared location both agents can reach — a
path in a shared repo/worktree, or a published Artifact URL — and pass
only the pointer:

```
FROM: 🛠️ Forge
TO: 🛡️ Sentinel
TASK: Review the auth refactor
STATUS: complete
PAYLOAD: diff pushed to branch `agent/forge/auth-refactor`, PR not yet opened
NEXT: review, then either approve (I'll open the PR) or send blocking
      issues back to me
```

The Chief of Staff should require this envelope format in every agent's
`CLAUDE.md` so that when it asks "what's the status," any agent's answer
is machine-parseable enough to roll up into a clean report for the user.

---

## 9. Step 7 — The Oversight Loop (Chief of Staff Checks In)

"In charge of all the other agents, checking that they are on track" needs
to be an actual mechanism, not a vibe. Give the Chief of Staff a recurring
check-in using a scheduled trigger bound to its own session:

```
create_trigger(
  name: "Team status sweep",
  prompt: "Check in with every agent on the roster: message each one
           asking for a one-line status (on track / blocked / done). If
           anyone hasn't responded to their last assignment, escalate by
           messaging them directly. Summarize any blockers.",
  cron_expression: "0 * * * *",   # hourly, adjust to your team's pace
  initiation: "own_followup"
)
```

On each firing, the Chief of Staff:
1. Messages every active agent for a status.
2. Compares against what it delegated (keep a running task list — the
   `TaskCreate`/`TaskList` tools or a simple markdown checklist in its own
   `CLAUDE.md`/memory work fine).
3. Nudges anyone who's gone quiet or drifted off-brief.
4. Only surfaces to the user when there's something worth surfacing —
   a blocker, a decision needed, or a completed deliverable. Silent
   sweeps stay silent.

This is also where "chief of staff checks that they're on track" becomes
literal: it's not just relaying messages, it's the one agent with a
standing view of the whole roster's state.

---

## 10. Step 8 — The User Only Talks to the Chief of Staff

This is a policy, not a technical lock — enforce it by convention and by
what you expose:

- Give the user one entry point: the Chief of Staff's session (or a
  connector/channel — Slack, `claude.ai/code` — that's bound only to that
  session).
- Every other agent's `CLAUDE.md` should say explicitly: *"You do not talk
  to the user directly. If a user question reaches you, hand a summary
  back to 🧭 Chief of Staff instead of answering it yourself."* This
  matters because SendMessage-reachable agents could technically be
  messaged by anyone with access — the instruction is what keeps the
  *pattern* hub-shaped for the user even though the *mesh* is fully
  connected underneath.
- The Chief of Staff's `CLAUDE.md` (Step 3) already states it never
  exposes raw agent chatter unless asked — that's the other half of the
  same contract.

---

## 11. Step 9 — Test-Drive the Team

A good first request exercises delegation, peer messaging, data handoff,
and the oversight loop all at once:

```
You → 🧭 Chief of Staff:
"Look into whether we should switch our rate limiter from in-memory to
Redis, prototype it if it makes sense, and give me a one-page writeup."
```

Expected flow:
1. 🧭 Chief of Staff messages 🔎 Scout: research in-memory vs. Redis
   rate limiting trade-offs for our setup.
2. 🔎 Scout replies with a structured summary (Step 6 format); Chief of
   Staff reviews and decides it's worth prototyping.
3. 🧭 Chief of Staff messages 🛠️ Forge with Scout's findings attached,
   asking for a prototype.
4. 🛠️ Forge builds it, then — per its own `CLAUDE.md` — messages 🛡️
   Sentinel **directly**, without routing back through the Chief of Staff.
5. 🛡️ Sentinel reviews, approves, messages Forge and the Chief of Staff.
6. 🧭 Chief of Staff messages ✍️ Quill with Scout's research + Forge's
   diff + Sentinel's sign-off, asking for the one-pager.
7. 🧭 Chief of Staff delivers the finished writeup to you, with a short
   note on who did what — not a wall of raw agent transcripts.

If step 4 instead round-trips through the Chief of Staff, that's a sign
the peer-messaging instruction in Forge's `CLAUDE.md` needs to be more
explicit — go back to Step 5.

---

## 12. Lightweight Alternative: Single-Session Subagents

If you don't need persistent, peer-messaging agents — just fast delegated
work inside one session — use the built-in `Agent` tool with custom
subagent definitions instead of standing up separate sessions. This trades
away true peer-to-peer messaging (subagents report only to whoever spawned
them) for much lower overhead.

**`.claude/agents/scout.md`:**

```markdown
---
name: scout
description: Research specialist — web and codebase research, fact-finding. Use for any research-heavy sub-task before implementation.
tools: WebSearch, WebFetch, Grep, Glob, Read
model: inherit
---

You are Scout 🔎, the research specialist. Return findings in this format:
SUMMARY / KEY FACTS / SOURCES / OPEN QUESTIONS. Never write production code.
```

Define `forge.md`, `sentinel.md`, `quill.md` the same way (each with its
own `tools` allowlist and charter), and give the **primary** session's
`CLAUDE.md` the Chief of Staff instructions from Step 3, minus the
session/`SendMessage` mechanics — it delegates via the `Agent` tool
instead:

```markdown
# You are the Chief of Staff 🧭 for this session's sub-agents:
🔎 scout (research) · 🛠️ forge (engineering) · 🛡️ sentinel (review) ·
✍️ quill (writing)

Delegate role-shaped work to the matching sub-agent via the Agent tool.
Since sub-agents can't message each other directly here, relay handoffs
between them yourself using the structured envelope format, and never let
Forge's output reach the user without Sentinel's review first.
```

Because subagents can't reach each other, the Chief of Staff itself plays
message-router for handoffs (Forge's diff → Sentinel, Sentinel's verdict →
Forge). It's a real limitation versus the session-based mesh — decide
which trade-off fits your use case before building.

---

## 13. Best Practices & Pitfalls

**DO:**
- Keep the roster small (3–5 agents) — a bigger mesh means more
  coordination overhead than value.
- Give every agent a written charter that says what it owns *and* what it
  must hand off.
- Use one consistent icon+name convention everywhere (titles, messages,
  dashboards) — that consistency is what makes it feel like a team, not a
  pile of anonymous tool calls.
- Require the structured handoff envelope (Step 6) — free-text handoffs
  degrade fast as the team grows.
- Let the Chief of Staff stay a router and status-tracker, not a
  bottleneck — peer agents should talk directly when the call doesn't need
  its judgment.

**DON'T:**
- Don't let every agent talk to the user directly — one entry point keeps
  the experience coherent and lets the Chief of Staff maintain context.
- Don't skip the oversight loop — "in charge of checking they're on track"
  needs a scheduled check-in, not an assumption that agents self-report.
- Don't pass large payloads inline in messages — use a shared file/branch/
  artifact and hand over the pointer.
- Don't give every agent every tool — scope each agent's `tools` to what
  its role actually needs (Scout doesn't need `Edit`; Forge doesn't need
  `WebSearch` unless research is explicitly its job).

---

## 14. Full Reference Example

A minimal end-to-end roster you can copy and adapt:

```
Team: Product Launch Squad

🧭 Chief of Staff   — user-facing, delegates, tracks, reports
🔎 Scout             — research & fact-finding
🛠️ Forge             — implementation
🛡️ Sentinel          — review & QA, gatekeeper before anything ships
✍️ Quill             — docs, summaries, external-facing writing

Wiring:
- 5 sessions, one per agent, each with its own CLAUDE.md charter
- Titles set to "<emoji> <Name> — <Role>" for the roster/icon view
- Chief of Staff's CLAUDE.md holds the roster table + delegation/oversight policy
- Every agent's CLAUDE.md: (a) knows the full roster, (b) uses the
  structured handoff envelope, (c) knows which peers it may message
  directly vs. which decisions need Chief of Staff sign-off, (d) never
  talks to the user directly
- Chief of Staff has an hourly "team status sweep" trigger for oversight
```

From here, extend the roster as real needs show up — but resist growing it
faster than the Chief of Staff's oversight loop can actually track. A team
of five well-defined agents that stay on track beats a team of fifteen that
drift.

---

*Part of the [Claude Code Tutorial](index.md). See [Section 16: Multi-Agent
& Parallel Tasks](index.md#16-multi-agent--parallel-tasks) for the basics
this guide builds on.*
