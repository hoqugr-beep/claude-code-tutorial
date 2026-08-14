# Automation scaffold

A runnable starting point for the kind of tool you build once a client workflow
has earned it: high volume, repetitive, and needing output with the same shape
every time.

It processes a folder of documents per client, extracts structured records, and
writes results to an outbox — the "results appear where they already work"
delivery shape, which is the one small businesses adopt most reliably.

The example pipeline extracts supplier invoices. Swap the schema and the
instructions; the machinery around them does not change.

## Quickstart

```bash
cd examples/automation-scaffold
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # add your API key
cp clients.example.yaml clients.yaml

set -a && source .env && set +a

python -m src.run --dry-run   # validates config, makes no API calls
```

Then drop a text document into `inbox/acme/` and:

```bash
python -m src.run --client acme --limit 1
python -m src.run --usage     # what that just cost
```

Always run `--limit 1` first against real client data. It is the cheapest way to
find out that the instructions need work.

## What each piece does

| File | Responsibility |
|---|---|
| `src/settings.py` | Environment config. Every secret comes from the environment, never the repo. |
| `src/registry.py` | Per-client configuration loaded from `clients.yaml`. |
| `src/ledger.py` | **Usage recording and spend caps.** The module that makes this safe to sell. |
| `src/guarded.py` | The only code that calls the API. Cap check, schema enforcement, usage recording, typed errors. |
| `src/pipeline.py` | The actual work — document in, validated record out. |
| `src/deliver.py` | Results to CSV/JSON, plus a human-readable summary. |
| `src/alerts.py` | Failures go to you, not to the client. |
| `src/run.py` | Entrypoint for the scheduler. |
| `db/schema.sql` | Postgres schema for when you outgrow SQLite. |

## The four things it guarantees

Every API call goes through `guarded.extract()`, so these hold without anyone
needing to remember them:

1. **The spend cap is checked before the call.** A client at its cap stops the
   run cleanly and alerts you. One runaway loop cannot eat your margin.
2. **Output matches a fixed schema.** Structured outputs plus Pydantic
   validation, so downstream imports can rely on the shape.
3. **Usage is recorded per client, per call.** You cannot price an engagement
   or answer "is this client profitable?" without this.
4. **Failures are typed and actionable**, and reach you before they reach the
   client.

One bad document does not stop the batch — failures are collected, reported,
and the run continues.

## Deploying

Push to a host that runs scheduled jobs (Render and Railway both do this from a
git push). Set the environment variables in the host's settings, point a cron
schedule at `python -m src.run`, and let a non-zero exit code drive alerting.

Two things to get right in production:

- **Put `LEDGER_PATH` on a persistent volume.** If the ledger resets, so do
  your spend caps.
- **Move to Postgres before running more than one worker.** SQLite does not
  like concurrent writers. `db/schema.sql` has the migration.

## Adapting it

**Different extraction:** replace `InvoiceRecord` in `src/pipeline.py` and the
`instructions` in `clients.yaml`. Keep schemas flat — structured outputs support
types, enums and nesting, but not numeric or string range constraints, so
validate business rules in code.

**Different input route:** `pipeline.process()` reads files from a directory.
Point that at a synced cloud folder, an inbound-email webhook's payload, or an
upload endpoint — whichever route the engagement chose.

**Different delivery:** `deliver.summary_text()` already assembles the human
summary. Wire it to your transactional mail provider. It is deliberately not
implemented here, because shipping an untested mail path is worse than shipping
none.

## Before it touches a client invoice

The price table in `src/ledger.py` reflects published list rates at the time of
writing. Per-token pricing changes and promotional rates expire — verify it
against current published pricing before it informs anything you bill. It exists
so caps are enforceable, not as a billing source of truth.
