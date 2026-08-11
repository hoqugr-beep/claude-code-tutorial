# Product Spec — Healthcare Claims Copilot (working name: **Ledger**)

**Status:** Draft v1 for build decision · August 2026
**Companion doc:** `app-store-ai-gaps-2026.md` (why this category, over the alternatives)

---

## 1. Thesis

Every existing consumer app in this space treats a medical bill as **a document to
analyze**. Photograph it, get an LLM opinion, get a letter, delete the app. That
is a one-shot tool in a category where the underlying problem recurs every time
anyone in the household sees a doctor.

Ledger treats a household's medical billing as **a continuous ledger with an
adversarial counterparty and statutory deadlines.** The product is not "explain
this bill." It is: *nothing gets paid that shouldn't, nothing gets missed that
was owed to you, and no appeal window closes silently.*

The wedge that makes this work in v1 requires no AI at all: **compare what the
insurer's EOB says you owe against what the provider actually billed you.** When
those two numbers disagree, the provider is usually wrong, and the patient almost
never checks because the two documents arrive weeks apart in different envelopes.

---

## 2. Why now — the timing is the whole bet

**CMS-0057-F (Interoperability and Prior Authorization Final Rule)** requires
impacted payers — Medicare Advantage organizations, state Medicaid/CHIP FFS,
Medicaid and CHIP managed care, and QHPs on the federal exchanges — to operate
**four FHIR APIs by January 1, 2027**:

| API | What it gives a consumer app |
|---|---|
| **Patient Access** | Claims, encounters, and — newly required under this rule — **prior authorization data** (excluding drugs) |
| Provider Access | (not consumer-facing) |
| Payer-to-Payer | Continuity when the user changes plans |
| **Prior Authorization** | Status and decision data on the exact events that generate denials |

Operational prior-auth policy compliance dates began **January 1, 2026**, with the
first mandated metrics reported by **March 31, 2026**. Public reporting is already
live.

**What this means:** the single hardest part of this product — getting structured,
authoritative claim and denial data out of insurers — stops being a business
development problem and becomes a legal obligation on the counterparty, on a known
date. An app that is architected and shipped through H2 2026 walks into a data
supply that arrives on schedule in January 2027. The incumbents shipping photo
scanners are not building for that.

This is the most defensible thing about the idea, and it has an expiration date.
The window is roughly **now through mid-2027**, after which the data is commodity
and the advantage shifts entirely to whoever accumulated the outcomes corpus first
(§7).

---

## 3. The user

**Primary — "the household administrator."** One person per family absorbs all
medical admin. Skews female, 35–60, often managing care for a child or parent as
well as themselves. Financially literate, not clinically or legally trained.
Trigger event: a bill arrives that is larger than expected, or a claim is denied.

**Their actual jobs:**
1. *"Do I really owe this?"* — the reconciliation job. Highest frequency, lowest emotional stakes, best wedge.
2. *"This was denied and I think it shouldn't have been."* — the appeal job. Lower frequency, very high stakes, monetizes hardest.
3. *"Am I on track against my deductible / out-of-pocket max?"* — the position job. Creates the reason to open the app when nothing is wrong.
4. *"What is the deadline on this, and did I miss it?"* — the anxiety job. This is the retention engine.

**Secondary — the caregiver.** Managing a parent's Medicare Advantage plan.
Different appeal regime (§6.4), different urgency, higher denial rates. Serve in
v2, not v1 — the timelines are unforgiving and getting one wrong is a real harm.

**Explicit non-user:** the uninsured, and anyone whose problem is affording a
correct bill. That is charity care and financial-assistance screening — an
adjacent, worthy, differently-shaped product. Out of scope.

---

## 4. Scope

### v1 — "Reconcile" (target: 12 weeks to TestFlight)

**In:**
- Capture EOBs and provider bills by camera, PDF, photo library, or share sheet
- OCR + structured extraction into the claim ledger
- Automatic pairing of a provider bill to its matching EOB
- The v1 detection rule set (§6.2) — deterministic checks, no model judgment
- Deadline tracking with escalating reminders for commercial/ERISA plans
- Generated dispute artifacts: provider billing-office letter, insurer internal
  appeal letter, phone script with the specific numbers filled in
- Deductible / OOP-max position, computed from ingested EOBs
- Household support: multiple members under one plan

