# Divine Tool

Divine Tool is a local hybrid web app and daemon worker. It tracks a weekly or monthly GBP quota, records lawful income, accepts queued commands, runs a browser dashboard, and can run as a small background daemon that watches the quota state.

It does not perform fraud, spam, unauthorized access, market manipulation, or autonomous real-money trading. It is built to help the Creator pursue legitimate revenue and decide what to upgrade next.

Current release: `v3.5.0`. See [ROADMAP.md](ROADMAP.md) for phases, stages, and release gates.

## Quick Start

```powershell
python -m divine_tool init
python -m divine_tool account setup creator --recovery-email owner@example.com
python -m divine_tool web
```

Open the dashboard at:

```text
http://127.0.0.1:8765
```

Core CLI commands still work:

```powershell
python -m divine_tool status
python -m divine_tool quota set watchful 250 --period week
python -m divine_tool income add 75 --source "paid consultation" --strategy freelance_services
python -m divine_tool opportunities
python -m divine_tool roi
python -m divine_tool report --period week
python -m divine_tool temple summary
python -m divine_tool temple create "Product Temple" --template products
python -m divine_tool temple switch product_temple
python -m divine_tool import .\income-export.csv --type payment --dry-run
python -m divine_tool external
python -m divine_tool approval draft invoice_reminder --target "Client Ltd" --amount 250 --due 2026-09-14 --invoice INV-001
python -m divine_tool receivable add "Client Ltd" INV-001 750 --due 2026-09-14
python -m divine_tool receivable list --status overdue
python -m divine_tool receivable pay 1 250 --reference BANK-001
python -m divine_tool receivable remind 1
python -m divine_tool reconcile import .\bank-export.csv --provider bank --dry-run
python -m divine_tool reconcile list --status review
python -m divine_tool reconcile confirm 1 1 --note "Reference and amount verified"
python -m divine_tool follow-up status
python -m divine_tool follow-up configure --due-soon "3,0" --overdue "3,7,14,30"
python -m divine_tool follow-up run
python -m divine_tool follow-up client "Client Ltd" paused --until 2026-09-14 --reason "Account query"
python -m divine_tool recurring create "Support Retainer" "Client Ltd" CLIENT-SUPPORT 750 --kind retainer --cadence monthly --start 2026-09-14
python -m divine_tool recurring status
python -m divine_tool recurring run
python -m divine_tool recurring template 1 paused
python -m divine_tool forecast
python -m divine_tool account status
python -m divine_tool deploy preflight
python -m divine_tool upgrade
```

For non-GBP income, provide the GBP equivalent so the quota accounting is explicit:

```powershell
python -m divine_tool income add 0.01 --currency BTC --gbp-equivalent 420 --source "crypto sale"
```

## Background Mode

Run one daemon pass:

```powershell
python -m divine_tool daemon --once
```

Queue commands for the daemon:

```powershell
python -m divine_tool command add-income 25 --source "queued invoice"
python -m divine_tool command set-mood hungry
python -m divine_tool daemon --once
```

Run continuously:

```powershell
python -m divine_tool daemon --interval 300
```

On Windows, you can start it hidden from PowerShell:

```powershell
Start-Process python -ArgumentList "-m divine_tool daemon --interval 300" -WindowStyle Hidden
```

## Data

By default, state lives in `.divine_tool/`:

- `config.json`: quota, moods, channels, automation settings, and boundaries.
- `divine_tool.sqlite3`: income, leads, receivables, recurring templates and occurrences, payments, reconciliation evidence, follow-up cadences and outcomes, rules, accounts, events, worker-cycle history, and other durable application state.
- `commands.jsonl`: daemon command inbox.
- `commands.processed.jsonl`: processed daemon commands.
- `commands.failed.jsonl`: failed daemon commands.

Use another state directory with:

```powershell
python -m divine_tool --data-dir C:\path\to\state status
```

## Useful Commands

```powershell
python -m divine_tool mood set merciful
python -m divine_tool quota set hungry 1500 --period month
python -m divine_tool exception add --reason "payment processor outage" --until 2026-08-30
python -m divine_tool income list
python -m divine_tool config show
```

