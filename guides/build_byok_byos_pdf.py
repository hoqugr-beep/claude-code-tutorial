"""Build the BYOK / BYOS orchestration procedure PDF.

Usage:  python3 guides/build_byok_byos_pdf.py
Output: guides/byok-byos-orchestration-procedure.pdf
Requires: reportlab
"""
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph, Preformatted,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

OUT = Path(__file__).with_name("byok-byos-orchestration-procedure.pdf")

ss = getSampleStyleSheet()
INK = colors.HexColor("#1f2937")
ACCENT = colors.HexColor("#1d4ed8")
MUTED = colors.HexColor("#6b7280")
CODEBG = colors.HexColor("#f3f4f6")
WARNBG = colors.HexColor("#fef3c7")
NOTEBG = colors.HexColor("#e0e7ff")

body = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.5,
                      leading=13.5, textColor=INK, spaceAfter=6)
h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=17,
                    leading=21, textColor=ACCENT, spaceBefore=6, spaceAfter=10, keepWithNext=1)
h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12.5,
                    leading=16, textColor=INK, spaceBefore=10, spaceAfter=5, keepWithNext=1)
h3 = ParagraphStyle("h3", parent=ss["Heading3"], fontName="Helvetica-Bold", fontSize=10.5,
                    leading=14, textColor=INK, spaceBefore=6, spaceAfter=3)
code = ParagraphStyle("code", fontName="Courier", fontSize=7.4, leading=9.4, textColor=INK,
                      backColor=CODEBG, borderPadding=(5, 5, 5, 5), spaceBefore=4,
                      spaceAfter=10, leftIndent=4, rightIndent=4)
cell = ParagraphStyle("cell", parent=body, fontSize=8.2, leading=10.5, spaceAfter=0)
cellb = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold")
title = ParagraphStyle("title", parent=h1, fontSize=26, leading=31, alignment=TA_CENTER)
subtitle = ParagraphStyle("subtitle", parent=body, fontSize=12.5, leading=17,
                          alignment=TA_CENTER, textColor=MUTED)

story = []


def H1(t):
    story.append(Paragraph(t, h1))


def H2(t):
    story.append(Paragraph(t, h2))


def H3(t):
    story.append(Paragraph(t, h3))


def P(t):
    story.append(Paragraph(t, body))


def B(items, numbered=False):
    story.append(ListFlowable(
        [ListItem(Paragraph(i, body), leftIndent=12) for i in items],
        bulletType="1" if numbered else "bullet", start="1" if numbered else None,
        leftIndent=14, bulletFontSize=8 if not numbered else 9.5))


def C(t):
    story.append(Preformatted(t.strip("\n"), code))


def BOX(t, bg=NOTEBG, label="Note"):
    tbl = Table([[Paragraph(f"<b>{label}.</b> {t}", cell)]], colWidths=[6.5 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8))


def WARN(t):
    BOX(t, WARNBG, "Verify")


def T(rows, widths):
    data = [[Paragraph(str(c), cellb if r == 0 else cell) for c in row]
            for r, row in enumerate(rows)]
    tbl = Table(data, colWidths=[w * inch for w in widths], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 10))


def arrow(d, x1, y1, x2, y2, col=MUTED):
    d.add(Line(x1, y1, x2, y2, strokeColor=col, strokeWidth=1))
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    s = 5
    p1 = (x2 - s * math.cos(a - 0.4), y2 - s * math.sin(a - 0.4))
    p2 = (x2 - s * math.cos(a + 0.4), y2 - s * math.sin(a + 0.4))
    d.add(Polygon([x2, y2, p1[0], p1[1], p2[0], p2[1]], fillColor=col, strokeColor=col))


def box(d, x, y, w, h, label, sub="", fill=colors.HexColor("#eff6ff")):
    d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=ACCENT, strokeWidth=0.8))
    d.add(String(x + w / 2, y + h / 2 + (3 if sub else -3), label, fontName="Helvetica-Bold",
                 fontSize=7.6, textAnchor="middle", fillColor=INK))
    if sub:
        d.add(String(x + w / 2, y + h / 2 - 8, sub, fontName="Helvetica", fontSize=6.4,
                     textAnchor="middle", fillColor=MUTED))


def architecture_diagram():
    d = Drawing(468, 300)
    green = colors.HexColor("#ecfdf5")
    amber = colors.HexColor("#fffbeb")
    box(d, 5, 250, 110, 38, "Browser / client", "Cloudflare Pages SPA")
    box(d, 175, 250, 120, 38, "Supabase Auth", "JWT issuance (JWKS)")
    box(d, 150, 160, 170, 60, "Orchestrator (Worker)", "auth > resolve > route > meter",
        fill=colors.HexColor("#dbeafe"))
    box(d, 5, 165, 110, 38, "Credential vault", "AES-GCM envelope", fill=amber)
    box(d, 5, 95, 110, 38, "Postgres (Supabase)", "tenants, creds, usage", fill=amber)
    box(d, 355, 170, 108, 38, "Rate limit / cache", "Upstash Redis / KV", fill=amber)
    box(d, 150, 80, 170, 45, "Provider adapters", "uniform request / response shape")
    # provider row
    xs = [0, 95, 190, 285, 380]
    names = [("OpenAI", "BYOK"), ("Anthropic", "BYOK"), ("Gemini", "BYOK"),
             ("AWS Bedrock", "BYOS: assumed role"), ("Azure OpenAI", "BYOS: endpoint")]
    for x, (n, s) in zip(xs, names):
        box(d, x + 3, 8, 82, 36, n, s, fill=green)
        arrow(d, 235, 80, x + 44, 44)
    arrow(d, 60, 250, 190, 220)
    arrow(d, 115, 270, 175, 270)
    arrow(d, 235, 250, 235, 222)
    d.add(String(242, 233, "verify JWT", fontName="Helvetica", fontSize=6.2, fillColor=MUTED))
    arrow(d, 150, 185, 117, 185)
    arrow(d, 150, 170, 117, 118)
    arrow(d, 320, 190, 353, 190)
    arrow(d, 235, 160, 235, 127)
    return d


def flow_diagram():
    d = Drawing(468, 70)
    steps = ["1 Authenticate", "2 Resolve credential", "3 Policy + budget",
             "4 Route + call", "5 Meter + log"]
    w = 84
    for i, s in enumerate(steps):
        x = 2 + i * (w + 11)
        box(d, x, 18, w, 34, s)
        if i < len(steps) - 1:
            arrow(d, x + w, 35, x + w + 10, 35)
    return d


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    if doc.page > 1:
        canvas.drawString(inch, 0.55 * inch, "BYOK / BYOS Orchestration — Start-to-Deployment Procedure")
        canvas.drawRightString(7.5 * inch, 0.55 * inch, f"Page {doc.page}")
    canvas.restoreState()


# ---------------------------------------------------------------- cover
story += [Spacer(1, 1.6 * inch),
          Paragraph("Bring Your Own Key &amp; Bring Your Own Subscription", title),
          Spacer(1, 8),
          Paragraph("An orchestration architecture for multi-provider LLM access —<br/>"
                    "a start-to-deployment procedure built on free-tier services", subtitle),
          Spacer(1, 0.5 * inch)]
