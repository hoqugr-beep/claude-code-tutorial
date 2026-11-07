"""Build the AI Team Orchestration client deployment playbook PDF.

Usage:  python3 guides/build_playbook_pdf.py
Output: guides/ai-team-orchestration-playbook.pdf
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

OUT = Path(__file__).with_name("ai-team-orchestration-playbook.pdf")

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




def diagram_mode_a():
    d = Drawing(468, 250)
    green = colors.HexColor("#ecfdf5")
    amber = colors.HexColor("#fffbeb")
    d.add(Rect(0, 0, 468, 250, rx=8, ry=8, fillColor=None, strokeColor=MUTED,
               strokeWidth=0.6, strokeDashArray=[3, 3]))
    d.add(String(10, 238, "Client's computer (Mode A)", fontName="Helvetica-Bold", fontSize=7.5,
                 fillColor=MUTED))
    box(d, 20, 185, 110, 38, "Staff member", "types a request")
    box(d, 175, 180, 140, 48, "Your engine", "routing + load balancing",
        fill=colors.HexColor("#dbeafe"))
    box(d, 350, 185, 105, 38, "Client profile", "roles, rules, routing", fill=amber)
    box(d, 175, 110, 140, 42, "Grok = BOSS", "plans, splits, assigns, reviews",
        fill=colors.HexColor("#fde68a"))
    arrow(d, 130, 204, 173, 204)
    arrow(d, 350, 204, 317, 204)
    arrow(d, 245, 180, 245, 154)
    workers = [("Claude worker", "Claude Code CLI"), ("Grok worker", "Grok Build CLI"),
               ("Gemini worker", "Gemini CLI"), ("ChatGPT worker", "Codex CLI")]
    for i, (n, s) in enumerate(workers):
        x = 12 + i * 114
        box(d, x, 22, 104, 40, n, s, fill=green)
        arrow(d, 245, 110, x + 52, 63)
    d.add(String(234, 6, "each CLI logged in with the CLIENT's own subscription",
                 fontName="Helvetica-Oblique", fontSize=6.6, textAnchor="middle",
                 fillColor=MUTED))
    return d


def diagram_mode_b():
    d = Drawing(468, 210)
    green = colors.HexColor("#ecfdf5")
    box(d, 0, 150, 100, 40, "Staff browser", "any device")
    box(d, 130, 150, 120, 40, "Cloudflare Access", "work-email login")
    box(d, 280, 150, 100, 40, "Cloudflare Tunnel", "no open ports")
    d.add(Rect(150, 30, 315, 105, rx=8, ry=8, fillColor=None, strokeColor=MUTED,
               strokeWidth=0.6, strokeDashArray=[3, 3]))
    d.add(String(158, 124, "Client-owned free cloud VM (Mode B)", fontName="Helvetica-Bold",
                 fontSize=7, fillColor=MUTED))
    box(d, 165, 70, 110, 40, "Chat page + engine", "Grok boss logic",
        fill=colors.HexColor("#dbeafe"))
    box(d, 295, 70, 150, 40, "keys.env (locked file)", "client's API keys",
        fill=colors.HexColor("#fffbeb"))
    arrow(d, 100, 170, 128, 170)
    arrow(d, 250, 170, 278, 170)
    arrow(d, 330, 150, 230, 112)
    arrow(d, 295, 90, 277, 90)
    apis = ["xAI API", "Anthropic API", "Google Gemini API", "OpenAI API"]
    for i, a in enumerate(apis):
        x = 5 + i * 117
        box(d, x, 0, 105, 24, a, fill=green)
    for i in range(4):
        arrow(d, 220, 70, 57 + i * 117, 25)
    return d


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    if doc.page > 1:
        canvas.drawString(inch, 0.55 * inch, "AI Team Orchestration — Client Deployment Playbook")
        canvas.drawRightString(7.5 * inch, 0.55 * inch, f"Page {doc.page}")
    canvas.restoreState()


CHECK = "[&nbsp;&nbsp;&nbsp;]&nbsp;&nbsp;"


def CHECKS(items):
    for i in items:
        story.append(Paragraph(CHECK + i, body))
    story.append(Spacer(1, 6))


# ================================================================ cover
story += [Spacer(1, 1.5 * inch),
          Paragraph("AI Team Orchestration", title),
          Spacer(1, 6),
          Paragraph("Client Deployment Playbook", ParagraphStyle(
              "t2", parent=title, fontSize=18, leading=23, textColor=INK)),
          Spacer(1, 10),
          Paragraph("Grok as the boss &middot; Claude, Grok, Gemini and ChatGPT as workers<br/>"
                    "Custom worker roles for each client's business<br/>"
                    "Mode A: client's own subscriptions on the client's computer<br/>"
                    "Mode B (option): client's own API keys (BYOK) on a free cloud server",
                    subtitle),
          Spacer(1, 0.45 * inch)]
T([["Item", "Value"],
   ["Document type", "Step-by-step procedure, from packaging to handover and support"],
   ["Prepared", "7 November 2026"],
   ["For", "The consultant who installs and configures the system for each client"],
   ["Users of the finished system", "The client's own staff, on the client's own computers"],
   ["Who pays the AI providers", "The client, always: their subscriptions (Mode A) or their API "
                                 "keys (Mode B)"]], [1.9, 4.6])
WARN("Product names, install commands, subscription plans, free-tier limits and terms of "
     "service change often. Items checked online around the preparation date are marked "
     "<b>(checked)</b>; everything else is from general knowledge and marked "
     "<b>verify</b> or <b>approx.</b> Re-check the vendor's own pages before each client "
     "install. This playbook describes a reference layout; map it onto your actual engine, "
     "which the author of this document has not seen.")
story.append(PageBreak())

# ================================================================ contents
H1("Contents")
for line in [
    "Start here — The Starter Package (recommended first offer)",
    "1. What you are delivering",
    "2. Ground rules: accounts, terms and data",
    "3. How the system works",
    "4. Phase 1 — Package your laptop system into a product",
    "5. Phase 2 — Discovery and worker-role design with the client",
    "6. Phase 3 — Pre-install checklist",
    "7. Phase 4 — Install on the client's computer (Mode A)",
    "8. Phase 5 — Testing and acceptance",
    "9. Phase 6 — Handover and staff training",
    "10. Phase 7 — Updates, support and backups",
    "11. Mode B — BYOK on a free cloud server",
    "12. Security and privacy checklist",
    "13. Troubleshooting",
    "14. Master checklists",
    "Appendix A — Role card template",
    "Appendix B — Client handover sheet",
    "Appendix C — Questions to settle before your first paid client",
]:
    story.append(Paragraph(line, ParagraphStyle("toc", parent=body, spaceAfter=2)))
story.append(PageBreak())

# ================================================================ 1
# ================================================================ starter package
H1("Start here — The Starter Package")
P("This is the recommended first offer: the <b>easiest and least expensive</b> way to deliver "
  "the system. It uses Mode A (the client's own computer and subscriptions), needs no server "
  "or extra software, and keeps both your costs and the client's as low as possible. The rest "
  "of this playbook is the full procedure; this section tells you which parts to use first.")
H2("S.1 What the Starter Package includes")
T([["Item", "Starter Package", "Add later (upsell)"],
   ["Where it runs", "One client computer (Mode A)", "More computers, or Mode B cloud server"],
   ["Users", "One staff member", "More users (each may need their own subscription seats)"],
   ["Boss", "Grok", "—"],
   ["Workers", "One paid worker (chosen by testing), plus free tiers where available",
    "Remaining providers, one at a time"],
   ["Roles", "3 roles", "More roles, industry role library"],
   ["Support", "Updates + fixes for the pilot period", "Monthly support plan"]],
  [1.3, 2.6, 2.6])
H2("S.2 Costs")
T([["Who pays", "Item", "Approximate cost (verify current prices)"],
   ["You", "Private GitHub repository for your master copy", "Free"],
   ["You", "Remote screen-share / support tool (e.g. Chrome Remote Desktop)", "Free (verify)"],
   ["You", "Your laptop for building and testing", "Already owned"],
   ["Client", "Grok subscription (boss)", "Entry plans typically ~$20–30/month (approx.)"],
   ["Client", "One paid worker subscription", "Entry plans typically ~$20–30/month (approx.)"],
   ["Client", "Optional extra workers on free tiers", "$0 if free tiers allow it (verify)"],
   ["Client", "Server / hosting", "None in Mode A"]], [0.8, 3.2, 2.5])
WARN("Free tiers reported at the time of writing: Gemini CLI with a Google account login, Codex "
     "with a free ChatGPT account, and free Grok access during the Grok Build beta. I cannot "
     "confirm these are still offered or that they allow business use; check each provider "
     "before relying on them, and treat them as testing aids rather than something to promise "
     "a client.")
H2("S.3 Choosing the one paid worker: a quick test")
B(["Take 5 real examples from discovery (Section 5) for the client's most important role.",
   "Run the same 5 requests through each candidate model (use free tiers or your own accounts "
   "for this comparison only).",
   "Score each answer 1–5 for accuracy, following the rules, and needing few edits; have the "
   "client score them too, without seeing which model wrote which.",
   "Pick the highest total. Record the scores so you can justify the choice and revisit it "
   "later."], numbered=True)
H2("S.4 Four-week pilot plan (one friendly client)")
T([["Week", "Your work", "Done when"],
   ["1", "Check provider terms (2.2); package your system (Phase 1); test the install on a "
         "fresh user account on your laptop", "Clean install works from scratch"],
   ["2", "Discovery session; write 3 role cards; run the worker test (S.3)",
    "Client approves the role cards"],
   ["3", "Pre-install checklist; install; client logs in; acceptance tests (Phases 3–5)",
    "All tests pass; handover sheet signed"],
   ["4", "Client uses it daily; short check-in calls; fix issues; note time saved",
    "Client confirms value; you have a written case study"]], [0.6, 3.9, 2.0])
H2("S.5 Go / no-go after the pilot")
CHECKS(["Install took under half a day and needed no unplanned fixes",
        "The client used it on most working days in week 4",
        "Staff estimate real time saved (ask for hours per week)",
        "No rule breaches in output (prices, private data, promises)",
        "Subscription usage limits were not a regular problem",
        "Terms check (2.2) found nothing that blocks scripted CLI use"])
P("If most boxes are ticked, standardise: turn the pilot's roles into templates, fix the "
  "install script, and set your prices. If subscription limits or terms are a problem, move "
  "the affected worker to API keys (Mode B approach) for that provider only.")
H2("S.6 Pricing structure (fill in your own numbers)")
P("I do not have verified market rates for this kind of service, so the amounts are left for "
  "you to set. The structure keeps you out of AI billing entirely:")
T([["Charge", "Covers", "Your price"],
   ["Setup fee (one-time)", "Discovery, 3 role cards, packaging for the client, install, "
                            "testing, training", "$ ______"],
   ["Extra role (one-time)", "Design, testing and install of one more role", "$ ______"],
   ["Extra worker / seat (one-time)", "Adding a provider or a user computer", "$ ______"],
   ["Monthly support", "Updates, fixes, small role tweaks, remote help", "$ ______ / month"],
   ["Pilot discount", "First client, in exchange for feedback and a testimonial", "____ %"],
   ["AI usage", "Paid by the client directly to each provider", "Not billed by you"]],
  [1.8, 3.4, 1.3])
H2("S.7 Upgrade path")
B(["<b>More workers:</b> add one provider at a time when a role clearly performs better on it.",
   "<b>More users:</b> install on more computers; confirm seat rules (2.2).",
   "<b>Mode B:</b> when a client needs shared access from any device, always-on service, or "
   "many seats — or when pay-per-use API keys would cost less than several subscriptions for "
   "light usage (Section 11)."])
story.append(PageBreak())
H1("1. What you are delivering")
P("You have built an orchestration system on your laptop: a <b>boss</b> model (Grok) receives a "
  "request, breaks it into tasks, and distributes them to <b>worker</b> models (Claude, Grok, "
  "Gemini, ChatGPT) through their command-line tools (CLIs), with your own routing and "
  "load-balancing logic in between. This playbook turns that into a repeatable service: you "
  "install the same system on each client's computer, design worker roles that fit their "
  "business, and leave them with something their staff can use and you can maintain.")
H2("1.1 Two deployment modes")
T([["", "Mode A — Desktop (primary)", "Mode B — Cloud BYOK (option)"],
   ["Runs on", "The client's own computer(s)", "A free cloud server the client owns"],
   ["AI access", "Client's own subscriptions, logged in to each CLI",
    "Client's own API keys (pay per use)"],
   ["Who uses it", "Staff at that computer", "Any staff member, from a browser, after login"],
   ["Always on?", "Only while the computer is on", "Yes"],
   ["Extra build work", "None beyond packaging", "A simple chat page in front of your engine"],
   ["Best for", "Small teams, one or a few power users",
    "Teams who want shared access, or many seats"]], [1.2, 2.65, 2.65])
H2("1.2 Vocabulary used in this playbook")
T([["Term", "Meaning"],
   ["Engine", "Your routing / load-balancing code. Identical for every client."],
   ["Boss", "Grok, acting as planner and dispatcher: decides which worker gets which task, "
            "then reviews and combines the results."],
   ["Worker", "A model doing one kind of job, defined by a role card (see Appendix A)."],
   ["Role card", "A short file describing one worker: purpose, instructions, model, limits, "
                 "and when a human must review."],
   ["Client profile", "All role cards plus routing rules for one client."],
   ["Subscription", "A monthly consumer or business plan (e.g. Claude Pro/Max, ChatGPT Plus, "
                    "SuperGrok, Google AI plans) used by logging in to a CLI."],
   ["API key (BYOK)", "A pay-per-use key from a provider's developer console."]], [1.4, 5.1])

# ================================================================ 2
H1("2. Ground rules: accounts, terms and data")
H2("2.1 The client owns every AI account")
B(["The client buys each subscription (or creates each API account) in <b>their</b> company's "
   "name, with <b>their</b> payment method and a company email address.",
   "The client types their own passwords and completes their own two-factor prompts during "
   "install. You never collect, store or reuse a client's passwords.",
   "If you stop working with the client, the system keeps working because nothing depends on "
   "your accounts."])
H2("2.2 Terms-of-service checks before you sell")
WARN("I am not certain of each provider's current wording, so confirm these points on each "
     "provider's terms and plan pages, and keep a dated note of what you found:")
B(["<b>Seats:</b> consumer subscriptions are generally licensed to one person. If several staff "
   "members will use the system, the client may need one seat each or a team/business plan. "
   "Sharing one login across several people may breach the terms.",
   "<b>CLI access is included:</b> confirm which plan tiers include CLI use (e.g. which Claude, "
   "ChatGPT, SuperGrok and Google plans unlock Claude Code, Codex, Grok Build and Gemini CLI "
   "respectively).",
   "<b>Automation:</b> confirm the plan allows its CLI to be driven by a script (your engine) "
   "rather than typed into by hand. Usage limits on subscriptions are sized for one person.",
   "<b>Business use:</b> confirm commercial use of outputs is allowed on the chosen plans.",
   "<b>Your own work:</b> you configured your engine with help from Grok; confirm xAI's terms "
   "on using generated output commercially before reselling setups built with it."])
H2("2.3 Client data")
B(["Every request a worker handles is sent to that provider. List for the client which "
   "providers will see which kinds of data.",
   "Consumer plans may, depending on settings, allow the provider to use conversations to "
   "improve models; business plans and API usage often default differently. I do not have "
   "current verified details for each provider, so check each account's privacy/data "
   "settings with the client during install and record the choices.",
   "Agree in writing which data must never be sent to the system (e.g. card numbers, health "
   "records, passwords), and put that rule in every role card."])
H2("2.4 Your service agreement (outline)")
P("Put a short written agreement in place; have a lawyer review it, as I cannot advise on your "
  "jurisdiction. Typical contents: scope (roles delivered, number of computers), the client's "
  "responsibility for their AI accounts and costs, data rules, support hours and response "
  "times, update policy, limits of liability for AI-generated output, and what happens at the "
  "end of the engagement.")

# ================================================================ 3
story.append(PageBreak())
story.append(KeepTogether([Paragraph("3. How the system works", h1),
                           Paragraph("3.1 Mode A at a glance", h2), diagram_mode_a()]))
story.append(Spacer(1, 6))
H2("3.2 Life of a request")
B(["A staff member gives the system a request (e.g. \"Draft a quote for the Smith job and a "
   "follow-up email\").",
   "The engine sends it to <b>Grok (boss)</b> together with the list of available worker roles "
   "from the client profile.",
   "The boss returns a plan: which tasks, which role handles each, in what order.",
   "The engine dispatches each task to the right worker CLI, applying your load-balancing rules "
   "(e.g. if one provider hits its usage limit, use the role's fallback model).",
   "Results come back to the boss, which checks them against each role's rules and combines "
   "them into one answer.",
   "If a role is marked <i>human review required</i>, the result is shown as a draft for the "
   "staff member to approve rather than as final output."], numbered=True)
H2("3.3 Headless (non-interactive) CLI calls")
P("For an engine to drive a CLI, each tool needs a non-interactive mode where a prompt goes in "
  "and an answer comes out. Your engine already does this; the table records the commands to "
  "confirm on each client install, because flags change between versions.")
T([["Worker", "CLI", "Non-interactive form (verify with --help)"],
   ["Claude", "Claude Code", "<font face='Courier'>claude -p \"&lt;prompt&gt;\"</font>"],
   ["ChatGPT", "Codex CLI", "<font face='Courier'>codex exec \"&lt;prompt&gt;\"</font>"],
   ["Gemini", "Gemini CLI", "<font face='Courier'>gemini -p \"&lt;prompt&gt;\"</font>"],
   ["Grok", "Grok Build (<font face='Courier'>grok</font>)",
    "Check <font face='Courier'>grok --help</font>; I have not verified its headless flag"]],
  [1.0, 1.6, 3.9])
BOX("These CLIs are built as coding agents and can read files and run commands in the folder "
    "they start in. Start each worker in a dedicated, empty working folder (e.g. "
    "<font face='Courier'>work/claude</font>) and use each tool's permission settings so "
    "workers cannot change files or run commands you did not intend.", label="Safety")

# ================================================================ 4
H1("4. Phase 1 — Package your laptop system into a product")
P("Goal: anything client-specific or personal is pulled out of the code, so the same engine "
  "installs anywhere with a different profile.")
H2("4.1 Steps")
B(["<b>Back up</b> your current working system (copy the whole folder somewhere safe).",
   "<b>Put it in a private GitHub repository</b> if it is not already. This becomes the master "
   "copy and the source of every client install and update.",
   "<b>Find personal values</b>: your usernames, folder paths (e.g. <font face='Courier'>"
   "C:\\Users\\you\\...</font> or <font face='Courier'>/Users/you/...</font>), your email, any "
   "keys or tokens. Replace each with a setting read from a config file or environment "
   "variable.",
   "<b>Move roles and routing into files</b> under <font face='Courier'>profiles/</font> "
   "(format below), so a client's setup is data, not code.",
   "<b>Add a .gitignore</b> so logs, outputs and any secrets file are never committed.",
   "<b>Write the install script</b> (4.4) and test it on a clean computer or a fresh user "
   "account on your own machine. This is the single best predictor of a smooth client "
   "install.",
   "<b>Tag a version</b> (e.g. v1.0.0) so you always know what each client is running."],
  numbered=True)
H2("4.2 Suggested folder layout")
C("""
ai-team/
  engine/                 # your routing + load balancing (same for all clients)
  profiles/
    _template/            # starter profile copied for each new client
      team.yaml           # boss, workers, routing rules
      roles/
        researcher.yaml
        writer.yaml
    acme-plumbing/        # one folder per client (or keep in a private client repo)
  scripts/
    install-mac.sh
    install-windows.ps1
    update.(sh|ps1)
    doctor.(sh|ps1)       # checks every CLI is installed and logged in
  docs/
    staff-guide.md        # one-page guide left with the client
  .gitignore              # logs/, outputs/, *.env
  VERSION