## Web App

The local web app is now a React, TypeScript, and Tailwind CSS dashboard served by the Python app. It provides:

- Quota, income, active module, and temple level cards.
- Period progress and remaining time.
- Active strategy recommendations.
- Divine configuration status.
- Temple log.
- Recent income.
- Income, quota, mood, and exception controls.
- Worker heartbeat indicator.
- Opportunity scoring by value, effort, risk, deadline fit, repeatability, probability, and recorded strategy evidence.
- Strategy ROI comparing current period, previous period, average conversion size, return per effort, and pause/push recommendations.
- Weekly and monthly report generation with quota results, missed-quota review, ROI summary, priority opportunities, upgrades, and income entries.
- Manual CSV imports for generic income, payment exports, and affiliate reports, with dry-run review and duplicate detection.
- Read-only external signals for fiat currency rates, GitHub project telemetry, optional payment summaries, and product analytics summaries.
- Human-approved action drafts for invoice reminders, outreach messages, and content prompts.
- Owner account setup, password login, protected dashboard/API routes, session logout, and role-aware account status.
- Recovery-ready auth screens with username reminder, password reset fallback, and optional owner recovery email.
- Hosted deployment preflight, container packaging, health checks, daemon service configuration, and state backups.
- Multi-temple profiles with separate quotas, moods, strategy templates, scoped income, and cross-temple rollups.
- Componentized React layout shell with shared cards, panels, fields, buttons, badges, toolbars, and dashboard sections.
- Hash-based navigation for overview, temples, strategies, leads, receivables, recurring revenue, cash forecasting, follow-ups, reconciliation, imports, approvals, reports, and settings views.
- Workflow form validation, inline feedback notices, loading states, and safer confirmation prompts.
- Responsive layout and accessibility pass with skip navigation, visible focus states, live worker/status regions, semantic quota progress, reduced-motion support, and overflow-safe dense rows.
- Lead Pipeline board with lead intake, weighted value, stage movement, due follow-ups, and priority scoring tied to quota gap and strategy evidence.
- Conversion Tracking for booking leads into linked income, conversion rates, average deal size, strategy conversion evidence, and lost opportunity notes.
- Revenue Rules for turning pipeline, conversion, follow-up, loss, and opportunity evidence into explicit promote, pause, approval, or block decisions.
- Receivables Pipeline for invoices and other money owed, due and overdue exposure, partial or full collections, and human-approved payment reminders.
- Double-counting protection for receivables linked to booked lead income, with explicit opt-in income recording for standalone collections.
- Payment Reconciliation for read-only bank/provider CSV evidence, explainable receivable suggestions, explicit confirmation or ignore decisions, duplicate protection, and a complete batch/decision audit trail.
- Follow-Up Cadences for configurable due-soon and overdue schedules, client pause and do-not-contact safeguards, approval-gated drafts, durable reminder history, and collection outcome measurements.
- Retainers And Recurring Revenue for temple-scoped retainers, subscriptions, and finite instalments with bounded receivable generation, pause/resume/end controls, expected billing, and renewal risk.
- Cash Forecasting for evidence-based best, expected, and delayed collection dates, timing confidence, and separate booked-income and collected-cash quota gaps.
- Daemon rule evaluation history with per-temple pause and retire controls; rules never execute payments or external actions.
- Bounded API bodies, persistent login throttling, auditable failed sign-ins, redacted server errors, strict hosted origins, CSRF checks, hardened cookies, and trusted-proxy HTTPS enforcement.
- Unified worker cycles with structured command, rule, approval, duration, and failure outcomes across daemon, CLI, and browser runs.
- Separate daemon liveness, readiness, and stale-worker signals with recent cycle history in the dashboard.
- Checksum-backed portable backups, offline verified restores, automatic pre-restore safety backups, and state integrity checks.
- Isolated recovery drills for persistent-volume restarts, claimed command files, failed migrations, and stale workers.
- An operational release gate covering aggregate correctness, concurrent web/daemon access, response-time budgets, hosted security, recovery, worker parity, and authenticated desktop/mobile workflows.

