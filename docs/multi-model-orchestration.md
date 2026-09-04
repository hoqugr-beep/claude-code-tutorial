# Multi-Model Orchestration: Claude + Gemini inside Grok Bot

> **Status:** Plan / proposal. **Written:** September 2026.
> Every claim about Grok Bot in this document comes from third-party
> reporting, not from xAI's own docs — `x.ai` was unreachable from the
> environment this was researched in. Verify the load-bearing points
> yourself before you build. They are flagged inline.

---

## The finding this plan rests on

You said you have Claude and Gemini as **consumer subscriptions only**, with
no API keys and no appetite for adding API billing. That would normally kill
a multi-model plan dead: you can't call a model you can't call.

It doesn't here, for one reason:

**Grok Bot's cloud computer has a terminal — and both Claude and Gemini ship
first-party CLIs that authenticate against consumer subscriptions rather than
metered API keys.**

| CLI | Auth method | What it bills against |
|---|---|---|
| `claude` (Claude Code) | Browser OAuth (`claude` → login) | Your Claude Pro/Max subscription — flat rate, shared 5-hour rolling pool |
| `gemini` (Gemini CLI) | Personal Google account sign-in | Gemini Code Assist individual free tier — approximately 1,000 requests/day, 60/minute, no card |

So the integration is not "wire up three APIs." It is: **install two CLIs on
the machine Grok Bot already owns, log into them once, and let the Bot shell
out to them.** Marginal cost per call: zero.

!!! warning "Verify this before you build on it"
    Anthropic's consumer plans are intended for use through Anthropic's own
    interfaces, and there is community reporting that subscription OAuth
    credentials are **not** permitted to power third-party agent products.
    Invoking the genuine `claude` binary is a different thing from extracting
    its token into another tool — but I cannot confirm that Anthropic
    considers "an xAI agent shelling out to `claude -p`" acceptable use.
    **Check Anthropic's current consumer terms before Phase 1.** The downside
    is account suspension, not a warning.

    Same discipline for Google: Gemini Code Assist for individuals went
    through a deprecation event on 2026-06-18 that ended service for the IDE
    extensions. The CLI path appears intact, but confirm current limits.

---

## What Grok Bot actually gives you

Established from third-party sources (Vellum, Composio, MindStudio, AY
Automate), consistent across all of them:

- **A persistent cloud computer**, shared across all Bots on the account,
  with a real browser, filesystem, and terminal. It keeps running when your
  laptop is closed.
- **Login handoff** — the Bot opens a sign-in page and hands control to you;
  you authenticate; it resumes with the session. Credentials aren't stored
  by the Bot.
- **MCP-enabled tools** and OAuth connectors (Gmail, Google Calendar, Drive,
  OneDrive, Outlook, Teams, SharePoint, Notion, Slack, and others), plus a
  custom-plugin option.
- **Routines** — workflows on a schedule or from an event trigger.
- **Multiple named Bots** that can message each other and share a thread.

Three of those matter for this plan: **the terminal** (how you reach Claude
and Gemini), **the shared filesystem** (how you pass context cheaply), and
**routines** (how this runs without you).

Grok Bot launched 2026-08-11 and is described as early beta. Expect the
surface to move.

---

## Architecture: three tiers, one machine

Don't think of this as "three chatbots." Think of it as one machine with
three tiers of thinking available on it, each with a different cost shape.

**Grok Bot — the orchestrator and the hands.**
It owns execution: the browser, the filesystem, the connectors, the schedule,
and real-time X/web data. It decides what needs doing and does it. It should
almost never be the thing doing long, careful reasoning — that's what burns
its quota.

**Gemini — the bulk-context tier.**
Roughly 1,000 requests/day and a very large context window, for free. This is
where volume goes: reading long documents, digesting transcripts, first-pass
triage, "summarize these 40 emails," "what changed across these 200 commits."
Cheap enough to be wasteful with.

**Claude — the judgment tier.**
A flat-rate but genuinely limited pool (Pro/Max meter on a rolling 5-hour
window). Spend it on the calls where being right matters: drafting something
you'll actually send, reviewing a plan for what's wrong with it, extracting
structured decisions from a messy transcript, reviewing a diff.

The routing rule in one line:

> **Bulk and cheap → Gemini. Careful and consequential → Claude. Execution,
> scheduling, and real-time → Grok.**

---

## Why this is actually token-efficient

You named token efficiency as a goal. The savings don't come from "using a
cheaper model." They come from three structural things:

**1. Pass by reference, not by value.**
This is the big one. All three tools run on the *same filesystem*. So context
moves between them as file paths, not as pasted text:

```bash
# Bad: 40k tokens through the orchestrator's context
grok reads transcript.txt → pastes it into a prompt → gets a summary

# Good: ~200 tokens through the orchestrator's context
gemini -p "Summarize decisions in transcript.txt → write decisions.md"
grok reads decisions.md
```

The orchestrator never holds the raw material. It holds a filename and a
digest. On a long document this is a 50–100x reduction in what passes through
Grok Bot's context.

**2. Fixed-cost second opinions.**
Because Claude and Gemini are flat-rate, a "consult" has zero marginal cost.
That changes what's worth doing: adversarial review of every plan, a
second-model check before any irreversible action, cross-checking a summary
against its source. On metered APIs you'd ration these. Here you shouldn't.

**3. The orchestrator stops re-reading.**
Long agentic loops are expensive mostly because the same context gets carried
forward turn after turn. Pushing the reading work out to a subprocess that
returns a file means Grok Bot's loop stays short.

---

## Implementation

The phases are a real sequence — each depends on the one before it.

### Phase 0 — Verify (do this first, it's the gate)

- [ ] Read Anthropic's current consumer terms on programmatic and third-party
      use of a Pro/Max subscription. **If this is disallowed, stop here** and
      either budget for an Anthropic API key or drop Claude from the plan.
- [ ] Confirm Gemini CLI's free tier is still available on a personal Google
      account, and note the current daily/minute limits.
- [ ] Confirm your Grok Bot plan tier includes the cloud computer and
      routines (reported as SuperGrok, Cursor Pro, and Cursor Teams).

### Phase 1 — Provision the CLIs

Ask a Bot to do this in its terminal, then use the login handoff for both
OAuth flows:

```bash
# Node 18+ required for both
npm install -g @anthropic-ai/claude-code
npm install -g @google/gemini-cli   # verify the current package name

claude          # opens browser OAuth → hand off, sign in with Pro/Max
gemini          # opens browser OAuth → hand off, sign in with Google
```

Because all Bots share one machine, you authenticate **once** and every Bot
on the account inherits both sessions.

### Phase 2 — Wrap them as file-in / file-out helpers

The wrappers are what enforce pass-by-reference. Put these on `PATH`:

```bash
#!/usr/bin/env bash
# ~/bin/ask-claude  —  judgment tier. Usage: ask-claude <out.md> <prompt...>
set -euo pipefail
out="$1"; shift
claude -p "$*" > "$out"
echo "Claude wrote $(wc -c < "$out") bytes to $out"
```

```bash
#!/usr/bin/env bash
# ~/bin/ask-gemini  —  bulk tier. Usage: ask-gemini <out.md> <prompt...>
set -euo pipefail
out="$1"; shift
gemini -p "$*" > "$out"
echo "Gemini wrote $(wc -c < "$out") bytes to $out"
```

Both wrappers print only a receipt, never the content. That is deliberate:
the orchestrator gets a filename and a size, and reads the file only if it
needs to.

!!! note "Flags to confirm"
    `claude -p` (print / non-interactive mode) is correct. The equivalent
    Gemini CLI flag is `-p`/`--prompt` as far as I can establish, but
    **check `gemini --help` on the machine** before committing the wrapper —
    don't take my word for a flag.

### Phase 3 — Write the routing policy where the Bot reads it

Create `~/ROUTING.md` on the cloud computer and tell your orchestrator Bot to
follow it. Something like:

```markdown
Before doing extended reading or reasoning yourself, route it:

- Any source material over ~2,000 words → ask-gemini. Never read it directly.
- Anything I will send, sign, publish, or spend money on → ask-claude
  for a review pass before it goes out.
- Structured extraction (decisions, owners, dates, JSON) → ask-claude.
- Bulk triage, summarization, "what's in these files" → ask-gemini.
- Real-time X/web data, browser work, connectors, scheduling → do it yourself.
- Never paste a file's contents into a prompt. Pass the path.
```

### Phase 4 — Build two or three routines, not ten

Start with the daily triage and the weekly review below. Get those reliable
before adding more. Early-beta scheduling is where this will break first.

### Phase 5 — Add a quota guardrail

Claude's pool is the scarce resource. Have the wrapper log every call, and
have a routine warn you when the judgment tier is being used for bulk work:

```bash
echo "$(date -Iseconds)\tclaude\t${#*}" >> ~/model-usage.tsv
```

Review it weekly. If `ask-claude` is firing more than `ask-gemini`, your
routing policy isn't being followed.

---

## Use cases

These are ordered by how much value they return for how little setup, not as
a sequence. Each names which tier does what.

### Daily inbox and calendar triage

**Gemini** reads the overnight mail and today's calendar via the connectors
and writes `triage.md` — what needs a reply, what's FYI, what conflicts.
**Claude** drafts replies for only the items marked "needs a real answer."
**Grok** sends the approved ones and blocks the calendar conflicts.
*Why it works:* the expensive tier touches three emails, not forty.

### Weekly review

**Gemini** digests the week — notes, commits, messages, completed tasks —
into a factual changelog. **Claude** turns that into an actual review: what
moved, what stalled, what to prioritize next week, and what you keep
deferring. **Grok** files it into Notion and creates next week's tasks.
*Why it works:* the synthesis step is exactly where a careful model earns
its keep, and it's operating on a digest, not raw material.

### Meeting → decisions → tasks

**Gemini** takes a long transcript (its context window handles hours of it)
and produces a clean summary. **Claude** extracts decisions, owners, and
deadlines as strict JSON. **Grok** creates the tasks in your PM tool.
*Why it works:* structured extraction is unforgiving of sloppiness, and
JSON either parses or it doesn't.

### Adversarial plan review

**Grok** drafts a plan. **Claude** red-teams it — what breaks, what's
assumed, what's missing. **Gemini** fact-checks the claims against your
source documents. You read the disagreements.
*Why it works:* three models agreeing is weak evidence; three models
disagreeing tells you exactly where to look. This is only affordable because
the consults are flat-rate.

### Second-opinion gate before irreversible actions

Before a Bot sends an external email, spends money, deletes anything, or
posts publicly, it routes the action to **Claude** for a yes/no plus one
sentence of reasoning. **Grok** proceeds only on yes.
*Why it works:* an always-on agent with browser access and your logins is
exactly the thing that should have a second opinion in front of its
irreversible actions.

### Long-document ingestion

Contracts, specs, research papers. **Gemini** does the full read and flags
the clauses worth attention. **Claude** examines only the flagged ones in
depth.
*Why it works:* two-pass reading is how humans do it, for the same reason.

### Code review on personal projects

**Grok** detects a push and hands the diff to **Claude Code**, which is
purpose-built for this and already has repo context. Findings go back as a
comment or a file.
*Why it works:* you're not approximating a code reviewer, you're calling one.

### Research briefs

**Grok** pulls real-time X and web results — this is the one thing only it
can do well. **Gemini** condenses the pile. **Claude** writes the brief.
*Why it works:* each tier does the thing it's uniquely good at and nothing
else.

---

## What not to do

**Don't automate the web UIs.** Grok Bot *can* log into `claude.ai` and
`gemini.google.com` in its browser and drive them like a human. Don't. It's
the most fragile path (CAPTCHAs, bot detection, DOM changes) and the most
clearly contrary to those services' terms. The CLI path is strictly better on
every axis.

**Don't chain all three on every task.** Three sequential model calls is
three round trips of latency and three quota draws. Most tasks need one tier.
The routing policy exists to pick one, not to fan out.

**Don't let Claude become the bulk tier.** It's the scarce resource. If you
find yourself routing summarization to it because the output reads better,
you'll exhaust the 5-hour pool mid-morning and the routines will fail
silently at 11am.

**Don't build ten routines before two are reliable.** This is an early-beta
product on a shared cloud VM. Reliability is the constraint, not capability.

**Don't skip Phase 0.** The entire plan is contingent on it.

---

## Open questions

Things I could not resolve and you'll need to settle:

1. **Does Anthropic permit this pattern?** The single blocking unknown.
2. **Does the shared cloud computer persist across sessions long enough for
   OAuth sessions to survive?** If Bots re-provision the VM, you may be
   re-authenticating constantly, which breaks unattended routines.
3. **Can a routine run unattended when a CLI needs re-auth?** Probably not.
   Plan for the failure mode.
4. **Is a custom MCP plugin a better integration surface than shell wrappers?**
   Grok Bot supports custom plugins and MCP tools. Wrapping `ask-claude` and
   `ask-gemini` as MCP tools would make the routing legible to the Bot rather
   than dependent on it following a markdown file. Worth trying once the
   shell version works.