**Out of v1:**
- Payer API connections (v2 — gated on §11 unit economics)
- Medicare Advantage appeals (v2)
- Prior-auth tracking (v3, gated on the Jan 2027 API availability)
- Any negotiation-on-your-behalf or filing-on-your-behalf service (v3, and a
  different regulatory posture entirely)
- Provider price shopping, insurance plan selection, HSA/FSA management

**The v1 bar:** a user photographs one EOB and one bill and, within 60 seconds,
learns either "this is correct, pay it" or "you are being overcharged by $X, here
is the letter." Everything else is scaffolding around that moment.

---

## 5. Architecture

```
   INGEST                  LEDGER                ENGINES              OUTPUT
┌────────────┐        ┌──────────────┐      ┌─────────────┐     ┌──────────────┐
│ Camera/PDF │──┐     │              │      │ Detection   │     │ Findings     │
│ Share ext. │  │     │  Claim       │─────▶│ (rules)     │────▶│ (ranked, $)  │
├────────────┤  ├────▶│  Ledger      │      ├─────────────┤     ├──────────────┤
│ Email fwd  │──┤     │              │─────▶│ Deadline    │────▶│ Timeline +   │
├────────────┤  │     │  · Claims    │      │ (regime FSM)│     │ notifications│
│ Payer FHIR │──┘     │  · EOBs      │      ├─────────────┤     ├──────────────┤
│ (v2)       │        │  · Bills     │─────▶│ Appeal      │────▶│ Letter / PDF │
└────────────┘        │  · Plan doc  │      │ (generation)│     │ / script     │
                      └──────────────┘      └──────┬──────┘     └──────────────┘
                                                   │
                                            ┌──────▼──────┐
                                            │  OUTCOMES   │  ← the moat
                                            │  CORPUS     │
                                            └─────────────┘
```

### 5.1 Ingest paths, in order of build

1. **Document capture (v1).** Camera, PDF import, Photos, and a share-sheet
   extension. VisionKit `DataScannerViewController` for capture; on-device Vision
   OCR for text; a structured-extraction pass to map to the claim schema. Cheap,
   works for every plan type in the country on day one, and requires zero
   partnerships.
2. **Email forwarding (v1.5).** User forwards insurer/provider email to a unique
   address; server parses attachments. Low effort, meaningfully raises ingestion
   frequency, which is the leading indicator of retention.
3. **Payer FHIR APIs (v2).** Via an aggregator — Flexpa is the closest fit
   (CMS-9115 payer APIs, ONC provider APIs, TEFCA), with claims identification as
   its differentiated capability; 1upHealth is the enterprise alternative. **Do
   not build direct payer connections.** See §11 for the unresolved unit
   economics, which gate this entire path.
4. **Prior-auth data (v3, post-Jan 2027).** Arrives through the same Patient
   Access API once CMS-0057-F compliance lands.

### 5.2 The plan document

The differentiator nobody else has. A generic LLM cannot tell you whether *your*
plan covers a service; your Summary of Benefits and Coverage (SBC) and Evidence
of Coverage (EOC) can. On onboarding, the user uploads or the app fetches the SBC.
Extract: deductible (individual/family), OOP max, coinsurance, copay tiers,
preventive-care schedule, network tiers, plan type (ERISA self-funded vs fully
insured vs marketplace vs MA — this determines the entire appeal regime), and the
plan's own stated appeal address and deadlines.

Every finding is then argued **in the plan's own language**, quoting the section.
That is the difference between a letter that gets processed and one that gets
filed.

---

## 6. The engines

### 6.1 Claim ledger — data model sketch

```
Member        id, household_id, name, dob, member_id, plan_id
Plan          id, payer, plan_type[erisa_self|fully_insured|marketplace|
                  medicare_advantage|medicaid], plan_year, deductible_ind,
                  deductible_fam, oop_max_ind, oop_max_fam, coinsurance_pct,
                  sbc_doc_id, appeal_address, appeal_window_days
Claim         id, member_id, claim_number, date_of_service, provider_npi,
                  provider_name, place_of_service, status
ServiceLine   id, claim_id, cpt_hcpcs, modifiers[], units, billed_amount,
                  allowed_amount, plan_paid, patient_responsibility,
                  carc_codes[], rarc_codes[], is_preventive
EOB           id, claim_id, payer, processed_date, received_date, doc_id
ProviderBill  id, claim_id?, provider_name, statement_date, due_date,
                  amount_due, line_items[], doc_id
Finding       id, claim_id, rule_id, severity, dollars_at_stake, confidence,
                  status[open|disputed|resolved_win|resolved_loss|dismissed],
                  evidence_refs[]
Deadline      id, claim_id, regime, type[internal_appeal|external_review|
                  provider_dispute], starts_at, expires_at, state
AppealAction  id, finding_id, channel[letter|phone|portal], sent_at, outcome,
                  outcome_amount, argument_ids[]
```