T([["Item", "Value"],
   ["Document type", "Implementation procedure / reference architecture"],
   ["Prepared", "7 November 2026"],
   ["Audience", "Engineers building a SaaS or internal tool that calls LLM providers using "
                "customer-owned credentials"],
   ["Reference stack", "Cloudflare Workers + Pages, Supabase (Postgres + Auth), Upstash Redis, "
                       "GitHub Actions — all on free tiers"],
   ["Code language", "TypeScript (Workers runtime), SQL (Postgres)"]], [1.6, 4.9])
WARN("Free-tier quotas, provider APIs, model identifiers and terms of service change often. "
     "Every number in this document was checked against vendor pages around the preparation date "
     "where noted, and is marked 'approx.' where it was not. Re-check each vendor's current "
     "pricing and limits page before you rely on it. Code samples are illustrative starting points "
     "and have not been run against live provider accounts; test them before production use.")
story.append(PageBreak())

# ---------------------------------------------------------------- contents
H1("Contents")
for line in [
    "1. Scope, definitions and assumptions",
    "2. Requirements and design principles",
    "3. Reference architecture",
    "4. Free-tier service selection",
    "5. Phase 0 — Accounts, repository and tooling",
    "6. Phase 1 — Data model (Supabase Postgres)",
    "7. Phase 2 — Authentication and tenancy",
    "8. Phase 3 — Credential vault (envelope encryption)",
    "9. Phase 4 — BYOK onboarding and key validation",
    "10. Phase 5 — BYOS onboarding (cloud subscriptions)",
    "11. Phase 6 — Provider adapter layer",
    "12. Phase 7 — Orchestrator: resolution, routing, fallback",
    "13. Phase 8 — Rate limiting, budgets and metering",
    "14. Phase 9 — Frontend",
    "15. Phase 10 — Testing",
    "16. Phase 11 — CI/CD and deployment",
    "17. Phase 12 — Operations: observability, rotation, incidents",
    "18. Security checklist",
    "19. Scaling beyond free tiers",
    "20. Go-live checklist",
    "Appendix A — Environment variables and secrets",
    "Appendix B — Open questions to settle for your context",
]:
    story.append(Paragraph(line, ParagraphStyle("toc", parent=body, spaceAfter=2)))
story.append(PageBreak())

# ---------------------------------------------------------------- 1
H1("1. Scope, definitions and assumptions")
P("This procedure describes how to build and deploy an <b>orchestration layer</b> that sits "
  "between your application and one or more large-language-model (LLM) providers, where the "
  "provider credentials belong to your <i>customer</i>, not to you. The orchestrator authenticates "
  "the end user, finds the right customer credential, applies policy, calls the provider, and "
  "records usage — without ever exposing the raw secret to the browser or to logs.")
H2("1.1 Definitions used in this document")
T([["Term", "Meaning here"],
   ["BYOK — Bring Your Own Key",
    "The customer pastes a provider API key (e.g. an OpenAI, Anthropic or Google AI Studio key). "
    "Your platform stores it encrypted and uses it on their behalf. Provider bills the customer."],
   ["BYOS — Bring Your Own Subscription",
    "The customer connects an existing <b>cloud or enterprise subscription</b> they already pay "
    "for — e.g. an AWS account with Bedrock enabled, an Azure subscription with an Azure OpenAI "
    "resource, or a Google Cloud project with Vertex AI. Access is granted by a scoped, revocable "
    "mechanism (cross-account role, endpoint + key, workload identity) rather than a long-lived "
    "personal key where possible. Also covers OAuth-style 'connect your account' flows that a "
    "provider or aggregator explicitly offers to third-party apps."],
   ["Platform credential", "Your own key, used only as an optional fallback or for a free trial."],
   ["Tenant", "An organisation/workspace in your app. Credentials attach to a tenant or a user."],
   ["KEK / DEK", "Key-encryption key (master secret) / data-encryption key (per tenant)."]],
  [1.7, 4.8])
WARN("<b>Consumer chat subscriptions are out of scope.</b> Plans such as ChatGPT Plus or "
     "Claude Pro are consumer products; to my knowledge their terms do not permit reusing them as "
     "an API backend inside a third-party service, and scraping or proxying their web sessions is "
     "very likely a terms-of-service violation. I am not certain of every vendor's current wording, "
     "so read each provider's terms yourself. This document treats BYOS strictly as the "
     "sanctioned routes described above.")
H2("1.2 Assumptions (change these if they do not match your situation)")
B(["You are building a web application (SaaS or internal) with multiple tenants.",
   "You want a zero-cost starting point and accept free-tier limits (cold starts, quotas, "
   "pausing) during development and early usage.",
   "TypeScript on Cloudflare Workers is acceptable for the backend. Section 19 lists "
   "container-based alternatives if you need Python or long-running processes.",
   "You are not yet subject to a specific compliance regime (SOC 2, HIPAA, PCI). If you are, "
   "free tiers are usually unsuitable for production data — see Section 19."])

# ---------------------------------------------------------------- 2
H1("2. Requirements and design principles")
H2("2.1 Functional requirements")
B(["F1. A tenant admin can add, test, rotate and delete BYOK keys per provider.",
   "F2. A tenant admin can connect a cloud subscription (BYOS) for Bedrock, Azure OpenAI or Vertex AI.",
   "F3. Application code calls one internal endpoint (<font face='Courier'>POST /v1/chat</font>) "
   "with a provider-neutral payload; the orchestrator chooses credential and provider.",
   "F4. Credential precedence is configurable: user key &gt; tenant BYOS &gt; tenant BYOK &gt; "
   "platform fallback (if enabled).",
   "F5. Automatic fallback to another provider/credential on rate-limit or server errors, "
   "within tenant policy.",
   "F6. Per-tenant usage metering (tokens, requests, estimated cost) and optional budgets.",
   "F7. Streaming responses (server-sent events) pass through to the client."])
H2("2.2 Non-functional requirements")
B(["N1. Secrets are encrypted at rest with authenticated encryption and never returned to clients "
   "after creation (show only a fingerprint such as the last 4 characters).",
   "N2. Secrets never appear in logs, error messages, analytics or crash reports.",
   "N3. Tenant isolation is enforced in the database (row-level security), not only in code.",
   "N4. Every credential use is auditable (who, when, which credential, which model).",
   "N5. The system degrades gracefully when a free-tier quota is exhausted."])
H2("2.3 Design principles")
B(["<b>Decrypt late, forget early.</b> Decrypt a credential only inside the request that uses it; "
   "never cache plaintext across requests.",
   "<b>Least privilege for BYOS.</b> Ask the customer for a role that can only invoke models, "
   "with an external ID, instead of broad cloud credentials.",
   "<b>Adapters, not conditionals.</b> One adapter per provider behind a common interface keeps "
   "the router simple and testable.",
   "<b>Server-side only.</b> The browser never sees decrypted keys; it only ever talks to your "
   "orchestrator."])

# ---------------------------------------------------------------- 3
story.append(PageBreak())
story.append(KeepTogether([Paragraph("3. Reference architecture", h1), architecture_diagram()]))
story.append(Paragraph("Figure 1 — Components and data flow. Amber = stateful stores; "
                       "green = customer-owned provider accounts.",
                       ParagraphStyle("cap", parent=body, fontSize=8, textColor=MUTED,
                                      alignment=TA_CENTER)))