""")
H2("4.3 Team and role file formats (example)")
P("Use whatever format your engine already reads; YAML is shown because it is easy for "
  "non-programmers to edit.")
C("""
# profiles/acme-plumbing/team.yaml
client: Acme Plumbing Ltd
boss:
  worker: grok
  instructions: |
    You are the team lead. Split each request into tasks, assign each task to the
    best role below, then check and combine the results. Follow every role's rules.
workers:                      # how to reach each model on THIS machine
  claude:  { cli: claude, mode: subscription }
  chatgpt: { cli: codex,  mode: subscription }
  gemini:  { cli: gemini, mode: subscription }
  grok:    { cli: grok,   mode: subscription }
routing:
  max_parallel_tasks: 2       # keep low: subscription limits are per person
  retry_on_limit: true        # on a usage-limit error, use the role's fallback
  timeout_seconds: 300
""")
C("""
# profiles/acme-plumbing/roles/quote-writer.yaml
id: quote-writer
title: Quote Writer
purpose: Turn job notes into a customer quote using the price list.
worker: claude
fallback: chatgpt
inputs: [job notes, price-list.csv]
output: Quote in the company template, under one page.
instructions: |
  Use only prices from price-list.csv. If an item is missing, list it under
  "Needs pricing" instead of guessing. Plain, friendly tone.