The unit of value is the **Finding**: a specific dollar amount, on a specific
claim, with a named cause and a next action. Never surface an undifferentiated
"analysis."

### 6.2 Detection rules — v1 set

Deterministic first. Every rule below is arithmetic or a lookup, not a judgment
call, which means high precision and no hallucinated accusations. Ship these
before any model-based detection.

| # | Rule | Signal | Why it wins |
|---|---|---|---|
| R1 | **Bill exceeds EOB patient responsibility** | `bill.amount_due > Σ line.patient_responsibility` | The highest-frequency, highest-confidence error in American healthcare. Pure arithmetic. |
| R2 | **Preventive billed as diagnostic** | Service on the ACA preventive schedule carrying patient cost-share | ACA mandates $0 cost-share for in-network preventive care. Extremely common with screening colonoscopies and annual physicals. |
| R3 | **Balance billing violation (No Surprises Act)** | Out-of-network clinician billing at an in-network facility, or emergency services, with cost-share above in-network rates | Federal violation; the letter writes itself. |
| R4 | **Timely-filing denial passed to patient** | CARC 29 present, yet patient responsibility > 0 | Provider's failure to file on time is a provider write-off. Patient owes nothing. |
| R5 | **Duplicate line** | Same CPT + same DOS + same NPI + same units, billed twice | Arithmetic. |
| R6 | **Deductible already satisfied** | Cumulative YTD deductible from ledger ≥ plan deductible, yet line applies deductible | Requires the ledger — a single-document scanner structurally cannot catch this. |
| R7 | **Out-of-pocket max exceeded** | Cumulative YTD OOP ≥ plan OOP max, yet cost-share applied | Same. This is the ledger's proof of value. |
| R8 | **Cost-share exceeds plan terms** | Coinsurance charged ≠ `allowed_amount × plan.coinsurance_pct` | Cross-checks the EOB against the SBC. |
| R9 | **In-network facility, out-of-network rate applied** | Facility in network per plan directory; OON tier applied | Common EOB processing error. |
| R10 | **Billed before EOB processed** | Provider bill dated before payer processed date | User should not pay yet — pure timing advice, builds trust cheaply. |
| R11 | **Unbundling (NCCI)** | Component codes billed separately where an NCCI edit pair exists | Requires the NCCI edit tables; defer to v1.5 if it slips. |

Model-assisted detection (upcoding plausibility, medical-necessity argument
construction) comes **after** the deterministic set is shipping and calibrated.
The failure mode to avoid is an app that confidently accuses a provider of fraud
because a language model pattern-matched. Every finding surfaced to a user must
carry a dollar figure and a citation.

**Code lists:** CARC and RARC are maintained by X12 / WPC and **carry use
licenses.** Resolve licensing with X12 before shipping any code list in the
binary. This is a real, cheap-to-fix legal item that is easy to discover late.

### 6.3 Deadline engine

Modeled as a per-regime state machine, because the regimes genuinely differ and
missing a deadline is the most common reason a winnable appeal is lost.

**Commercial / ERISA / marketplace (v1):**
- Internal appeal: **180 days** from the date of the denial notice
- Plan must decide: within **45 days** (post-service claims)
- External review: **4 months** from the final internal determination *(45 CFR §147.136(d)(2)(i))*
- Urgent care: expedited review within **72 hours**; may run concurrently with internal appeal

**Medicare Advantage (v2):**
- Level 1 reconsideration: **60 days** from the denial notice (some plans allow 65)
- Plan decides: **30 days** standard, **72 hours** expedited
- Level 2: automatic forward to the Independent Review Entity
- Levels 3–5 (OMHA/ALJ → Medicare Appeals Council → federal district court): **60 days** at each step

**Medicare FFS:** redetermination within **120 days**.

Reminders escalate as the window closes: T-90 informational, T-30 actionable,
T-14 urgent, T-7 daily, T-2 final. **This is the notification stream that makes
the app worth keeping installed**, and it is honest — every alert is tied to a
real statutory clock and a specific dollar amount.

### 6.4 Appeal engine

Generates a packet, not a paragraph:

1. **Cover letter** — claim number, member ID, date of service, the specific
   dollar amount in dispute, the argument, and the plan's own language quoted with
   its section reference
2. **Statutory citation** — the regulation that applies to this denial type
3. **Phone script** — for the user who would rather call, with every field
   pre-filled and a place to log what the rep said and their reference number
4. **Certified-mail checklist** — where to send it, what to enclose, what to keep
5. **Follow-up scheduling** — auto-scheduled against the plan's own decision
   deadline, so silence from the insurer becomes an actionable event

Every appeal records its outcome. Which feeds:

---

## 7. The moat: the outcomes corpus

Each `AppealAction` writes back `outcome`, `outcome_amount`, and the argument IDs
used, keyed to `(payer, plan_type, CARC/RARC, service category, argument)`.

After a few thousand appeals the product can answer a question no competitor and
no general-purpose model can: **"For this insurer, on this denial code, which
argument actually gets overturned, and how often?"** That routes users to the
argument that wins rather than the argument that sounds good.

Properties that make this a real moat: it compounds with usage, it cannot be
scraped, it is the direct output of the core loop rather than a side project, and
it improves the headline metric (dollars recovered) rather than a vanity one.

Design consequence: **outcome capture is a first-class flow, not analytics.**
Prompt for it, make it one tap, and reward it by showing the user how their answer
improved the recommendation for the next person.

---

## 8. Core flows

### 8.1 Onboarding (target: under 4 minutes)
1. Household setup — who's covered
2. Plan capture — photograph the insurance card, upload or fetch the SBC
3. Plan-terms confirmation screen — the app shows what it extracted (deductible,
   OOP max, coinsurance) and the user corrects it. Establishes the mental model
   that this app *knows their plan*.
4. First document — "Have a bill that looks wrong? Start there." Time-to-first-
   finding is the activation metric.

### 8.2 The reconciliation loop (the daily-driver flow)
Capture → extract → auto-pair bill to EOB → run rules → present findings ranked by
dollars at stake → choose an action per finding → track to resolution.

A clean claim shows **"Correct — pay $X"** with the arithmetic shown. Confirming
correctness is a feature: it is what makes the app trustworthy when it does flag
something.

### 8.3 The denial event (the monetizing flow)
Denial detected → regime identified → deadline clock starts and is pinned to the
home screen → argument selected from the corpus → packet generated → user sends →
follow-up auto-scheduled → outcome captured.

### 8.4 The quiet-period flow (the retention flow)
When nothing is wrong, the app still has something true to say: position against
deductible and OOP max, YTD dollars recovered, open deadlines, and claims that are
processing. This is what a ledger has and a scanner does not.

---

## 9. Tech

- **Client:** Swift / SwiftUI, iOS 17+. VisionKit capture, Vision OCR.
- **On-device where it counts:** Apple's Foundation Models framework for
  extraction and drafting on-device — free Private Cloud Compute access under 2M
  first-time downloads, and it lets the privacy label say the health data never
  left the device. Fall back to a server model only for tasks that genuinely need
  frontier reasoning (novel appeal argument construction), and disclose it plainly.
- **Server:** the ledger, corpus, email ingestion, and deadline scheduler.
  Postgres. Encrypted at rest; documents in object storage with per-household keys.
- **App Intents from day one** — `LogBill`, `CheckDeadlines`, `WhatDoIOwe`. iOS 27
  deprecates SiriKit and drops intent-less apps from Siri's agentic compositions;
  this is also a discovery channel.
- **Notifications:** deadline escalation via scheduled local + push; Live Activity
  for an appeal in flight is a natural fit and worth prototyping.

---

## 10. Monetization

| Tier | Price | Contents |
|---|---|---|
| Free | $0 | 3 document scans/mo, reconciliation, findings shown with dollar amounts, deadlines tracked. **Letters locked.** |
| Ledger | **$19/mo or $149/yr** | Unlimited capture, full household, all letters and scripts, deadline escalation, position tracking, email ingestion |
| Ledger+ (v2) | **$29/mo** | Payer API connection, automatic claim sync, prior-auth tracking |
| Appeal Assist (v3) | **$75–125 per appeal** | Prepared, printed, certified-mailed on the user's behalf, with tracking |

**The paywall is placed where the value is proven, not before it.** The user sees
*"You are being overcharged $340"* for free; the letter that recovers it is the
purchase. Conversion should be excellent because the ROI is arithmetic and
already displayed.