H2("3.1 Components")
T([["Component", "Responsibility", "Free-tier implementation"],
   ["Client SPA", "Settings UI for keys/subscriptions; chat UI", "Cloudflare Pages"],
   ["Identity", "Sign-up, login, JWT issuance, org membership", "Supabase Auth"],
   ["Orchestrator", "JWT verification, credential resolution, policy, routing, fallback, "
                    "streaming, metering", "Cloudflare Worker"],
   ["Credential vault", "Envelope-encrypt / decrypt secrets; KEK held as a Worker secret",
    "Web Crypto API inside the Worker + ciphertext in Postgres"],
   ["Relational store", "Tenants, members, credential metadata + ciphertext, usage, audit",
    "Supabase Postgres"],
   ["Rate limiter / counters", "Per-tenant request limits, short-lived counters",
    "Upstash Redis (or Workers KV for coarse limits)"],
   ["Provider adapters", "Translate neutral request to OpenAI / Anthropic / Gemini / Bedrock / "
                         "Azure OpenAI / Vertex formats", "Code inside the Worker"],
   ["CI/CD", "Tests, migrations, deploy", "GitHub Actions"]], [1.3, 3.0, 2.2])
story.append(KeepTogether([Paragraph("3.2 Request lifecycle", h2), flow_diagram()]))
B(["<b>Authenticate</b> — verify the Supabase JWT; load the user's tenant and role.",
   "<b>Resolve credential</b> — apply precedence rules (F4) to pick a credential record that "
   "supports the requested model family.",
   "<b>Policy + budget</b> — check model allow-list, rate limit and monthly budget.",
   "<b>Route + call</b> — decrypt the secret, call the provider via its adapter, stream back; on "
   "429/5xx try the next eligible credential.",
   "<b>Meter + log</b> — record tokens, latency, status and credential ID (never the secret)."],
  numbered=True)

# ---------------------------------------------------------------- 4
H1("4. Free-tier service selection")
P("The table summarises the free tiers this design relies on. Figures were checked on or around "
  "the preparation date against vendor documentation where marked <b>(checked)</b>; others are "
  "from my general knowledge and marked <b>approx.</b> — confirm them before you plan capacity.")
T([["Service", "Role", "Free-tier highlights", "Caveats"],
   ["Cloudflare Workers", "Orchestrator",
    "100,000 requests/day; 10 ms CPU per request (time waiting on fetch/IO does not count) "
    "<b>(checked)</b>",
    "Limits reset daily 00:00 UTC; over-quota requests fail. Heavy JSON work can hit the CPU cap."],
   ["Workers KV", "Coarse counters, config cache",
    "100,000 reads/day, 1,000 writes/day, ~1 GB storage <b>(checked)</b>",
    "Eventually consistent — not suitable for exact rate limits or secrets of record."],
   ["Cloudflare Pages", "Frontend hosting",
    "Static hosting with generous bandwidth (approx.; build-minute caps apply)",
    "Verify current build limits."],
   ["Supabase", "Postgres + Auth",
    "500 MB database per project; 2 active projects <b>(checked)</b>",
    "Free projects pause after ~1 week of inactivity and must be restored manually."],
   ["Upstash Redis", "Rate limiting",
    "Approx. 500K commands/month and 256 MB (sources conflicted)",
    "Older docs said 10K commands/day — confirm on Upstash pricing page."],
   ["GitHub Actions", "CI/CD",
    "Free for public repos; a monthly minute allowance for private repos (approx.)",
    "Verify current minute allowance for your account type."],
   ["Render (alternative)", "Container backend",
    "750 free instance-hours/month per workspace; spins down after 15 min idle, ~1 min wake "
    "<b>(checked)</b>", "Cold starts hurt interactive latency."],
   ["Google Cloud Run (alt.)", "Container backend",
    "Monthly free request/CPU allowance (approx. 2M requests/month)",
    "Requires a billing account; verify current free allowance."],
   ["Oracle Cloud Always Free (alt.)", "Self-managed VM",
    "Arm VM capacity in the Always Free tier (approx. up to 4 OCPU / 24 GB)",
    "Capacity availability varies by region; you run the OS and patches."]],
  [1.15, 1.0, 2.35, 2.0])
BOX("Vercel's Hobby plan is free but, as far as I know, restricted to non-commercial use; check "
    "its current terms before using it for a commercial product. Fly.io ended its general free "
    "allowance for new organisations in 2024 to my knowledge — verify before choosing it.")
H2("4.1 Why Workers for the orchestrator")
B(["The orchestrator is I/O-bound: most wall-clock time is spent waiting on the LLM provider, "
   "which does not count toward the Workers CPU limit.",
   "No cold-start sleep like free container platforms; global edge placement.",
   "Built-in Web Crypto for AES-GCM, and first-class secrets via <font face='Courier'>wrangler "
   "secret put</font>.",
   "Streaming responses are supported through standard <font face='Courier'>ReadableStream</font>."])

# ---------------------------------------------------------------- 5
H1("5. Phase 0 — Accounts, repository and tooling")
H2("5.1 Create accounts")
B(["Cloudflare (Workers + Pages), Supabase, Upstash, GitHub.",
   "Enable MFA on every account; these accounts guard your customers' keys.",
   "Create separate <b>staging</b> and <b>production</b> Supabase projects (the free tier allows "
   "two active projects)."], numbered=True)
H2("5.2 Repository layout")
C("""
byok-orchestrator/
  apps/
    web/                 # SPA (Vite + React or similar) -> Cloudflare Pages
    orchestrator/        # Cloudflare Worker (TypeScript)
      src/
        index.ts         # router / entry
        auth.ts          # JWT verification
        vault.ts         # envelope encryption
        resolve.ts       # credential resolution
        adapters/        # openai.ts, anthropic.ts, gemini.ts, bedrock.ts, azure.ts
        meter.ts         # usage + audit
        ratelimit.ts
      wrangler.toml
  supabase/
    migrations/          # SQL migrations (schema + RLS)
  .github/workflows/     # CI + deploy
""")
H2("5.3 Bootstrap the Worker")
C("""
npm create cloudflare@latest apps/orchestrator   # choose "Hello World" Worker, TypeScript
cd apps/orchestrator
npm install jose @upstash/redis @upstash/ratelimit aws4fetch
npx wrangler login
""")
P("<font face='Courier'>jose</font> verifies JWTs, <font face='Courier'>@upstash/ratelimit</font> "
  "implements sliding-window limits, and <font face='Courier'>aws4fetch</font> signs AWS SigV4 "
  "requests for Bedrock/STS in a fetch-based runtime. Check each package's README for its "
  "current API before use.")
H2("5.4 Minimal wrangler.toml")
C("""
name = "byok-orchestrator"
main = "src/index.ts"
compatibility_date = "2026-10-01"     # set to the date you start; see Cloudflare docs

[vars]
SUPABASE_URL = "https://<project-ref>.supabase.co"
ALLOWED_ORIGIN = "https://app.example.com"

# Secrets (set with `npx wrangler secret put NAME`, never committed):
#   KEK_V1                    base64 32-byte master key
#   SUPABASE_SERVICE_ROLE_KEY server-only DB key
#   UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN
#   PLATFORM_FALLBACK_KEY     optional
""")

# ---------------------------------------------------------------- 6
H1("6. Phase 1 — Data model (Supabase Postgres)")
P("Create a migration under <font face='Courier'>supabase/migrations/</font> and apply it with "
  "the Supabase CLI (<font face='Courier'>supabase db push</font>) or the SQL editor.")