Run it with:

```powershell
python -m divine_tool web --port 8765
```

The dashboard and API share the same `.divine_tool/` state as the CLI and daemon.

## Receivables Pipeline

Stage 6.1 keeps billed revenue and collected cash visible without silently inflating quota income. A receivable linked to a converted lead inherits that lead's booked income reference, so later payments update collection progress but cannot be counted as income again. A standalone receivable may add a payment to the income ledger only when `--count-as-income` or the matching dashboard checkbox is explicitly selected.

Core API routes are `GET/POST /api/receivables`, `POST /api/receivables/payment`, `POST /api/receivables/{id}/reminder`, and `POST /api/receivables/{id}/status`. Reminder requests create pending approval drafts; they do not send external messages. Receivables, payments, approvals, and income remain scoped to the active temple.

## Payment Reconciliation

Stage 6.2 imports incoming bank and payment-provider CSV rows as local evidence only. It never signs in to, writes to, or changes an external financial account. Each row receives a temple-scoped fingerprint and explainable candidate scores based on native amount, GBP value, currency, invoice reference, client or payer words, and transaction date.

Every match still requires a human decision. Confirming a match records the imported evidence, receivable payment, balance update, and optional income entry in one SQLite transaction. Linked lead income cannot be counted again, repeated files do not duplicate transactions, and concurrent confirmation attempts cannot create a second payment.

```powershell
python -m divine_tool reconcile import .\bank-export.csv --provider bank --dry-run
python -m divine_tool reconcile import .\bank-export.csv --provider bank
python -m divine_tool reconcile list --status review
python -m divine_tool reconcile confirm 1 4 --count-as-income --note "Verified against invoice"
python -m divine_tool reconcile ignore 2 --reason "Internal transfer"
```

Core API routes are `GET /api/reconciliation`, `POST /api/reconciliation/import`, `POST /api/reconciliation/{id}/confirm`, and `POST /api/reconciliation/{id}/ignore`. CSV imports accept common date, amount, currency, reference, payer, and description headings; non-GBP rows require a GBP-equivalent column.

## Follow-Up Cadences

Stage 6.3 turns open receivables into a controlled reminder schedule. Each temple can configure days before due, days overdue, minimum contact gaps, maximum completed reminders, and the final overdue cutoff. The daemon and manual run command use the same idempotent processor, but they only create pending approval drafts; neither path sends an external message.

Client contact state can be active, paused, or do not contact. Suppressed steps remain in the reminder history without an approval draft, and a cleared temporary suppression can release the same step without duplicating it. Approving and manually completing a draft records contact time. Later payments update the latest completed reminder to partial or paid, cancel any stale active draft, and feed collection-time and outcome metrics.

```powershell
python -m divine_tool follow-up status
python -m divine_tool follow-up configure --due-soon "3,0" --overdue "3,7,14,30" --minimum-gap 2 --max-reminders 6 --stop-after 60
python -m divine_tool follow-up client "Client Ltd" do_not_contact --reason "Client requested no reminders"
python -m divine_tool follow-up run
python -m divine_tool follow-up outcome 1 payment_promised --note "Payment promised Friday"
```

Core API routes are `GET /api/follow-ups`, `POST /api/follow-ups/cadence`, `POST /api/follow-ups/client`, `POST /api/follow-ups/run`, and `POST /api/follow-ups/{id}/outcome`. All routes are protected by the same owner authentication policy as receivables and approvals.

## Retainers And Recurring Revenue

Stage 6.4 creates scheduled internal receivables from temple-scoped retainer, subscription, and instalment templates. Weekly, monthly, quarterly, and yearly schedules retain their original calendar anchor, including month-end dates. Generation opens only inside the configured lead window, runs atomically, and is capped at 12 occurrences per template in one cycle.

Generated items enter the ordinary Receivables Pipeline. They do not charge a customer, move money, record a payment, or increase quota income. Payment evidence, reconciliation, follow-up approval, and booked-income double-counting protections continue to apply. Pausing stops future generation, resuming keeps the schedule, and ending is permanent while preserving history.