**Apple mechanics, which materially change the model:**
- Subscriptions are digital goods → IAP, 30% (15% under Small Business Program).
- **Appeal Assist is a real-world service consumed outside the app** — printing,
  certified mail, filing. Under guideline 3.1.3/3.1.5 that must *not* use IAP, and
  carries **0% Apple commission.** Take it through Stripe.
- Post-*Epic* (2025), US-storefront apps may link out to external purchase methods
  with no entitlement required. Design the purchase flow to exploit this
  deliberately rather than stumbling into a rejection.

Annual pricing matters here: the underlying problem is annual (plan year,
deductible reset), and annual plans blunt the 30%-faster-churn pattern that
defines AI apps.

---

## 11. Open questions that gate the build

**Q1 — Payer API unit economics. This is the one that can kill v2.**
Reported historical aggregator pricing has run roughly **$200–450 per month per
connection** for enterprise scopes. At a $29/mo consumer price that is
catastrophically upside-down. Before committing to the API path, get written
consumer-scale pricing from Flexpa (their annual platform model may price very
differently from per-connection enterprise deals) and from 1upHealth. Design
around it if needed: periodic sync rather than continuous, connection as a
higher-priced tier, or one-time annual reconciliation.
**Decision gate: resolve before any v2 engineering. v1 does not depend on it.**

**Q2 — OCR accuracy on real EOBs.** Every payer's EOB layout differs and many are
hostile to parsing. Collect 100 real EOBs across the top 10 payers and measure
extraction accuracy per field before committing to the automated-pairing UX. If
accuracy on `patient_responsibility` is below ~95%, the confirm-and-correct step
becomes a primary flow rather than an edge case.

**Q3 — Does R1 actually fire often enough?** The entire v1 wedge assumes
provider-bill-exceeds-EOB is common. Validate against real documents before build,
not after.

**Q4 — X12 licensing** for CARC/RARC code lists (§6.2).

---

## 12. Compliance and legal posture

- **Not a HIPAA covered entity** as a direct-to-consumer tool — but the **FTC
  Health Breach Notification Rule explicitly covers health apps**, with enforcement
  precedent against GoodRx and Premom. Breach notice without unreasonable delay and
  no later than **60 days**; 500+ affected means notifying the FTC concurrently.
  Build the notification runbook before launch, not after an incident.
- **State health-privacy law** — Washington's My Health My Data Act carries a
  private right of action and is the binding constraint for consumer health apps;
  have counsel confirm the current multi-state picture before launch.
- **No legal or medical advice.** The app prepares documents and surfaces the
  user's own plan terms and public regulations. It does not advise. Language
  discipline throughout: *"Your plan's section 4.2 states…"*, never *"You should
  sue"* or *"This is medically necessary."*
- **No accusations of fraud.** Findings describe discrepancies and cite evidence.
  "Billed amount exceeds your EOB's patient responsibility by $340" — never
  "your provider is overbilling you."
- **Data minimization as product.** Retain documents only as long as the claim is
  open plus the appeal window; offer one-tap household deletion. This is also the
  marketing.

---

## 13. Metrics

**North star: dollars recovered per active household per year.** It is the only
number that is simultaneously the user's benefit, the retention driver, and the
justification for price.

| Stage | Metric | v1 target |
|---|---|---|
| Activation | % reaching first reconciled pair in session 1 | > 60% |
| Value proof | % of households with ≥1 finding in 30 days | > 45% |
| Conversion | Free → paid after first finding with dollars > $100 | > 25% |
| Engagement | Documents ingested per household per month | ≥ 3 |
| Retention | Month-6 retention | > 45% (vs 21.1% AI-app annual baseline) |
| Moat | Appeals with captured outcomes | > 70% |
| Efficacy | Appeal win rate vs the ~80.7% MA overturn benchmark | track from first 50 |

---

## 14. Roadmap

| Phase | Window | Ships |
|---|---|---|
| **0 — Validate** | 2 weeks | 100 real EOB/bill pairs; measure R1 fire rate and OCR accuracy; resolve Q1–Q4. **Kill or proceed.** |
| **1 — Reconcile** | 12 weeks | v1 scope (§4). TestFlight with 50 recruited households. |
| **1.5 — Ingest** | 4 weeks | Email forwarding, share extension, NCCI unbundling |
| **2 — Connect** | 8 weeks | Flexpa integration *(gated on Q1)*, Medicare Advantage regime, caregiver mode |
| **3 — Prior auth** | Q1 2027 | CMS-0057-F prior-auth data as it goes live; corpus-routed arguments; Appeal Assist |