C("""
create table tenants (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  policy      jsonb not null default '{"precedence":["user","byos","byok","platform"],
                                        "allow_platform_fallback": false}',
  monthly_budget_usd numeric,
  created_at  timestamptz not null default now()
);

create table memberships (
  tenant_id uuid references tenants(id) on delete cascade,
  user_id   uuid references auth.users(id) on delete cascade,
  role      text not null check (role in ('owner','admin','member')),
  primary key (tenant_id, user_id)
);

create table credentials (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null references tenants(id) on delete cascade,
  owner_user   uuid references auth.users(id),          -- null = tenant-wide
  kind         text not null check (kind in ('byok','byos')),
  provider     text not null,   -- openai | anthropic | gemini | bedrock | azure_openai | vertex
  label        text,
  config       jsonb not null default '{}',  -- non-secret: region, endpoint, role ARN, models
  ciphertext   bytea not null,  -- AES-GCM(secret JSON)
  iv           bytea not null,
  wrapped_dek  bytea not null,  -- DEK encrypted under KEK
  kek_version  int  not null default 1,
  fingerprint  text not null,   -- e.g. 'sk-...a1b2'
  status       text not null default 'active' check (status in ('active','invalid','revoked')),
  last_validated_at timestamptz,
  created_at   timestamptz not null default now()
);

create table usage_events (
  id            bigserial primary key,
  tenant_id     uuid not null references tenants(id) on delete cascade,
  user_id       uuid,
  credential_id uuid references credentials(id) on delete set null,
  provider      text, model text,
  input_tokens  int, output_tokens int,
  est_cost_usd  numeric, latency_ms int, status int,
  created_at    timestamptz not null default now()
);

create table audit_log (
  id bigserial primary key, tenant_id uuid, actor uuid,
  action text not null, target uuid, meta jsonb, at timestamptz default now()
);
""")
H2("6.1 Row-level security")
P("The Worker uses the service-role key (which bypasses RLS), but RLS still protects any direct "
  "client access through the Supabase JS client. Critically, the client must never be able to "
  "read <font face='Courier'>ciphertext</font> or <font face='Courier'>wrapped_dek</font>.")
C("""
alter table credentials  enable row level security;
alter table usage_events enable row level security;
alter table memberships  enable row level security;

-- Members may see their own memberships
create policy own_memberships on memberships for select
  using (user_id = auth.uid());

-- Expose credential METADATA only, through a view without secret columns
create view credential_public with (security_invoker = true) as
  select id, tenant_id, kind, provider, label, config, fingerprint, status,
         last_validated_at, created_at
  from credentials;

create policy members_read_creds on credentials for select
  using (tenant_id in (select tenant_id from memberships where user_id = auth.uid()));

-- No insert/update/delete policies for clients: all writes go through the Worker.
revoke select (ciphertext, iv, wrapped_dek) on credentials from anon, authenticated;
""")
WARN("Column-level REVOKE combined with RLS and views has subtle behaviour in PostgreSQL; test "
     "with the <font face='Courier'>authenticated</font> role that a client query for "
     "<font face='Courier'>ciphertext</font> fails. The simplest safe option is to deny all "
     "client access to <font face='Courier'>credentials</font> and serve metadata only via the "
     "Worker.")

# ---------------------------------------------------------------- 7
H1("7. Phase 2 — Authentication and tenancy")
P("The SPA signs users in with Supabase Auth and sends the access token as "
  "<font face='Courier'>Authorization: Bearer &lt;jwt&gt;</font> to the Worker. The Worker "
  "verifies it locally against the project's JWKS.")
C("""
// src/auth.ts
import { createRemoteJWKSet, jwtVerify } from "jose";

let jwks: ReturnType<typeof createRemoteJWKSet> | undefined;

export async function authenticate(req: Request, env: Env) {
  const token = req.headers.get("Authorization")?.replace(/^Bearer\\s+/i, "");
  if (!token) throw new HttpError(401, "missing token");
  jwks ??= createRemoteJWKSet(new URL(`${env.SUPABASE_URL}/auth/v1/.well-known/jwks.json`));
  const { payload } = await jwtVerify(token, jwks, {
    issuer: `${env.SUPABASE_URL}/auth/v1`,
    audience: "authenticated",
  });
  const tenantId = req.headers.get("X-Tenant-Id");
  const role = await db.membershipRole(env, tenantId, payload.sub!);   // query memberships
  if (!role) throw new HttpError(403, "not a member of tenant");
  return { userId: payload.sub!, tenantId: tenantId!, role };
}
""")
WARN("Supabase has used both symmetric (HS256 shared secret) and asymmetric (JWKS) JWT signing; "
     "which one your project uses depends on its settings and creation date. Confirm the JWKS URL "
     "and issuer in your project's Auth settings, or verify with the legacy JWT secret if your "
     "project still uses HS256.")

# ---------------------------------------------------------------- 8
H1("8. Phase 3 — Credential vault (envelope encryption)")
P("Each credential secret is encrypted with a random 256-bit <b>DEK</b> using AES-256-GCM. The "
  "DEK itself is encrypted (\"wrapped\") with the <b>KEK</b>, which exists only as a Worker "
  "secret. A database leak alone therefore yields no usable keys. Storing "
  "<font face='Courier'>kek_version</font> lets you rotate the KEK without downtime.")
C("""
// src/vault.ts  — uses only the standard Web Crypto API available in Workers
const b64 = (s: string) => Uint8Array.from(atob(s), c => c.charCodeAt(0));

async function kek(env: Env, version: number): Promise<CryptoKey> {
  const raw = b64((env as any)[`KEK_V${version}`]);
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
}

export async function seal(env: Env, secret: object, aad: string) {
  const dekRaw = crypto.getRandomValues(new Uint8Array(32));
  const dek = await crypto.subtle.importKey("raw", dekRaw, "AES-GCM", false, ["encrypt"]);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ad = new TextEncoder().encode(aad);            // bind to tenant+credential id
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: ad }, dek,
               new TextEncoder().encode(JSON.stringify(secret)));
  const wiv = crypto.getRandomValues(new Uint8Array(12));
  const wrapped = await crypto.subtle.encrypt({ name: "AES-GCM", iv: wiv },
               await kek(env, env.KEK_CURRENT_VERSION), dekRaw);
  return { ciphertext: new Uint8Array(ct), iv,
           wrapped_dek: concat(wiv, new Uint8Array(wrapped)),
           kek_version: env.KEK_CURRENT_VERSION };
}

export async function open(env: Env, rec: SealedRecord, aad: string) {
  const wiv = rec.wrapped_dek.slice(0, 12), wct = rec.wrapped_dek.slice(12);
  const dekRaw = await crypto.subtle.decrypt({ name: "AES-GCM", iv: wiv },
               await kek(env, rec.kek_version), wct);
  const dek = await crypto.subtle.importKey("raw", dekRaw, "AES-GCM", false, ["decrypt"]);
  const pt = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: rec.iv, additionalData: new TextEncoder().encode(aad) },
      dek, rec.ciphertext);
  return JSON.parse(new TextDecoder().decode(pt));
}
""")
H2("8.1 Generate and install the KEK")
C("""
openssl rand -base64 32 | npx wrangler secret put KEK_V1
# also add KEK_CURRENT_VERSION = "1" (as a var or secret)
""")
B(["Store an offline backup of the KEK in a password manager or hardware-backed vault. "
   "<b>If the KEK is lost, every stored credential is unrecoverable.</b>",
   "Use a different KEK for staging and production.",
   "Use additional authenticated data (AAD) = <font face='Courier'>tenant_id:credential_id</font> "
   "so a ciphertext copied into another tenant's row fails to decrypt.",
   "Upgrade path: replace the Worker-secret KEK with a managed KMS (AWS KMS, GCP KMS, HashiCorp "
   "Vault) when you leave free tiers."])