must_not:
  - invent prices, discounts or delivery dates
  - include customer card or bank details
human_review: required        # staff approve before anything is sent
""")
H2("4.4 Install script responsibilities")
B(["Check prerequisites (Node.js version, Git) and stop with a clear message if missing.",
   "Install or update each CLI (Section 7.2).",
   "Copy the engine and the client's profile into a fixed location.",
   "Create the per-worker working folders.",
   "Run <font face='Courier'>doctor</font>: confirm each CLI starts and is logged in, and run "
   "one test prompt through the boss.",
   "Create a desktop shortcut or a single start command for staff."])

# ================================================================ 5
H1("5. Phase 2 — Discovery and worker-role design")
P("This is where your value is: understanding the business and turning it into a small team "
  "of well-defined workers. Plan a 60–90 minute session with the owner and the staff who will "
  "use the system.")
H2("5.1 Discovery questions")
B(["What tasks eat the most time each week? Who does them today?",
   "Which of those produce a document, message or decision that a person could check?",
   "What inputs exist (templates, price lists, FAQs, past examples)? Collect 3–5 good examples "
   "of finished work for each task.",
   "What must never happen (wrong prices, promises, sharing private data, tone mistakes)?",
   "Who approves output before it leaves the business?",
   "Which staff members will use the system, on which computers?"])
H2("5.2 From tasks to roles")
B(["Start with <b>3 to 5 roles</b>. More roles make the boss's routing less reliable and are "
   "harder to test.",
   "One role = one kind of output. Split a role if its instructions start to contradict "
   "themselves.",
   "Write the <i>must_not</i> list from the client's own words in discovery.",
   "Mark any customer-facing or money-related role as <b>human review required</b>.",
   "Assign a primary model and a fallback. Choose by testing the client's real examples on two "
   "or three models and comparing; model strengths shift with each release, so avoid fixed "
   "assumptions about which model is best at what."])
H2("5.3 Example role sets (starting points, adapt per client)")
T([["Business type", "Possible roles"],
   ["Trades / home services", "Quote Writer, Job Scheduler Assistant, Customer Reply Drafter, "
                              "Review Responder"],
   ["Real estate", "Listing Writer, Market Summary Researcher, Client Update Drafter, "
                   "Document Checklist Checker"],
   ["Accounting / bookkeeping", "Client Email Drafter, Document Request Tracker, "
                                "Policy Q&amp;A (internal), Meeting Summariser"],
   ["Retail / e-commerce", "Product Description Writer, Customer Service Drafter, "
                           "Social Post Writer, Competitor Price Researcher"],
   ["Professional services", "Proposal Writer, Research Assistant, Report Formatter, "
                             "Meeting Summariser"]], [1.8, 4.7])
BOX("For anything legal, medical, financial or safety-related, set roles to draft-only with "
    "mandatory human review, and say so in the staff guide.")

# ================================================================ 6
H1("6. Phase 3 — Pre-install checklist")
P("Send this to the client about a week before the install visit or screen-share.")
H2("6.1 Client tasks")
CHECKS(["Buy the agreed subscriptions in the company's name (one per user if required — "
        "see 2.2): Claude, ChatGPT, SuperGrok/X, Google AI plan as agreed.",
        "Enable two-factor authentication on each account and have phones ready for codes.",
        "Have the computer's administrator (admin) password available.",
        "Collect the example documents, templates and price lists from discovery.",
        "Decide which staff will use the system and on which computers."])
H2("6.2 Computer requirements")
T([["Item", "Requirement"],
   ["Operating system", "Recent macOS, or Windows 10/11. On Windows, some CLIs work best "
                        "inside WSL2 (Windows Subsystem for Linux) — check each tool's docs."],
   ["Node.js", "A current LTS release. Sources disagree on minimum versions per CLI "
               "(one guide says Codex needs Node 22+); use the newest LTS to be safe "
               "<b>(verify)</b>."],
   ["Git", "Needed to install and update your engine."],
   ["Internet", "Stable connection; the system cannot work offline."],
   ["Disk / RAM", "Several GB free disk; 8 GB RAM or more recommended (approx.)."]],
  [1.4, 5.1])

# ================================================================ 7
H1("7. Phase 4 — Install on the client's computer (Mode A)")
H2("7.1 Order of work")
B(["Create a dedicated local user folder for the system, or a separate computer account if "
   "the machine is shared.",
   "Install prerequisites: Node.js LTS and Git.",
   "Install the four CLIs (7.2).",
   "<b>Client logs in to each CLI</b> with their own account while you guide (7.3).",
   "Install your engine from your repository at the tagged version.",
   "Copy in the client's profile (roles + routing) from Phase 2.",
   "Run <font face='Courier'>doctor</font>, then the acceptance tests in Section 8.",
   "Create the staff start shortcut; walk staff through one real task."], numbered=True)
H2("7.2 Install the CLIs")
T([["CLI", "macOS / Linux", "Windows (PowerShell)", "Status"],
   ["Claude Code", "<font face='Courier'>curl -fsSL https://claude.ai/install.sh | bash</font>",
    "<font face='Courier'>irm https://claude.ai/install.ps1 | iex</font>",
    "verify; npm package <font face='Courier'>@anthropic-ai/claude-code</font> also exists"],
   ["Grok Build", "<font face='Courier'>curl -fsSL https://x.ai/cli/install.sh | bash</font>",
    "<font face='Courier'>irm https://x.ai/cli/install.ps1 | iex</font>",
    "checked (secondary sources); beta, changes often — see x.ai/cli"],
   ["Gemini CLI", "<font face='Courier'>npm install -g @google/gemini-cli</font>",
    "same", "checked (secondary sources)"],
   ["Codex CLI", "<font face='Courier'>npm install -g @openai/codex</font>", "same",
    "checked (secondary sources)"]], [1.0, 2.15, 1.85, 1.5])
WARN("Piping an install script from the internet into a shell runs it with your permissions. "
     "Only use the official domains above, type them carefully, and prefer the vendor's "
     "current install page over copying from this document.")
H2("7.3 Log in with the client's subscriptions")
T([["CLI", "How to sign in", "What to check"],
   ["Claude Code", "Run <font face='Courier'>claude</font> and choose the Claude account "
                   "(subscription) login", "Signed in as the client's company email"],
   ["Codex CLI", "Run <font face='Courier'>codex login</font> and sign in with ChatGPT",
    "Correct ChatGPT account and plan"],
   ["Gemini CLI", "Run <font face='Courier'>gemini</font> and choose Google account login",
    "Company Google account, not a personal one"],
   ["Grok Build", "Run <font face='Courier'>grok</font> and sign in", "Correct X/xAI account"]],
  [1.1, 3.2, 2.2])
B(["Make sure no API-key environment variables (e.g. <font face='Courier'>ANTHROPIC_API_KEY"
   "</font>, <font face='Courier'>OPENAI_API_KEY</font>, <font face='Courier'>GEMINI_API_KEY"
   "</font>) are set on the machine in Mode A; some CLIs prefer a key over the subscription "
   "login when both exist, which would bill the client per use instead <b>(verify per CLI)</b>.",
   "Check each CLI's own logout/status command so you can show the client how to disconnect "
   "an account if a staff member leaves."])
H2("7.4 Smoke test")
C("""
doctor                         # your script: versions + login status for all 4 CLIs
claude -p "Reply with OK"      # each worker answers on its own (verify flags)
codex exec "Reply with OK"
gemini -p "Reply with OK"
<your engine start command> "Plan a short test task using two roles"
""")

# ================================================================ 8
H1("8. Phase 5 — Testing and acceptance")
H2("8.1 Test set per role")
P("For each role, prepare at least five test requests built from the client's real examples: "
  "three normal cases, one edge case (missing information), and one <i>must_not</i> case (a "
  "request that should be refused or flagged). Record the expected behaviour in advance.")
T([["Check", "Pass when"],
   ["Routing", "The boss assigns each test request to the intended role"],
   ["Quality", "Output matches the client's example standard; staff would send it after "
               "light edits"],
   ["Rules", "Every must_not case is refused, flagged or left for a human"],
   ["Fallback", "Simulated limit/unavailable worker results in the fallback model being used, "
                "or a clear message"],
   ["Speed", "Typical request completes in a time staff accept (agree a target)"],
   ["Review gates", "Roles marked human_review produce drafts, never final sends"]],
  [1.5, 5.0])
H2("8.2 Acceptance")
P("Run the tests with the client watching, fix what fails, re-run, and have the client sign "
  "the handover sheet (Appendix B). Keep the test set; rerun it after every update.")

# ================================================================ 9
H1("9. Phase 6 — Handover and staff training")
B(["A one-page staff guide: how to start the system, how to phrase requests, what the roles "
   "are, what must never be entered, how to report a problem.",
   "A 30–45 minute session where each user completes two real tasks.",
   "Show the owner how to: see which accounts are logged in, sign a departing staff member "
   "out, and change a subscription plan.",
   "Leave the handover sheet (Appendix B) with versions, roles, contacts and support terms."])

# ================================================================ 10
H1("10. Phase 7 — Updates, support and backups")
H2("10.1 Updates")
B(["Improve the engine in your master repository; tag a new version; test it on your laptop "
   "with a copy of each client's profile.",
   "Update a client with the update script (pull the tagged version, update CLIs, run "
   "doctor and the client's test set). Record the new version on the handover sheet.",
   "Update the CLIs themselves regularly (e.g. <font face='Courier'>grok update</font>, "
   "<font face='Courier'>npm update -g</font> for npm-installed tools); retest afterwards "
   "because CLI changes can break headless flags."])
H2("10.2 Remote support")
B(["Use a remote-support tool the client controls, with access granted per session.",
   "Never ask for passwords; let the client re-authenticate CLIs themselves if needed."])
H2("10.3 Backups")
B(["Your master repository plus each client profile is the backup of the configuration.",
   "Agree whether outputs/logs are kept, where, and for how long; exclude them from Git."])

# ================================================================ 11
story.append(PageBreak())
H1("11. Mode B — BYOK on a free cloud server")
P("Offer Mode B when a client wants staff to use the system from any device, wants it running "
  "when office computers are off, or would need many subscription seats. The client creates "
  "<b>API accounts</b> (pay per use) instead of subscriptions, and the client owns the cloud "
  "server too, so the whole setup stays theirs.")
story.append(KeepTogether([Paragraph("11.1 Mode B at a glance", h2), diagram_mode_b()]))
story.append(Spacer(1, 6))
H2("11.2 What changes compared to Mode A")
B(["Workers use the client's <b>API keys</b> instead of subscription logins. Most of the CLIs can "
   "read a key from an environment variable (e.g. <font face='Courier'>ANTHROPIC_API_KEY"
   "</font>, <font face='Courier'>OPENAI_API_KEY</font>, <font face='Courier'>GEMINI_API_KEY"
   "</font>); confirm Grok Build's API-key option in its docs. Alternatively your engine can "
   "call the providers' APIs directly, which is faster and more robust on a server.",
   "Staff reach the system through a simple <b>private chat web page</b>. This is the one new "
   "piece to build; your engine's start command sits behind it.",
   "Access is protected by a login (Cloudflare Access) and the server is not exposed directly "
   "to the internet (Cloudflare Tunnel)."])
H2("11.3 Free server options")
T([["Option", "What's free", "Caveats"],
   ["Oracle Cloud Always Free (recommended)",
    "Arm VM (Ampere A1). Reported in 2026 as cut to <b>2 OCPU / 12 GB RAM</b> total, from the "
    "4 OCPU / 24 GB many guides still quote <b>(checked, secondary sources — verify on "
    "Oracle's page)</b>",
    "Sign-up needs a card for verification (verify). Idle instances can be reclaimed when "
    "usage stays low over 7 days (thresholds reported variously at ~10–20% CPU). Capacity "
    "can be unavailable in some regions."],
   ["Google Cloud free tier",
    "One small e2-micro VM in certain US regions (approx.; verify)",
    "About 1 GB RAM — tight for several Node-based CLIs plus an engine."],
   ["Render free web service",
    "750 instance-hours/month <b>(checked)</b>",
    "Sleeps after 15 min idle (~1 min wake-up) and is designed for web apps, not "
    "long-running CLI jobs — not recommended here."],
   ["Low-cost paid VPS", "Not free: roughly $5–10/month (approx.)",
    "Simplest reliable option if free capacity is unavailable."]], [1.5, 2.6, 2.4])
H2("11.4 Get the client's API keys")
T([["Provider", "Where the client creates the key (verify URLs)", "Environment variable"],
   ["xAI (Grok)", "console.x.ai", "<font face='Courier'>XAI_API_KEY</font> (common "
                                  "convention; verify)"],
   ["Anthropic (Claude)", "console.anthropic.com", "<font face='Courier'>ANTHROPIC_API_KEY</font>"],
   ["Google (Gemini)", "aistudio.google.com", "<font face='Courier'>GEMINI_API_KEY</font>"],
   ["OpenAI (ChatGPT models)", "platform.openai.com", "<font face='Courier'>OPENAI_API_KEY</font>"]],
  [1.5, 2.8, 2.2])
B(["The client creates each key while logged in to their own account and pastes it directly "
   "into the server's key file during the session (11.5 step 6). Do not send keys by email or "
   "chat.",
   "Have the client set a <b>monthly spending limit</b> or budget alert in each provider "
   "console, if the provider offers one."])
H2("11.5 Server setup (Oracle Always Free, Ubuntu)")
B(["Client creates the Oracle Cloud account (company email, their card for verification).",
   "Create a VM: Ubuntu image, Ampere A1 shape within the Always Free allowance; add your SSH "
   "public key (and the client's) for login. Keep the default network rules; do not open web "
   "ports — the tunnel makes that unnecessary.",
   "Log in over SSH and apply updates.",
   "Create a dedicated user for the system and install Node.js LTS (follow nodejs.org's "
   "current Ubuntu instructions) and Git.",
   "Install your engine and the API-key-capable CLIs (or your direct-API workers).",
   "Create the locked key file with the client's keys.",
   "Run the engine as a service so it restarts automatically.",
   "Add Cloudflare Tunnel and Access (11.6).",
   "Run the acceptance tests (Section 8) through the chat page."], numbered=True)
C("""
# step 3-4
sudo apt update && sudo apt -y upgrade
sudo apt install -y git curl
sudo useradd --create-home --shell /bin/bash aiteam

