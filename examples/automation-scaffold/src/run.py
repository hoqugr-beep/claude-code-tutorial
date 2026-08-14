"""Entrypoint. This is what the scheduler calls.

    python -m src.run                  process every client
    python -m src.run --client acme    process one
    python -m src.run --limit 5        cap documents per client (useful on a
                                       first run against real data)
    python -m src.run --dry-run        validate config, touch no API
    python -m src.run --usage          print this month's spend per client

Exit codes: 0 all good, 1 something needed attention. Point your host's cron at
this and let a non-zero exit drive your alerting.
"""

from __future__ import annotations

import argparse
import sys

from . import alerts, deliver, ledger, pipeline, registry, settings


def _print_usage_report() -> int:
    ledger.init()
    rows = ledger.summary()
    if not rows:
        print("No usage recorded this month.")
        return 0

    print(f"{'client':<16}{'calls':>7}{'in tokens':>12}{'out tokens':>12}{'spend':>10}")
    print("-" * 57)
    total = 0
    for row in rows:
        print(
            f"{row['client_id']:<16}{row['calls']:>7}{row['input_tokens']:>12,}"
            f"{row['output_tokens']:>12,}{'$' + format(row['spend_usd'], '.2f'):>10}"
        )
        total += row["spend_usd"]
    print("-" * 57)
    print(f"{'total':<16}{'':>31}{'$' + format(total, '.2f'):>10}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the automation for all clients.")
    parser.add_argument("--client", help="process only this client id")
    parser.add_argument("--limit", type=int, help="max documents per client")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate configuration without calling the API",
    )
    parser.add_argument(
        "--usage", action="store_true", help="print this month's spend and exit"
    )
    args = parser.parse_args(argv)

    if args.usage:
        return _print_usage_report()

    try:
        clients = registry.load()
    except registry.RegistryError as exc:
        alerts.alert("configuration error", str(exc))
        return 1

    if args.client:
        if args.client not in clients:
            alerts.alert(
                "unknown client", f"{args.client!r} is not in {settings.CLIENTS_FILE}"
            )
            return 1
        clients = {args.client: clients[args.client]}

    if args.dry_run:
        print(f"Config OK — {len(clients)} client(s) loaded from {settings.CLIENTS_FILE}")
        for client in clients.values():
            pending = 0
            if client.inbox.exists():
                pending = sum(1 for p in client.inbox.iterdir() if p.is_file())
            print(
                f"  {client.id:<14} model={client.model:<18} "
                f"cap=${client.cap_usd} pending={pending}"
            )
        print("\nNo API calls were made.")
        return 0

    # Fail fast on missing credentials. Without this the key error surfaces
    # once per document, so a config mistake reads like every document being
    # unreadable — misleading at 1 document and useless at 200.
    try:
        settings.api_key()
    except settings.ConfigError as exc:
        alerts.alert("configuration error", str(exc))
        return 1

    ledger.init()
    exit_code = 0

    for client in clients.values():
        try:
            result = pipeline.process(client, limit=args.limit)
        except Exception as exc:  # noqa: BLE001 — one client must not stop the rest
            alerts.alert("run failed", str(exc), client_id=client.id)
            exit_code = 1
            continue

        if not result.processed and not result.failed:
            print(f"{client.id}: nothing pending")
            continue

        print(deliver.deliver(client, result))
        print()

        if result.failed or result.stopped_early:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