```powershell
python -m divine_tool recurring create "Support Retainer" "Client Ltd" CLIENT-SUPPORT 750 --kind retainer --cadence monthly --start 2026-09-14 --renewal 2027-09-14
python -m divine_tool recurring create "Implementation Plan" "Client Ltd" CLIENT-PLAN 400 --kind instalment --cadence monthly --start 2026-09-14 --occurrences 4
python -m divine_tool recurring status
python -m divine_tool recurring run
python -m divine_tool recurring template 1 paused
python -m divine_tool recurring template 1 active
python -m divine_tool recurring template 1 ended
```

Core API routes are `GET /api/recurring-revenue`, `POST /api/recurring-revenue/templates`, `POST /api/recurring-revenue/run`, and `POST /api/recurring-revenue/templates/{id}/status`. Dashboard and report summaries distinguish normalized monthly recurring value, expected 30-day and 90-day billings, finite remaining value, generated receivables, and renewal risk from collected cash.

## Cash Forecasting

Stage 6.5 computes a read-only cash forecast from open receivable due dates, completed-payment timing, and future recurring schedules. Client history is preferred, temple-wide history is the fallback, and a disclosed seven-day expected delay is used when no completed-payment evidence exists. The delayed band uses upper timing evidence plus a buffer; observed delays are capped from 30 days early to 120 days late so one extreme payment cannot dominate the forecast.

Every item shows best, expected, and delayed dates plus a qualitative timing-confidence label and its evidence basis. Confidence describes the support for the date estimate, not whether a client will pay. Generated receivables appear once as issued balances, while future recurring occurrences remain explicitly unissued and unbooked.

```powershell
python -m divine_tool forecast
python -m divine_tool forecast --horizon 30
python -m divine_tool forecast --format json
```

The protected API route is `GET /api/cash-forecast?horizon=90`, and the dashboard route is `#/forecast`. Forecast calculations never create income, payments, receivables, or recurring occurrences. Booked quota progress continues to come from the income ledger, while collected cash comes only from recorded receivable payments.

## Database Reliability

Every application connection uses SQLite WAL mode, enforces foreign keys, and waits up to 10 seconds for a contested write lock. This lets the threaded web server and daemon share the same state database without failing immediately during short overlapping writes.

The schema is upgraded through ordered, transactional migrations. Applied versions are recorded in `schema_migrations` and mirrored in SQLite's `user_version`; ordinary requests check the version without replaying table setup. A failed migration rolls back its schema and data changes and does not advance the recorded version.

The hosted preflight verifies WAL, the busy timeout, foreign-key integrity, command-log integrity, and the current schema version. Back up and verify the state before upgrading a hosted instance:

```powershell
python -m divine_tool deploy backup
python -m divine_tool deploy verify-backup ".divine_tool/backups/<backup-file>.zip"
python -m divine_tool deploy preflight
```

Each new archive carries file sizes and SHA-256 checksums. The backup command reads existing state without initializing or migrating its schema, so it can safely capture a pre-upgrade database first. Legacy archives without checksums remain restorable only after their ZIP, JSON, SQLite, foreign-key, and schema checks pass with a warning.

## Dashboard Performance

The dashboard loads one request-scoped snapshot on startup and after successful mutations. Quota status, opportunities, ROI, lead scoring, conversions, receivables, recurring revenue, cash forecasting, reconciliation, follow-up cadences, revenue rules, and temple rollups reuse the same snapshot inputs instead of recursively rebuilding each other.

The 10-second browser poll calls only `GET /api/worker/status`. Full weekly and monthly reports are generated only through `GET /api/report?period=week|month` when requested.

Response-time budgets for the local reference environment:

- Complete dashboard payload: median at or below 250 ms with 120 leads, 180 income rows, and 24 revenue rules.
- Worker status poll: median at or below 50 ms over local HTTP.

Benchmark recorded on 27 August 2026: the representative dashboard payload improved from about 330 ms to 61 ms median, and worker polling measured about 14 ms median over HTTP. The automated suite rebuilds the representative fixture and enforces the dashboard budget.

## Operational Release Gate