# step 6: key file readable only by the service user
sudo mkdir -p /etc/ai-team
sudo nano /etc/ai-team/keys.env          # client pastes:  XAI_API_KEY=...  etc.
sudo chown aiteam:aiteam /etc/ai-team/keys.env
sudo chmod 600 /etc/ai-team/keys.env

# step 7: /etc/systemd/system/ai-team.service
[Unit]
Description=AI team engine
After=network-online.target
[Service]
User=aiteam
WorkingDirectory=/home/aiteam/ai-team
EnvironmentFile=/etc/ai-team/keys.env
ExecStart=/usr/bin/npm start              # replace with your engine's start command
Restart=on-failure
[Install]
WantedBy=multi-user.target

sudo systemctl daemon-reload && sudo systemctl enable --now ai-team
""")
H2("11.6 Private access: Cloudflare Tunnel + Access")
P("Cloudflare's Zero Trust free plan covers up to <b>50 users</b> and includes Access and "
  "Tunnel <b>(checked)</b>. It needs a domain managed in a Cloudflare account (the client's). "
  "The tunnel connects outward from the server, so no inbound web port is opened.")
C("""
# on the server (install cloudflared per Cloudflare's current docs first)
cloudflared tunnel login
cloudflared tunnel create ai-team
cloudflared tunnel route dns ai-team team.clientdomain.com
# config: send team.clientdomain.com to the chat page, e.g. http://localhost:3000
sudo cloudflared service install
""")
B(["In the Cloudflare Zero Trust dashboard, create an Access application for "
   "<font face='Courier'>team.clientdomain.com</font> with a policy allowing only the client's "
   "staff email addresses (or their email domain).",
   "Staff then open the address, enter their work email, receive a one-time code, and reach "
   "the chat page.",
   "Command names above reflect Cloudflare's documented flow as I know it; follow the current "
   "Cloudflare Tunnel guide, which may prefer dashboard-created tunnels <b>(verify)</b>."])
H2("11.7 Keeping a free server healthy")
B(["Check Oracle's idle-reclamation rules; a lightly used assistant may look idle. Upgrading "
   "the account to pay-as-you-go (still using free resources) is reported to avoid "
   "reclamation — verify before relying on it.",
   "Enable automatic security updates (e.g. Ubuntu's unattended-upgrades).",
   "Back up the engine folder and profile (they are already in Git) and the key file location "
   "(not the keys — the client can recreate keys)."])

# ================================================================ 12
H1("12. Security and privacy checklist")
CHECKS([
    "All AI accounts are in the client's name; you hold no client passwords.",
    "Two-factor authentication is on for every AI, cloud and Cloudflare account.",
    "Mode A: no stray API-key environment variables; each worker runs in its own folder with "
    "restricted CLI permissions.",
    "Mode B: keys only in the locked key file (chmod 600), never in Git, email or chat; "
    "spending limits set at each provider.",
    "Mode B: no inbound web ports open; access only through Cloudflare Access.",
    "Data rules agreed and written into every role card's must_not list.",
    "Privacy/data-use settings reviewed in each AI account and recorded.",
    "Customer-facing and money-related roles require human review.",
    "Logs and outputs excluded from Git and kept only as long as agreed.",
    "Process for removing a departing staff member (sign out CLIs / remove from Access policy).",
])

# ================================================================ 13
H1("13. Troubleshooting")
T([["Symptom", "Likely cause", "Fix"],
   ["A worker says it is not logged in", "Session expired or password changed",
    "Client re-runs that CLI's login"],
   ["Worker errors about usage limits", "Subscription limit reached",
    "Fallback should take over; consider a higher plan or Mode B for heavy use"],
   ["Worker bills per use unexpectedly", "An API-key variable is set in Mode A",
    "Remove the variable; restart the engine"],
   ["Boss sends tasks to the wrong role", "Role purposes overlap or are vague",
    "Sharpen role purposes; reduce the number of roles"],
   ["Headless call hangs", "CLI waiting for a permission or update prompt",
    "Run the CLI by hand to see the prompt; adjust permission settings; update CLI"],
   ["Everything broke after an update", "CLI flags changed",
    "Roll back to the previous tagged version; retest; fix the engine"],
   ["Mode B page unreachable", "Tunnel or service stopped; VM reclaimed",
    "Check <font face='Courier'>systemctl status ai-team</font> and cloudflared; check the "
    "cloud console"]], [1.8, 2.0, 2.7])

# ================================================================ 14
H1("14. Master checklists")
H2("14.1 New client")
CHECKS(["Service agreement signed (2.4)", "Terms checks done and noted (2.2)",
        "Discovery session held; examples collected (5.1)",
        "Role cards written and reviewed with the client (5.2, Appendix A)",
        "Pre-install checklist completed by client (6)",
        "Install done; CLIs logged in by client (7)", "Acceptance tests passed (8)",
        "Staff trained; handover sheet signed (9, Appendix B)"])
H2("14.2 Each update")
CHECKS(["New version tagged and tested on your laptop with the client's profile",
        "Client notified of the update window", "Update script run; doctor passes",
        "Client test set passes", "Version recorded on handover sheet"])

# ================================================================ appendices
H1("Appendix A — Role card template")
C("""
id:            short-name-with-dashes
title:         Human-friendly name
purpose:       One sentence: what this worker produces, for whom.
worker:        claude | chatgpt | gemini | grok
fallback:      second choice model
inputs:        what it is given (files, notes, templates)
output:        format, length, tone, template to follow
instructions: |
  The detailed working instructions in the client's language and style.
