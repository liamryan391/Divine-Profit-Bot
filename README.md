# Divine Tool

Divine Tool is a local hybrid web app and daemon worker. It tracks a weekly or monthly GBP quota, records lawful income, accepts queued commands, runs a browser dashboard, and can run as a small background daemon that watches the quota state.

It does not perform fraud, spam, unauthorized access, market manipulation, or autonomous real-money trading. It is built to help the Creator pursue legitimate revenue and decide what to upgrade next.

Current release: `v2.6.1`. See [ROADMAP.md](ROADMAP.md) for phases, stages, and release gates.

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
python -m divine_tool approval draft invoice_reminder --target "Client Ltd" --amount 250 --due 2026-08-30 --invoice INV-001
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
- `divine_tool.sqlite3`: income ledger and exceptions.
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
- Hash-based navigation for overview, temples, strategies, imports, approvals, reports, and settings views.
- Workflow form validation, inline feedback notices, loading states, and safer confirmation prompts.
- Responsive layout and accessibility pass with skip navigation, visible focus states, live worker/status regions, semantic quota progress, reduced-motion support, and overflow-safe dense rows.
- Lead Pipeline board with lead intake, weighted value, stage movement, due follow-ups, and priority scoring tied to quota gap and strategy evidence.
- Conversion Tracking for booking leads into linked income, conversion rates, average deal size, strategy conversion evidence, and lost opportunity notes.
- Revenue Rules for turning pipeline, conversion, follow-up, loss, and opportunity evidence into explicit promote, pause, approval, or block decisions.
- Daemon rule evaluation history with per-temple pause and retire controls; rules never execute payments or external actions.

Run it with:

```powershell
python -m divine_tool web --port 8765
```

The dashboard and API share the same `.divine_tool/` state as the CLI and daemon.

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

The QA check verifies the generated HTML, CSS, and JS asset references, the responsive/accessibility hooks, and the `#/leads` Lead Pipeline route.

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

For HTTPS hosting behind a reverse proxy or cloud load balancer, set `DIVINE_PUBLIC_URL` and `DIVINE_COOKIE_SECURE=true` in the host environment. Keep API keys and payment credentials in environment variables only.

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

Reports include quota progress, missed-quota review, strategy ROI, priority opportunities, upgrade recommendations, and recent income entries.