---

## 15. Risks

| Risk | Severity | Response |
|---|---|---|
| Payer API pricing kills the connected tier | **High** | v1 is document-only by design and stands alone. Q1 resolved before v2 spend. |
| OCR accuracy makes reconciliation unreliable | **High** | Phase 0 measurement gate; confirm-and-correct UX as fallback |
| Incumbent or funded entrant builds the ledger version | Medium | The corpus is the durable asset — get to volume on appeals fast |
| A wrong deadline causes real user harm | **High** | Deadlines are deterministic, per-regime, conservative (always show the earliest applicable date), and never model-generated |
| False accusation damages a user's provider relationship | Medium | Deterministic rules only in v1; findings are described as discrepancies with citations |
| CMS-0057-F enforcement slips | Medium | v1 has no dependency on it; it is upside, not foundation |
| Apple rejection over health/medical claims | Low | No diagnosis, no treatment advice; positioned as financial/administrative |

**Kill criteria — be honest at the phase-0 gate:** if R1 fires on under 15% of
real bill/EOB pairs, or `patient_responsibility` extraction accuracy is below 90%,
the wedge is not real and the ledger thesis should be re-examined before writing
production code.

---

## Sources

- [CMS Interoperability and Prior Authorization Final Rule (CMS-0057-F) — CMS](https://www.cms.gov/priorities/burden-reduction/overview/interoperability/policies-and-regulations/cms-interoperability-and-prior-authorization-final-rule-cms-0057-f/cms-interoperability-and-prior-authorization-final-rule-cms-0057-f)
- [CMS-0057-F fact sheet — CMS Newsroom](https://www.cms.gov/newsroom/fact-sheets/cms-interoperability-prior-authorization-final-rule-cms-0057-f)
- [CMS-0057-F: 4 FHIR APIs due by 2027 — Health Samurai](https://www.health-samurai.io/articles/understanding-the-cms-0057-f-interoperability-and-prior-authorization-final-rule)
- [Patient Access API FAQ — CMS](https://www.cms.gov/priorities/burden-reduction/overview/interoperability/frequently-asked-questions/patient-access-api)
- [Internal Claims and Appeals and External Review — US DOL](https://www.dol.gov/agencies/ebsa/laws-and-regulations/laws/affordable-care-act/for-employers-and-advisers/internal-claims-and-appeals)
- [ACA claims and appeals regulation (PDF) — US DOL](https://www.dol.gov/sites/dolgov/files/ebsa/laws-and-regulations/laws/no-surprises-act/affordable-care-act-claims-appeals.pdf)
- [Appeals in Medicare health plans — Medicare.gov](https://www.medicare.gov/providers-services/claims-appeals-complaints/appeals/medicare-health-plans)
- [Claim Adjustment Reason Codes — X12](https://x12.org/codes/claim-adjustment-reason-codes)
- [Remittance Advice Remark Codes — X12](https://x12.org/codes/remittance-advice-remark-codes)
- [Guidance on Required RARC Codes (No Surprises Act) — CMS](https://www.cms.gov/cciio/programs-and-initiatives/other-insurance-protections/caa-nsa-rarc-codes.pdf)
- [Updated FTC Health Breach Notification Rule — FTC](https://www.ftc.gov/business-guidance/blog/2024/04/updated-ftc-health-breach-notification-rule-puts-new-provisions-place-protect-users-health-apps)
- [Complying with the FTC's Health Breach Notification Rule — FTC](https://www.ftc.gov/business-guidance/resources/complying-ftcs-health-breach-notification-rule-0)
- [Patient Access API — 1upHealth](https://1up.health/resources/patient-access-api/)
- [Flexpa — SMART App Gallery](https://apps.smarthealthit.org/app/flexpa)
- [Patient Access APIs in 2026 — Topflight](https://topflightapps.com/ideas/patient-access-apis/)
- [Patients deploy bots to battle health insurers — Stateline](https://stateline.org/2025/11/20/patients-deploy-bots-to-battle-health-insurers-that-deny-care/)
- [Apple external payment guideline changes post-Epic — Frankfurt Kurnit](https://technologylaw.fkks.com/post/102ixxm/top-5-things-app-developers-need-to-know-about-apples-new-guidelines-allowing-ex)
- [WWDC 2026 Foundation Models — Appbot](https://appbot.co/blog/apple-wwdc-2026-ai-foundation-model-update/)