# ---------------------------------------------------------------- 9
H1("9. Phase 4 — BYOK onboarding and key validation")
H2("9.1 Flow")
B(["Admin opens Settings &gt; AI Providers &gt; Add key; selects provider; pastes key over HTTPS.",
   "Worker validates the key with a cheap, read-only provider call (list models).",
   "On success: seal, insert row, write audit event, return only metadata + fingerprint.",
   "The plaintext key is dropped from memory at the end of the request; the UI never shows it again."],
  numbered=True)
H2("9.2 Validation endpoints")
T([["Provider", "Validation call", "Auth header"],
   ["OpenAI", "GET https://api.openai.com/v1/models", "Authorization: Bearer &lt;key&gt;"],
   ["Anthropic", "GET https://api.anthropic.com/v1/models",
    "x-api-key: &lt;key&gt;; anthropic-version: 2023-06-01"],
   ["Google Gemini (AI Studio)", "GET https://generativelanguage.googleapis.com/v1beta/models",
    "x-goog-api-key: &lt;key&gt;"],
   ["OpenRouter (aggregator)", "Check its docs for a key-info endpoint", "Authorization: Bearer"]],
  [1.5, 3.0, 2.0])
WARN("Endpoint paths and header names above are correct to the best of my knowledge but providers "
     "do change them — confirm against each provider's current API reference.")
C("""
// src/routes/credentials.ts (excerpt)
export async function addByok(req: Request, env: Env, ctx: AuthCtx) {
  requireRole(ctx, ["owner", "admin"]);
  const { provider, apiKey, label } = await req.json<AddKeyBody>();
  if (!VALIDATORS[provider]) throw new HttpError(400, "unsupported provider");
  const ok = await VALIDATORS[provider](apiKey);        // list-models call
  if (!ok) throw new HttpError(422, "key rejected by provider");
  const id = crypto.randomUUID();
  const sealed = await seal(env, { apiKey }, `${ctx.tenantId}:${id}`);
  await db.insertCredential(env, { id, tenant_id: ctx.tenantId, kind: "byok", provider,
    label, ...sealed, fingerprint: `${apiKey.slice(0, 3)}...${apiKey.slice(-4)}`,
    last_validated_at: new Date().toISOString() });
  await audit(env, ctx, "credential.create", id, { provider });
  return json({ id, provider, label, status: "active" }, 201);
}
""")

# ---------------------------------------------------------------- 10
H1("10. Phase 5 — BYOS onboarding (cloud subscriptions)")
P("BYOS lets enterprises keep spend, data-residency and quota inside their own cloud agreement. "
  "Prefer mechanisms that are <b>scoped, revocable, and short-lived</b>.")
H2("10.1 AWS Bedrock — cross-account IAM role (recommended pattern)")
B(["Your platform owns one AWS IAM user (or, better, a role reachable via OIDC) whose only "
   "permission is <font face='Courier'>sts:AssumeRole</font>. Store its credentials as Worker "
   "secrets.",
   "Generate a unique <b>external ID</b> per tenant and show it in the onboarding screen.",
   "The customer creates a role in <i>their</i> account that trusts your principal with that "
   "external ID and grants only Bedrock invoke permissions on the models they choose.",
   "The customer pastes the role ARN and region; you call STS AssumeRole to test, then store "
   "ARN + region + external ID in <font face='Courier'>config</font> (the external ID is not a "
   "secret but treat it carefully).",
   "Per request: AssumeRole (cache the temporary credentials for less than their expiry), then "
   "SigV4-sign the Bedrock runtime call."], numbered=True)
C("""
// Customer-side trust policy (they create this in their AWS account)
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "AWS": "arn:aws:iam::<YOUR_ACCOUNT_ID>:user/byok-orchestrator" },
    "Action": "sts:AssumeRole",
    "Condition": { "StringEquals": { "sts:ExternalId": "<TENANT_EXTERNAL_ID>" } }
  }]
}
// Customer-side permissions policy (scope Resource to specific model ARNs if desired)
{ "Version": "2012-10-17",
  "Statement": [{ "Effect": "Allow",
    "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
    "Resource": "*" }] }
""")
C("""
// src/adapters/bedrock.ts (excerpt) — aws4fetch signs requests with SigV4
import { AwsClient } from "aws4fetch";

async function assume(env: Env, cfg: BedrockCfg) {
  const sts = new AwsClient({ accessKeyId: env.AWS_PLATFORM_KEY_ID,
    secretAccessKey: env.AWS_PLATFORM_SECRET, service: "sts", region: cfg.region });
  const url = `https://sts.${cfg.region}.amazonaws.com/?Action=AssumeRole&Version=2011-06-15` +
    `&RoleArn=${encodeURIComponent(cfg.roleArn)}&RoleSessionName=byok-${cfg.tenantId}` +
    `&ExternalId=${encodeURIComponent(cfg.externalId)}&DurationSeconds=900`;
  const res = await sts.fetch(url);
  return parseAssumeRoleXml(await res.text());   // AccessKeyId, SecretAccessKey, SessionToken
}
// Then call https://bedrock-runtime.<region>.amazonaws.com/model/<modelId>/converse
// with a new AwsClient({ ...tempCreds, sessionToken, service: "bedrock" }).
""")
WARN("The Bedrock Converse endpoint path, STS query parameters, and aws4fetch constructor options "
     "are given from memory; confirm them in the AWS Bedrock Runtime API reference, the STS "
     "AssumeRole reference, and the aws4fetch README.")
H2("10.2 Azure OpenAI — customer resource endpoint")
B(["Customer supplies the resource endpoint, deployment name(s), API version and either an API "
   "key or (preferred, more work) a Microsoft Entra ID app registration they grant the "
   "'Cognitive Services OpenAI User' role (role name to be verified).",
   "Store the endpoint/deployments in <font face='Courier'>config</font>; seal the key or client "
   "secret in the vault.",
   "Validate by calling a cheap endpoint on the customer's resource."])
H2("10.3 Google Vertex AI — service account or workload identity federation")
B(["Simplest: customer creates a service account with Vertex AI user permissions and uploads a "
   "JSON key; you seal the whole JSON. Many organisations block key creation by policy.",
   "Better: Workload Identity Federation, where Google trusts an identity token you issue, "
   "avoiding long-lived keys. This needs an OIDC issuer you control — more setup; verify Google's "
   "current guidance.",
   "In a Worker you must mint an OAuth access token from the service-account key yourself "
   "(sign a JWT with RS256 via Web Crypto, exchange it at Google's token endpoint)."])
H2("10.4 Aggregator OAuth (\"connect your account\")")
P("Some aggregators (OpenRouter is one I believe offers this — verify) provide an OAuth/PKCE flow "
  "that returns a user-scoped key to your app. Treat the returned key exactly like a BYOK key: "
  "seal it, fingerprint it, and allow the user to revoke it.")

# ---------------------------------------------------------------- 11
H1("11. Phase 6 — Provider adapter layer")
P("Define one neutral request/response shape and implement it once per provider. The router "
  "never contains provider-specific code.")