Release `v3.0.0` closes Backend Roadmap 3.0 for protected local operation. The release candidate passed all 37 automated tests, the production frontend build and static QA, Python compilation, Docker Compose validation, deployment preflight, and all five isolated recovery drills on 31 August 2026.

The representative 120-lead and 24-rule benchmark measured a 64.35 ms median dashboard snapshot against a 250 ms budget and a 3.13 ms median worker-status query against a 50 ms budget. Authenticated browser verification also completed the lead-to-booked-income, revenue-rule, report, worker-cycle, and approval workflows, then rendered every primary route at desktop and 390 x 844 mobile widths without document overflow.

This gate validates the application and local reference environment. A public host must still pass preflight with its real HTTPS origin, proxy, cookie, persistent-volume, backup, and credential settings before exposure.

Stage 6.1 release `v3.1.0` passed all 39 automated tests, the production frontend build and static QA, Python compilation, Docker Compose validation, schema-v8 deployment preflight, and SQLite integrity checks on 31 August 2026. Isolated browser verification created a receivable, recorded a partial collection with explicit income treatment, queued a human-approved reminder, rendered every primary route at 390 x 844 without document overflow, and produced no console warnings or errors.

Stage 6.2 release `v3.2.0` passes all 42 automated tests, including exact and ambiguous scoring, duplicate imports, authenticated decisions, audit history, and concurrent confirmation protection. The production dashboard build and static QA also pass against schema v9; deployment and visual evidence are recorded in the Stage 6.2 roadmap gate.

Stage 6.3 release `v3.3.0` passes all 45 automated tests, including cadence idempotency, suppression release, approval gating, payment-linked outcomes, stale-draft cancellation, reporting, and authenticated API coverage. The production dashboard build and static QA pass against schema v10; deployment and visual evidence are recorded in the Stage 6.3 roadmap gate.

Stage 6.4 release `v3.4.0` passes all 48 automated tests, including month-end anchoring, bounded and concurrent idempotent generation, lifecycle controls, expected-value and renewal-risk visibility, authenticated API operations, worker parity, and explicit no-payment/no-income assertions. Production build, static QA, Python compilation, Docker Compose validation, schema-v11 preflight, integrity checks, and authenticated desktop/mobile review pass; all 12 routes remain overflow-free at 390 x 844 with a clean browser console.

Stage 6.5 release `v3.5.0` passes all 51 automated tests, including historical timing bands, partial-payment balances, no-write guarantees, booked-versus-collected accounting, recurring-schedule treatment, temple isolation, authenticated API access, and CLI/report parity. Production build, static QA, Python compilation, Docker Compose validation, schema-v11 preflight, integrity checks, and authenticated desktop/mobile review pass; all 13 routes remain overflow-free at 390 x 844 with a clean browser console.

## Worker Operations

The continuous daemon, `daemon --once`, and the dashboard's Run Worker Cycle action all use the same cycle implementation. Every cycle processes claimed commands, generates due recurring receivables inside bounded windows, evaluates and records active revenue rules, reviews due follow-up cadence steps for every temple, counts approval gates and pending approvals, and stores its duration and failures in SQLite.

Cycle sources remain distinct for honest monitoring:

- `daemon` cycles update the background daemon's liveness and readiness.
- `cli` cycles prove a manual run completed without pretending the daemon is online.
- `browser` cycles do the same for the authenticated dashboard action.

`GET /api/worker/status` returns the current daemon heartbeat, independent liveness and readiness objects, the stale threshold, the latest daemon cycle, and recent cycles from every source. `GET /api/health` keeps web-service liveness and readiness separate from the nested worker signals. The Worker Operations panel shows the same state and recent cycle outcomes.

Only one cycle can own the shared command and rule pipeline at a time. A concurrent browser or CLI request receives a busy response instead of duplicating work. Individual bad commands are preserved in `commands.failed.jsonl`; the cycle completes as `partial`, records the failure, and continues processing other commands.