examples:      paths to 3-5 good examples of finished work
must_not:
  - things it must never do (from discovery)
human_review:  required | optional
owner:         client staff member responsible for this role
""")
H1("Appendix B — Client handover sheet")
T([["Field", "Value"],
   ["Client / site", ""], ["Mode", "A (desktop) / B (cloud BYOK)"],
   ["Computers or server", ""], ["Engine version installed", ""],
   ["CLI versions (Claude Code / Codex / Gemini / Grok Build)", ""],
   ["AI accounts and plans (owner: client)", ""],
   ["Roles delivered", ""], ["Data rules agreed", ""],
   ["Privacy settings chosen per AI account", ""],
   ["Support contact and hours", ""], ["Acceptance tests passed on (date)", ""],
   ["Client signature / date", ""]], [3.0, 3.5])
H1("Appendix C — Questions to settle before your first paid client")
B(["Exactly which subscription plans give CLI access for each provider today, and whether "
   "scripted (headless) use is allowed on them (2.2)?",
   "One seat per staff member, or a team plan — what will each client need?",
   "Does your engine run on Windows as well as macOS, or will Windows clients need WSL2?",
   "How will you price: setup fee per client, per role, plus monthly support?",
   "Which roles become your standard library, reused across clients in the same industry?",
   "When does a client graduate from Mode A to Mode B?"])

doc = SimpleDocTemplate(str(OUT), pagesize=letter, leftMargin=inch, rightMargin=inch,
                        topMargin=0.85 * inch, bottomMargin=0.85 * inch,
                        title="AI Team Orchestration — Client Deployment Playbook",
                        author="Generated with Claude Code",
                        subject="Grok boss / multi-model worker orchestration deployment")
doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
print(f"wrote {OUT}")