C("""
// src/adapters/types.ts
export interface ChatRequest {
  model: string;                 // logical name, e.g. "fast" | "smart" or a concrete id
  messages: { role: "system" | "user" | "assistant"; content: string }[];
  maxTokens?: number; temperature?: number; stream?: boolean;
}
export interface ChatResult {
  stream?: ReadableStream<Uint8Array>; text?: string;
  usage?: { inputTokens: number; outputTokens: number };
  status: number; retryable: boolean;
}
export interface Adapter {
  provider: string;
  supports(model: string): boolean;
  call(req: ChatRequest, secret: any, cfg: any, signal: AbortSignal): Promise<ChatResult>;
}
""")
C("""
// src/adapters/anthropic.ts (non-streaming excerpt)
export const anthropic: Adapter = {
  provider: "anthropic",
  supports: m => m.startsWith("claude-"),
  async call(req, secret, _cfg, signal) {
    const system = req.messages.filter(m => m.role === "system").map(m => m.content).join("\\n");
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST", signal,
      headers: { "x-api-key": secret.apiKey, "anthropic-version": "2023-06-01",
                 "content-type": "application/json" },
      body: JSON.stringify({ model: req.model, max_tokens: req.maxTokens ?? 1024,
        system: system || undefined,
        messages: req.messages.filter(m => m.role !== "system") }),
    });
    const retryable = res.status === 429 || res.status >= 500;
    if (!res.ok) return { status: res.status, retryable };
    const j: any = await res.json();
    return { status: 200, retryable: false,
      text: j.content?.map((b: any) => b.text ?? "").join(""),
      usage: { inputTokens: j.usage?.input_tokens, outputTokens: j.usage?.output_tokens } };
  },
};
""")
C("""
// src/adapters/openai.ts (non-streaming excerpt)
export const openai: Adapter = {
  provider: "openai",
  supports: m => /^(gpt-|o\\d)/.test(m),
  async call(req, secret, _cfg, signal) {
    const res = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST", signal,
      headers: { Authorization: `Bearer ${secret.apiKey}`, "content-type": "application/json" },
      body: JSON.stringify({ model: req.model, messages: req.messages,
                             max_tokens: req.maxTokens, temperature: req.temperature }),
    });
    const retryable = res.status === 429 || res.status >= 500;
    if (!res.ok) return { status: res.status, retryable };
    const j: any = await res.json();
    return { status: 200, retryable: false, text: j.choices?.[0]?.message?.content,
      usage: { inputTokens: j.usage?.prompt_tokens, outputTokens: j.usage?.completion_tokens } };
  },
};
""")
WARN("Request/response field names reflect these providers' public APIs as I know them; OpenAI in "
     "particular also offers a newer Responses API and some models reject "
     "<font face='Courier'>max_tokens</font> in favour of another parameter. Model identifiers "
     "change frequently — keep them in configuration, not code, and confirm current IDs in each "
     "provider's model list.")
H2("11.1 Streaming")
P("For <font face='Courier'>stream: true</font>, request the provider's SSE stream and pipe it "
  "through a <font face='Courier'>TransformStream</font> that (a) normalises events into one "
  "format for your client, and (b) captures the final usage event for metering. Return "
  "<font face='Courier'>new Response(readable, { headers: { 'content-type': "
  "'text/event-stream' } })</font>. Use <font face='Courier'>ctx.waitUntil()</font> to write "
  "usage after the stream completes.")
H2("11.2 Logical model aliases")
P("Let tenants map aliases (<font face='Courier'>fast</font>, <font face='Courier'>smart</font>, "
  "<font face='Courier'>cheap</font>) to concrete model IDs per provider in "
  "<font face='Courier'>tenants.policy</font>. This makes fallback across providers possible "
  "without the application knowing provider-specific names.")

# ---------------------------------------------------------------- 12
H1("12. Phase 7 — Orchestrator: resolution, routing, fallback")
C("""
// src/resolve.ts
export async function candidates(env: Env, ctx: AuthCtx, req: ChatRequest) {
  const tenant = await db.tenant(env, ctx.tenantId);
  const creds = await db.activeCredentials(env, ctx.tenantId);    // includes sealed fields
  const order: string[] = tenant.policy.precedence;              // ["user","byos","byok",...]
  const ranked = [];
  for (const tier of order) {
    for (const c of creds) {
      const tierOf = c.owner_user ? "user" : c.kind;              // user | byos | byok
      if (tierOf !== tier) continue;
      if (tier === "user" && c.owner_user !== ctx.userId) continue;
      const model = resolveAlias(tenant.policy, req.model, c.provider);
      if (model && ADAPTERS[c.provider].supports(model)) ranked.push({ cred: c, model });
    }
  }
  if (tenant.policy.allow_platform_fallback && env.PLATFORM_FALLBACK_KEY)
    ranked.push(platformCandidate(env, tenant, req));
  return ranked;
}
""")
C("""
// src/index.ts — core handler (simplified)
export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext) {
    if (req.method === "OPTIONS") return cors(env, new Response(null, { status: 204 }));
    try {
      const auth = await authenticate(req, env);
      const url = new URL(req.url);
      if (url.pathname === "/v1/chat" && req.method === "POST") {
        const body = await req.json<ChatRequest>();
        await enforceLimits(env, auth);                       // rate limit + budget
        const list = await candidates(env, auth, body);
        if (!list.length) throw new HttpError(409, "no credential configured for this model");
        for (const { cred, model } of list.slice(0, 3)) {     // cap fallback attempts
          const secret = await open(env, cred, `${cred.tenant_id}:${cred.id}`);
          const t0 = Date.now();
          const r = await ADAPTERS[cred.provider].call({ ...body, model }, secret, cred.config,
                      AbortSignal.timeout(60_000));
          ctx.waitUntil(meter(env, auth, cred, model, r, Date.now() - t0));
          if (r.status === 401 || r.status === 403) ctx.waitUntil(markInvalid(env, cred.id));
          if (r.status === 200) return cors(env, respond(r));
          if (!r.retryable) return cors(env, json({ error: "provider_error",
                                                     status: r.status }, 502));
        }
        return cors(env, json({ error: "all_candidates_failed" }, 503));
      }
      return routeAdmin(req, env, auth);                       // credential CRUD etc.
    } catch (e) { return cors(env, errorResponse(e)); }       // never echo secrets
  },
};
""")
H2("12.1 Routing rules worth implementing")
B(["<b>Fail closed on auth errors:</b> a 401/403 from a provider marks the credential "
   "<font face='Courier'>invalid</font> and notifies the tenant admin — do not silently fall back "
   "to the platform key, or you will pay for their usage.",
   "<b>Retry only idempotent failures:</b> 429, 500, 502, 503, 504, and network timeouts.",
   "<b>Respect Retry-After</b> when present, but do not block a Worker for long; prefer moving "
   "to the next candidate.",
   "<b>Data-residency pinning:</b> a tenant policy flag can restrict candidates to BYOS "
   "credentials in specific regions.",
   "<b>No fallback mid-stream:</b> once bytes have been streamed to the client, a failure must "
   "surface as an error event rather than a silent provider switch."])