The daemon service uses an `unless-stopped` restart policy. A command inbox claimed by a cycle remains in a `commands.processing.*.jsonl` file until processing completes, and the next cycle resumes any claimed file left by an interrupted process. If a recorded `running` cycle outlives the configured stale window, the next cycle marks it `interrupted` before starting and writes a recovery event to the Temple Log.

## API And Authentication Security

The web boundary rejects oversized bodies before reading them. Ordinary JSON requests are limited to 256 KiB; income and reconciliation CSV request envelopes are limited to 5 MiB and decoded CSV content to 4 MiB. Both React importers check the same 4 MiB file limit before reading a selected file.

Failed sign-ins are tracked by both normalized username and client source. Five failures within 15 minutes trigger a 15-minute lockout by default, returned as HTTP `429` with `Retry-After`. Failures and throttled attempts are written to the authenticated Temple Log without passwords or session tokens. A successful sign-in or local password reset clears pending throttle rows; the audit events remain.

Unexpected server exceptions return only a generic message and correlation request ID. The internal server log retains the matching request ID, method, path, client source, and traceback for diagnosis. JSON responses and static assets also set a restrictive content security policy, framing protection, permissions policy, and related browser security headers.

Hosted mode uses this policy:

- Session cookies are `HttpOnly`, `Secure`, and `SameSite=Strict`.
- Unsafe requests must carry an exact approved `Origin` or `Referer`; cross-site fetches are rejected and CORS is not enabled.
- Application traffic must arrive over HTTPS. Only a loopback `/api/health` probe may use direct HTTP.
- Forwarding headers are ignored unless `DIVINE_TRUST_PROXY=true`.
- A trusted proxy must strip and overwrite `X-Forwarded-For` and `X-Forwarded-Proto` and must be the only network path to the application port.
- Production mode fails closed to secure-cookie, origin-check, and HTTPS defaults even when individual toggles are omitted.

Required hosted settings:

```text
DIVINE_DEPLOYMENT_MODE=production
DIVINE_PUBLIC_URL=https://divine.example
DIVINE_ALLOWED_ORIGINS=https://divine.example
DIVINE_COOKIE_SECURE=true
DIVINE_CSRF_REQUIRE_ORIGIN=true
DIVINE_TRUST_PROXY=true
DIVINE_FORCE_HTTPS=true
```

`python -m divine_tool deploy preflight --host 0.0.0.0` blocks a hosted release when the canonical HTTPS origin, secure cookie, origin check, proxy trust, or transport policy is incomplete.

For frontend development, run the Python web app for the API and use the Vite dev server for the browser UI:

```powershell
npm install
npm run dev
```

Compile the production dashboard into `divine_tool/static/` with:

```powershell
npm run build
```

Run the static frontend QA check after a build:

```powershell
npm run qa:static
```

The QA check verifies the generated HTML, CSS, and JS asset references, responsive/accessibility hooks, and the Lead, Receivables, Recurring, Forecast, Follow-Up, and Reconciliation workflows.

## Lead Pipeline

Phase 5 ships the `#/leads` workflow for turning legitimate opportunities into tracked revenue. Leads are scoped to the active temple and scored against quota pressure, expected value, probability, follow-up urgency, stage, and strategy evidence.

Current pipeline tools:

- Pipeline board across new, contacted, qualified, proposal, won, and lost stages.
- Lead intake form for contact, source, offer, value, probability, strategy, next action, follow-up date, and notes.
- Priority lead queue.
- Due follow-up queue.
- One-click stage movement for active leads.
- Weighted value and open-lead metrics.
- Conversion Tracking panel for recording qualified, proposal, or won leads as booked income.
- Linked income rows with lead IDs, conversion rate, win rate, linked revenue, average deal size, and lost value.
- Strategy conversion evidence and recent won/lost notes for the next prioritization pass.
- Complete lead, stage, value, due-follow-up, and revenue-rule aggregates even when the dashboard displays only the first page of rows.
- Pagination metadata with total, returned, next, and previous offsets for bounded lead API pages.

Lead API shape:

