# Divine Tool

Divine Tool is a local hybrid web app and daemon worker. It tracks a weekly or monthly GBP quota, records lawful income, accepts queued commands, runs a browser dashboard, and can run as a small background daemon that watches the quota state.

It does not perform fraud, spam, unauthorized access, market manipulation, or autonomous real-money trading. It is built to help the Creator pursue legitimate revenue and decide what to upgrade next.

Current release: `v1.6.0`. See [ROADMAP.md](ROADMAP.md) for phases, stages, and release gates.

## Quick Start

```powershell
python -m divine_tool init
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
python -m divine_tool import .\income-export.csv --type payment --dry-run
python -m divine_tool external
python -m divine_tool approval draft invoice_reminder --target "Client Ltd" --amount 250 --due 2026-08-30 --invoice INV-001
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

The local web app provides:

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

Run it with:

```powershell
python -m divine_tool web --port 8765
```

The dashboard and API share the same `.divine_tool/` state as the CLI and daemon.

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