# ---------------------------------------------------------------- 13
H1("13. Phase 8 — Rate limiting, budgets and metering")
C("""
// src/ratelimit.ts
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis/cloudflare";

export async function enforceLimits(env: Env, auth: AuthCtx) {
  const rl = new Ratelimit({
    redis: Redis.fromEnv(env),                         // reads UPSTASH_REDIS_REST_URL/TOKEN
    limiter: Ratelimit.slidingWindow(60, "1 m"),       // 60 req / minute / tenant
    prefix: "rl",
  });
  const { success } = await rl.limit(`tenant:${auth.tenantId}`);
  if (!success) throw new HttpError(429, "tenant rate limit");
  if (await overBudget(env, auth.tenantId)) throw new HttpError(402, "monthly budget reached");
}
""")
B(["<b>Cost estimate</b> = tokens x a price table you maintain in config (prices change; "
   "store the table with an effective date). For BYOK/BYOS the provider bills the customer, so "
   "the estimate is informational unless you resell.",
   "<b>Budget check</b>: keep a running month-to-date total in Redis "
   "(<font face='Courier'>INCRBYFLOAT</font>) updated in <font face='Courier'>waitUntil</font>; "
   "reconcile nightly from <font face='Courier'>usage_events</font>.",
   "<b>Quota awareness</b>: at roughly 100K Worker requests/day and ~500K Upstash commands/month "
   "(approx.), one rate-limit check per request would consume the Upstash allowance before the "
   "Worker allowance at sustained load — budget commands accordingly or batch checks."])
H2("13.1 Data retention")
P("The Supabase free database is 500 MB. A usage row is small (very roughly a few hundred bytes "
  "including indexes — measure yours), so millions of rows will approach the cap. Schedule a job "
  "(GitHub Actions cron or a Workers Cron Trigger) to roll up rows older than N days into daily "
  "aggregates and delete the raw rows. Do <b>not</b> store prompts or completions by default.")

# ---------------------------------------------------------------- 14
H1("14. Phase 9 — Frontend")
B(["Settings &gt; AI Providers page lists credentials from the Worker's metadata endpoint "
   "(provider, label, fingerprint, status, last validated).",
   "Add-key form: password-type input, <font face='Courier'>autocomplete=\"off\"</font>, submit "
   "directly to the Worker; clear the field from state after submit.",
   "BYOS wizard per provider: shows your AWS account ID and the tenant's external ID, "
   "copyable policy JSON, and a 'Test connection' button.",
   "Precedence and fallback toggles mapped to <font face='Courier'>tenants.policy</font>.",
   "Usage dashboard reading aggregated usage from the Worker.",
   "Content-Security-Policy restricting <font face='Courier'>connect-src</font> to your Worker and "
   "Supabase domains; no third-party scripts on the settings page."])
C("""
# Deploy SPA to Cloudflare Pages
cd apps/web && npm run build
npx wrangler pages deploy dist --project-name byok-web
""")

# ---------------------------------------------------------------- 15
H1("15. Phase 10 — Testing")
T([["Layer", "What to test", "How"],
   ["Vault", "Round-trip; wrong AAD fails; wrong KEK version fails; tampered ciphertext fails",
    "Unit tests with Vitest (Cloudflare provides a Workers Vitest integration — verify setup)"],
   ["Adapters", "Request mapping; error classification (401 vs 429 vs 500); usage parsing",
    "Mock fetch with recorded fixtures; no live keys in CI"],
   ["Resolver", "Precedence ordering; user-scoped keys not visible to other users; alias mapping",
    "Table-driven unit tests"],
   ["RLS", "Client cannot read ciphertext or other tenants' rows",
    "SQL tests against a local Supabase (supabase start) using the authenticated role"],
   ["Logging", "No secret in logs", "Test that greps captured logs for a canary key string"],
   ["End-to-end", "Add key, chat, rotate, revoke", "Playwright against staging with test keys "
                                                   "you own and spend caps set at the provider"],
   ["Load", "Behaviour at quota exhaustion", "Small k6/autocannon run against staging; confirm "
                                               "graceful 429/503 rather than 500"]],
  [0.9, 2.9, 2.7])

# ---------------------------------------------------------------- 16
H1("16. Phase 11 — CI/CD and deployment")
H2("16.1 Secrets setup (once per environment)")
C("""
npx wrangler secret put KEK_V1                     --env production
npx wrangler secret put SUPABASE_SERVICE_ROLE_KEY  --env production
npx wrangler secret put UPSTASH_REDIS_REST_URL     --env production
npx wrangler secret put UPSTASH_REDIS_REST_TOKEN   --env production
npx wrangler secret put AWS_PLATFORM_KEY_ID        --env production   # only if using Bedrock BYOS
npx wrangler secret put AWS_PLATFORM_SECRET        --env production
""")
P("In GitHub: add repository secrets <font face='Courier'>CLOUDFLARE_API_TOKEN</font> (scoped to "
  "Workers/Pages edit for one account), <font face='Courier'>CLOUDFLARE_ACCOUNT_ID</font>, and "
  "<font face='Courier'>SUPABASE_ACCESS_TOKEN</font> / DB password for migrations. Use GitHub "
  "Environments with required reviewers for production.")
H2("16.2 Workflow")
C("""
# .github/workflows/deploy.yml
name: deploy
on:
  push: { branches: [main] }
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - run: npm ci && npm test --workspaces
  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      - uses: supabase/setup-cli@v1
      - run: supabase link --project-ref ${{ secrets.SUPABASE_PROJECT_REF }}
             && supabase db push
        env:
          SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
          SUPABASE_DB_PASSWORD: ${{ secrets.SUPABASE_DB_PASSWORD }}
      - uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          workingDirectory: apps/orchestrator
          command: deploy --env production
""")
WARN("Action versions and inputs (<font face='Courier'>cloudflare/wrangler-action</font>, "
     "<font face='Courier'>supabase/setup-cli</font>) should be checked against their READMEs "
     "and pinned to a commit SHA for supply-chain safety.")
H2("16.3 Deployment procedure")
B(["Merge to <font face='Courier'>main</font> after tests pass on the pull request.",
   "Pipeline applies database migrations first (they must be backward-compatible with the "
   "currently running Worker).",
   "Pipeline deploys the Worker; Cloudflare switches traffic to the new version.",
   "Deploy the SPA to Pages (separate job or Pages Git integration).",
   "Smoke test: health endpoint, sign in, add a test key, run one chat, check a usage row exists.",
   "Rollback: <font face='Courier'>npx wrangler rollback</font> (verify the command for your "
   "Wrangler version) or redeploy the previous commit; database migrations should be "
   "forward-only with expand/contract steps."], numbered=True)
H2("16.4 Custom domain and TLS")
P("Attach <font face='Courier'>api.example.com</font> to the Worker and "
  "<font face='Courier'>app.example.com</font> to Pages in the Cloudflare dashboard; TLS "
  "certificates are issued automatically when the domain's DNS is on Cloudflare. Set "
  "<font face='Courier'>ALLOWED_ORIGIN</font> to the app origin for CORS.")

# ---------------------------------------------------------------- 17
H1("17. Phase 12 — Operations")
H2("17.1 Observability")
B(["Enable Workers Logs / observability in <font face='Courier'>wrangler.toml</font> and use "
   "<font face='Courier'>npx wrangler tail</font> for live debugging.",
   "Structured log fields: request ID, tenant ID, credential ID, provider, model, status, latency. "
   "Never the key, prompt or completion.",
   "A redaction helper that strips anything matching key patterns "
   "(<font face='Courier'>sk-</font>, <font face='Courier'>AKIA</font>, long base64 strings) "
   "before logging errors.",
   "Optional free-tier error tracking (e.g. Sentry's free developer plan — verify limits) with "
   "request bodies disabled."])