- `GET /api/leads?stage=&limit=&offset=`
- `POST /api/leads`
- `PATCH /api/leads/{id}`
- `POST /api/leads/{id}/note`
- `POST /api/leads/{id}/advance`
- `GET /api/leads/summary?limit=&offset=`
- `GET /api/conversions/summary`
- `POST /api/conversions/record`
- `POST /api/conversions/link`
- `GET /api/revenue-rules?status=&limit=`
- `GET /api/revenue-rules/summary`
- `POST /api/revenue-rules`
- `PATCH /api/revenue-rules/{id}`
- `POST /api/revenue-rules/{id}/status`

Revenue Rules are evaluated against recorded evidence and surfaced as guidance, approval gates, pauses, or blocks. The daemon records evaluation snapshots for auditability, but it does not send messages, move money, trade assets, or perform another external action from a rule.

## Accounts And Authentication

The web dashboard is protected once an owner account exists. On a fresh state directory, create the owner from the browser setup screen or from the CLI:

```powershell
python -m divine_tool account setup creator --recovery-email owner@example.com
python -m divine_tool account status
python -m divine_tool account list
python -m divine_tool account reset-password creator
```

Passwords are stored as salted hashes, and browser sessions are stored as hashed local session tokens. The API blocks dashboard data, income writes, imports, approvals, and configuration changes until the owner is signed in.

If you forget the local username, list configured accounts with:

```powershell
python -m divine_tool account list
```

The tool cannot display an existing password because passwords are not stored in recoverable form. The login screen and Settings view surface the safe local fallback commands, and Settings can store an optional recovery email label on the owner profile.

If you know the username but forgot the password, reset it with:

```powershell
python -m divine_tool account reset-password test
```

Secret policy: keep external credentials in environment variables, not config files. Current supported variables are `DIVINE_STRIPE_SECRET_KEY`, `DIVINE_GITHUB_TOKEN`, and `GITHUB_TOKEN`.

## Hosted Deployment

The production path is a two-service container setup:

- `web`: serves the dashboard and API.
- `daemon`: runs the background worker against the same persistent state volume.

Prepare local deployment settings:

```powershell
Copy-Item .env.example .env
python -m divine_tool account setup creator --recovery-email owner@example.com
python -m divine_tool deploy preflight --host 0.0.0.0
```

Run with Docker Compose:

```powershell
docker compose up --build -d
docker compose ps
```

Check the hosted service:

```powershell
python -m divine_tool deploy healthcheck --url http://127.0.0.1:8765/api/health
```

Create a portable backup of config, SQLite state, and command logs:

```powershell
python -m divine_tool deploy backup
```

For HTTPS hosting behind a reverse proxy or cloud load balancer, configure every variable in the API and Authentication Security section before starting the public service. Docker Compose publishes the application port on `127.0.0.1` by default so a host reverse proxy can reach it without exposing the trusted-header boundary directly; change `DIVINE_BIND_ADDRESS` only when the surrounding network provides an equivalent restriction. Keep API keys and payment credentials in environment variables only.

## Backup Restore And Recovery

Restore is an offline operator action and is intentionally unavailable through the web API. Stop both services, verify the archive, restore it, then start and check the services:

```powershell
docker compose stop web daemon
python -m divine_tool deploy verify-backup ".divine_tool/backups/<backup-file>.zip"
python -m divine_tool --data-dir .divine_tool deploy restore ".divine_tool/backups/<backup-file>.zip" --confirm
docker compose up -d
python -m divine_tool deploy healthcheck --url http://127.0.0.1:8765/api/health
python -m divine_tool deploy preflight
```

When replacing existing state, restore first creates and prints a safety-backup path. The archive is extracted, checked, and migrated in a disposable staging directory before live files change. A handled replacement failure rolls the original files back.

Run read-only integrity checks or the complete isolated drill suite at any time:

```powershell
python -m divine_tool deploy integrity
python -m divine_tool deploy drill
```

The drill takes a verified backup and proves round-trip restore, fresh-process persistence against the same volume, recovery of a claimed command file, transactional migration rollback, and stale-worker recovery. It does not alter the active ledger. For a real container restart drill, record `deploy integrity`, run `docker compose restart web daemon`, then repeat the integrity and health checks.

