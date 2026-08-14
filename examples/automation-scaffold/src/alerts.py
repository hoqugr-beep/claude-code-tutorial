"""Operator alerting.

The client should never be the one who discovers it broke. Every failure lands
here, goes to stderr (which your host captures), and optionally POSTs to a
webhook — a Slack incoming webhook URL is the usual choice.

This is small, and it is most of what justifies an operating fee.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

from . import settings


def alert(subject: str, detail: str = "", *, client_id: str | None = None) -> None:
    """Report a failure to the operator. Never raises."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    tag = f"[{client_id}] " if client_id else ""
    line = f"{stamp} ALERT {tag}{subject}"

    print(line, file=sys.stderr)
    if detail:
        print(f"  {detail}", file=sys.stderr)

    if not settings.ALERT_WEBHOOK:
        return

    body = json.dumps({"text": f"{line}\n{detail}".strip()}).encode()
    request = urllib.request.Request(
        settings.ALERT_WEBHOOK,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=10).close()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # An alerting failure must never take down the run that was trying to
        # report a problem. Fall back to stderr and carry on.
        print(f"  (alert webhook failed: {exc})", file=sys.stderr)