H2("17.2 Keep-alive for free tiers")
P("Supabase free projects pause after about a week without activity. A scheduled GitHub Action "
  "or Workers Cron Trigger that performs a trivial authenticated query every few days prevents "
  "this. Check whether Supabase's terms permit this for your use; upgrading is the robust fix.")
H2("17.3 Rotation")
T([["What", "Procedure"],
   ["Customer key (BYOK)", "Customer adds new key, tests it, sets it active, deletes old. Offer "
    "periodic re-validation (daily cron calling list-models) and alert on failure."],
   ["KEK", "Add KEK_V2; set KEK_CURRENT_VERSION=2; run a batch job that unwraps each DEK with V1 "
    "and re-wraps with V2 (ciphertext itself is unchanged); when no rows use V1, delete KEK_V1."],
   ["Platform AWS principal", "Create new access key, update secret, deploy, deactivate old key. "
    "Customers' trust policies are unaffected because the principal ARN is unchanged."],
   ["Supabase service-role key", "Rotate in Supabase, update Worker secret, redeploy."]],
  [1.6, 4.9])
H2("17.4 Incident runbook (suspected credential exposure)")
B(["Contain: disable the affected tenant's credentials (status = revoked) via an admin endpoint.",
   "Notify the customer promptly so they revoke the key at the provider — only they can.",
   "If the KEK may be exposed: rotate it immediately (17.3) and ask all tenants to rotate keys.",
   "Review audit_log and usage_events for anomalous use; preserve logs.",
   "Meet any contractual or legal notification duties applicable to you (seek legal advice; I "
   "cannot determine these for your jurisdiction)."], numbered=True)

# ---------------------------------------------------------------- 18
H1("18. Security checklist")
for item in [
    "KEK only in Worker secrets + offline backup; distinct per environment.",
    "AES-GCM with random 96-bit IVs, never reused; AAD binds ciphertext to tenant and credential.",
    "Plaintext secrets never returned by any API, never logged, never stored in KV or Redis.",
    "Client has no read access to ciphertext columns (tested).",
    "Only owners/admins can create, rotate or delete credentials; all actions audited.",
    "BYOS uses scoped roles with external IDs; no customer root/admin credentials accepted.",
    "Provider 401/403 marks credential invalid; no automatic fallback to platform billing.",
    "CORS restricted to your app origin; CSP on the frontend; HTTPS only.",
    "Request size limits and per-tenant rate limits to prevent abuse of customer keys.",
    "Dependencies pinned; GitHub Actions pinned to SHAs; Dependabot or similar enabled.",
    "Privacy policy and terms disclose that you store and use customer credentials.",
]:
    story.append(Paragraph("[&nbsp;&nbsp;&nbsp;]&nbsp;&nbsp;" + item, body))

# ---------------------------------------------------------------- 19
H1("19. Scaling beyond free tiers")
T([["Pressure point", "Symptom", "Upgrade path"],
   ["Worker request quota", "Errors after ~100K requests/day", "Workers Paid plan"],
   ["Worker CPU limit", "Error 1102 on large payload transforms", "Paid plan (higher CPU limits) "
    "or move heavy transforms off the hot path"],
   ["Supabase pausing / 500 MB", "Project paused; insert failures", "Supabase Pro, or another "
    "managed Postgres"],
   ["KEK in env secret", "Compliance asks for HSM-backed keys", "Cloud KMS / Vault with envelope "
    "encryption; Worker calls KMS to unwrap DEKs"],
   ["Need Python / long jobs", "Agentic workflows exceeding request time", "Container platform "
    "(Cloud Run, Render paid, Fly.io) with a queue; keep the vault logic identical"],
   ["Compliance (SOC 2 etc.)", "Customer security reviews", "Paid tiers with compliance "
    "attestations; formal key-management policy; pen test"]],
  [1.6, 2.2, 2.7])

# ---------------------------------------------------------------- 20
H1("20. Go-live checklist")
for item in [
    "Staging and production fully separated (projects, KEKs, API tokens).",
    "All Section 18 items verified.",
    "Migrations applied; RLS tests passing in CI.",
    "Smoke test passed on production with an owned test key; test key then removed.",
    "Monitoring and alerting for 5xx rate, quota exhaustion and invalid-credential spikes.",
    "Keep-alive or paid plan in place for any component that pauses.",
    "Rollback rehearsed once on staging.",
    "Runbook (17.4) shared with whoever is on call.",
    "Free-tier limits in Section 4 re-checked against vendor pages on launch day.",
]:
    story.append(Paragraph("[&nbsp;&nbsp;&nbsp;]&nbsp;&nbsp;" + item, body))

# ---------------------------------------------------------------- appendices
H1("Appendix A — Environment variables and secrets")
T([["Name", "Type", "Where", "Purpose"],
   ["SUPABASE_URL", "var", "Worker", "Project base URL"],
   ["SUPABASE_SERVICE_ROLE_KEY", "secret", "Worker", "Server-side DB access (bypasses RLS)"],
   ["KEK_V1 .. KEK_Vn", "secret", "Worker", "Master key(s) for wrapping DEKs"],
   ["KEK_CURRENT_VERSION", "var", "Worker", "Which KEK wraps new DEKs"],
   ["UPSTASH_REDIS_REST_URL / _TOKEN", "secret", "Worker", "Rate limiting / counters"],
   ["AWS_PLATFORM_KEY_ID / _SECRET", "secret", "Worker", "Principal allowed to AssumeRole (BYOS)"],
   ["PLATFORM_FALLBACK_KEY", "secret", "Worker", "Optional platform-paid fallback"],
   ["ALLOWED_ORIGIN", "var", "Worker", "CORS origin of the SPA"],
   ["VITE_SUPABASE_URL / _ANON_KEY", "public", "SPA build", "Client auth (anon key is public by design)"],
   ["CLOUDFLARE_API_TOKEN / ACCOUNT_ID", "secret", "GitHub", "Deploy"],
   ["SUPABASE_ACCESS_TOKEN / DB_PASSWORD / PROJECT_REF", "secret", "GitHub", "Migrations"]],
  [2.2, 0.6, 0.8, 2.9])

H1("Appendix B — Open questions to settle for your context")
P("These materially change the design; I have assumed defaults above but you should decide them "
  "explicitly:")
B(["Which providers must be supported at launch, and which BYOS clouds your customers actually use?",
   "Is there a platform-paid fallback (and therefore billing/reselling), or strictly customer-paid?",
   "Do you need to store prompts/completions (e.g. for history), which raises data-protection "
   "obligations?",
   "Which compliance regimes and data-residency constraints apply to your customers?",
   "Do you need per-user keys, per-tenant keys, or both?",
   "Expected request volume — does it fit inside the free quotas in Section 4?"])

doc = SimpleDocTemplate(str(OUT), pagesize=letter, leftMargin=inch, rightMargin=inch,
                        topMargin=0.85 * inch, bottomMargin=0.85 * inch,
                        title="BYOK / BYOS Orchestration — Start-to-Deployment Procedure",
                        author="Generated with Claude Code",
                        subject="Bring Your Own Key and Bring Your Own Subscription architecture")
doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
print(f"wrote {OUT}")