If an operating-system interruption leaves `.divine_tool/.restore-in-progress.json`, keep both services stopped and read its `safety_backup` path. Restore that archive with `--confirm --skip-safety-backup`, run `deploy integrity`, and only then restart services.

## Strategy Scoring

Income can be tagged to a configured strategy:

```powershell
python -m divine_tool income add 120 --source "product sale" --strategy digital_product
```

The dashboard ranks strategies using:

- expected value against the remaining quota
- fit for the current deadline
- effort level
- risk level
- repeatability
- probability
- income already produced by that strategy

## Multi-Temple Expansion

Use temples when you want separate revenue projects with their own quotas, moods, and strategy lists:

```powershell
python -m divine_tool temple list
python -m divine_tool temple create "Product Temple" --template products
python -m divine_tool temple create "Client Services" --template services
python -m divine_tool temple switch product_temple
python -m divine_tool temple summary
```

Available templates are `balanced`, `services`, and `products`. Existing state migrates into the default `main` temple. Normal commands such as `income add`, `quota set`, `mood set`, imports, reports, and approvals operate on the active temple.

The dashboard includes a Temple Switchboard, an active-temple selector, per-temple progress rows, and an overall cross-temple earned/quota summary.

## Manual Imports

Use import mode when a bank, payment processor, or affiliate platform gives you a CSV export:

```powershell
python -m divine_tool import .\income-export.csv --type payment --dry-run
python -m divine_tool import .\income-export.csv --type payment
python -m divine_tool import .\affiliate-report.csv --type affiliate
```

Supported import types are `generic`, `payment`, and `affiliate`. The importer accepts common column names such as `date`, `paid_at`, `amount`, `net_amount`, `commission`, `currency`, `gbp_equivalent`, `source`, `description`, `program`, `strategy`, `channel`, `transaction_id`, `reference`, and `sale_id`.

Dry runs show rows that are ready, duplicate, or skipped without writing to the ledger. Non-GBP rows need a GBP equivalent column so quota accounting stays explicit.

## External Connections

Refresh read-only external signals from the CLI:

```powershell
python -m divine_tool external
python -m divine_tool external --format json
```

The dashboard also has an External Signals panel with a manual refresh button. The current connector set includes:

- Currency rates through Frankfurter, using public no-key GBP fiat rates.
- GitHub telemetry for `liamryan391/Divine-Profit-Bot`, including recent commits, open issues, open PRs, and stars.
- Payment summaries through either a local summary file or Stripe balance transactions when explicitly enabled.
- Product analytics summaries from a local JSON export when configured.

Payment connectors do not store secrets in the project. To try Stripe later, set `integrations.payments.enabled` to `true` in `.divine_tool/config.json` and provide a restricted key through the `DIVINE_STRIPE_SECRET_KEY` environment variable.

## Human-Approved Actions

Queue drafts locally, review them, and only mark them complete after a human has used them manually:

```powershell
python -m divine_tool approval draft invoice_reminder --target "Client Ltd" --amount 250 --due 2026-08-30 --invoice INV-001 --strategy freelance_services
python -m divine_tool approval draft outreach --target "Acme Lead" --offer "a fast revenue dashboard" --context "manual reporting is slow"
python -m divine_tool approval draft content_prompt --topic "profitable dashboard habits" --goal "book a paid consultation" --channel blog
python -m divine_tool approval list --show-body
python -m divine_tool approval approve 1
python -m divine_tool approval complete 1 --note "Sent manually"
```

Approving a draft does not send email, messages, payments, trades, or external requests. It only records that the draft is approved for manual use.

## Strategy ROI

Use ROI mode to review which channels deserve more attention:

```powershell
python -m divine_tool roi
```

The ROI view compares the current period against the previous period, shows recent conversion notes, estimates return per effort unit, and recommends whether each strategy should be pushed, watched, or paused.

## Reports

Generate a Markdown report:

```powershell
python -m divine_tool report --period week
python -m divine_tool report --period month --output monthly-report.md
```

Reports include quota progress, missed-quota review, strategy ROI, receivables, payment reconciliation exposure, priority opportunities, upgrade recommendations, and recent income entries.
