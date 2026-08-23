# Divine Profit Bot Roadmap

This roadmap defines how the project moves from the current command-line foundation into the hybrid web app plus daemon worker: the Digital Temple dashboard and the Divine Income Engine.

## Version Rules

- `v0.x`: foundation work before the full hybrid product is operational.
- `v1.0.0`: first complete operational release with web dashboard, API, daemon worker, persistent state, and safe local operation.
- `v1.1.0`, `v1.2.0`, `v1.3.0`, `v1.4.0`, `v1.5.0`, `v1.6.0`: meaningful feature upgrades after `v1.0.0`, such as new modules, reports, integrations, or dashboards.
- `v1.1.1`, `v1.1.2`: patch releases for bug fixes, small polish, reliability improvements, or security fixes.
- `v2.0.0`: account protection and authenticated local operation.
- `v2.1.0`: hosted deployment packaging, preflight, monitoring, and backups.
- `v2.2.0`: multi-temple expansion with separate profiles and cross-temple reporting.
- `v2.3.0` or later: growth operations such as leads, conversion tracking, and revenue pipelines.

## Current Status

Current version: `v2.2.0`.

Completed:

- Local quota engine.
- GBP income ledger.
- Mood-based weekly/monthly targets.
- Exceptions for missed quota windows.
- Background command inbox.
- Basic daemon loop.
- Upgrade recommendations.
- Unit tests for the core flow.
- Local API service.
- Digital Temple dashboard.
- Browser controls for income, quotas, moods, and exceptions.
- Worker heartbeat indicator.
- Browser-based temple log.
- API test for the web income flow.
- Opportunity scoring with strategy evidence.
- Strategy ROI with current-vs-previous comparison and pause recommendations.
- Weekly and monthly report generation.
- Manual CSV importers for generic income, payment exports, and affiliate reports.
- Dry-run import review and duplicate detection.
- Read-only external signals for fiat currency rates, GitHub project telemetry, optional payment summaries, and product analytics summaries.
- Human-approved action drafts for invoice reminders, outreach messages, and content prompts.
- Approval queue with approve, reject, and manual-complete states.
- Owner account setup, password login, hashed sessions, protected dashboard/API routes, and role-aware account status.
- Secret-management guidance for future hosted integrations.
- Hosted deployment preflight checks.
- Docker and Docker Compose packaging for web plus daemon services.
- Environment-based production configuration.
- Healthcheck command for hosted monitoring.
- Portable state backups for config, SQLite data, and command logs.
- Multi-temple profiles with the existing state migrated into `main`.
- Separate temple quota, mood, strategy template, income, exception, event, and approval contexts.
- CLI temple list/create/switch/summary commands.
- Dashboard Temple Switchboard and active temple selector.
- Cross-temple quota rollups.

## Phase 0: Foundation

Goal: establish the lawful money-tracking core and prove the core rules work.

### Stage 0.1: Core Ledger

Status: complete.

Deliverables:

- Income entries with source notes.
- GBP quota accounting.
- Non-GBP income support with explicit GBP equivalent.
- SQLite persistence.

Exit gate:

- Income can be recorded and counted toward the current period.

### Stage 0.2: Mood, Quota, And Exceptions

Status: complete.

Deliverables:

- Configurable moods.
- Weekly or monthly quota periods.
- Mercy exceptions for valid missed-quota circumstances.
- Consequence states without destructive behavior.

Exit gate:

- The tool can report whether the quota is satisfied, at risk, or covered by an exception.

### Stage 0.3: Command Inbox And Daemon Loop

Status: complete.

Deliverables:

- Queueable commands.
- One-pass daemon mode.
- Continuous daemon mode.
- Processed and failed command logs.

Exit gate:

- A queued command can be processed by the daemon and reflected in status.

## Phase 1: Hybrid App V1

Goal: make the project a usable local web application backed by the existing engine.

### Stage 1.1: Local API Service

Status: complete.

Deliverables:

- HTTP API for status, income, quotas, moods, exceptions, opportunities, upgrades, and logs.
- Shared access to the existing SQLite state.
- Input validation and clear error responses.
- Health endpoint for the daemon and frontend.

Exit gate:

- The web app can get and update all core state through the API.

### Stage 1.2: Digital Temple Dashboard

Status: complete.

Deliverables:

- Dark dashboard matching the reference direction.
- Current quota card.
- Income this period card.
- Active module card.
- Temple level card.
- Quota progress bar.
- Time remaining.
- Active strategies.
- Divine configuration.
- Temple log.

Exit gate:

- A user can understand quota health, income progress, and active strategy state from the first screen.

### Stage 1.3: Control Panel

Status: complete.

Deliverables:

- Add income form.
- Set quota form.
- Change mood control.
- Add exception form.
- Queue command control.
- Start/stop guidance for background mode.

Exit gate:

- The user can operate the core tool from the web app without using the CLI for normal tasks.

### Stage 1.4: Worker Heartbeat

Status: complete.

Deliverables:

- Daemon heartbeat stored in state.
- Last-run timestamp.
- Worker status indicator in the dashboard.
- Failed command visibility.
- Basic recovery messages.

Exit gate:

- The dashboard can show whether the background worker is alive and when it last checked in.

### Stage 1.5: V1 Packaging

Status: complete.

Deliverables:

- One command to run the API and frontend locally.
- One command to run the daemon.
- Clear environment/config defaults.
- Updated README.
- Tests for API and core flows.

Exit gate:

- A fresh clone can run the full local hybrid app with documented commands.

## V1.0.0 Ready Criteria

The project is `v1.0.0` ready when all of these are true:

- Web dashboard runs locally.
- API service runs locally.
- Daemon worker runs and reports heartbeat.
- Income can be added from the web UI.
- Quota, mood, and exceptions can be managed from the web UI.
- Temple log is visible in the web UI.
- State persists after restart.
- The README explains setup, run, and operation.
- Tests pass.
- No module performs unlawful, deceptive, spammy, unauthorized, or autonomous high-risk money movement.

Status: ready.

## Phase 2: V1.1 Revenue Intelligence

Goal: improve the engine after the basic temple is operational.

### Stage 2.1: Opportunity Scoring

Status: complete.

Deliverables:

- Score revenue opportunities by expected value, effort, risk, deadline fit, and repeatability.
- Show the top recommended next action.
- Track which strategies produce real income.

Release target:

- `v1.1.0`.

Release status: shipped.

### Stage 2.2: Strategy ROI

Status: complete.

Deliverables:

- Track income by strategy.
- Show conversion notes.
- Compare revenue channels over time.
- Recommend low-return channels to pause.

Release target:

- `v1.2.0`.

Release status: shipped.

### Stage 2.3: Report Generation

Status: complete.

Deliverables:

- Weekly report.
- Monthly report.
- Missed-quota review.
- Upgrade recommendation summary.

Release target:

- `v1.3.0`.

Release status: shipped.

## Phase 3: Integrations

Goal: connect real-world sources while keeping human approval for sensitive actions.

### Stage 3.1: Manual Importers

Status: complete.

Deliverables:

- CSV import for income.
- Bank/payment export import.
- Affiliate report import.
- Duplicate detection.

Release target:

- `v1.4.0`.

Release status: shipped.

### Stage 3.2: External Data Connections

Status: complete.

Deliverables:

- Optional currency-rate lookup.
- Optional payment processor read-only summaries.
- Optional GitHub/project telemetry.
- Optional product analytics summary file.

Release target:

- `v1.5.0`.

Release status: shipped.

### Stage 3.3: Human-Approved Actions

Status: complete.

Deliverables:

- Draft invoice reminders.
- Draft outreach messages.
- Draft content prompts.
- Approval queue before anything external is sent.

Release target:

- `v1.6.0`.

Release status: shipped.

## Phase 4: V2 Production Temple

Goal: turn the local tool into a production-grade application.

### Stage 4.1: Authentication And Accounts

Status: complete.

Deliverables:

- User login.
- Protected dashboard.
- Role-aware settings.
- Secret management.

Release target:

- `v2.0.0`.

Release status: shipped.

### Stage 4.2: Hosted Deployment

Status: complete.

Deliverables:

- Production container build.
- Persistent hosted state volume for the SQLite database.
- Background daemon service hosting.
- Health endpoint plus deployment healthcheck command.
- Portable backups.
- Production environment template.

Release target:

- `v2.1.0`.

Release status: shipped.

### Stage 4.3: Multi-Temple Expansion

Status: complete.

Deliverables:

- Multiple projects or temples.
- Separate quota profiles.
- Strategy templates.
- Cross-temple reporting.
- Scoped ledgers, exceptions, logs, and approval queues.
- Dashboard switching.

Release target:

- `v2.2.0`.

Release status: shipped.

## Phase 5: Growth Operations

Goal: help each temple convert legitimate opportunities into tracked revenue.

### Stage 5.1: Lead Pipeline

Status: future.

Deliverables:

- Lead records per temple.
- Offer, value, source, and next-step fields.
- Follow-up dates.
- Pipeline stages.
- Priority scoring tied to quota gaps.

Release target:

- `v2.3.0`.

### Stage 5.2: Conversion Tracking

Status: future.

Deliverables:

- Link income entries back to leads, drafts, imports, or strategies.
- Conversion rate summaries.
- Average deal size by temple and strategy.
- Lost-opportunity notes.

Release target:

- `v2.4.0` or later.

### Stage 5.3: Revenue Rules

Status: future.

Deliverables:

- Configurable safe automation rules.
- Human approval gates for any external action.
- Rule run logs.
- Disable switches per temple.

Release target:

- `v2.5.0` or later.

## Operational Definition

The tool is fully operational for protected local use when the Creator can:

- Open the dashboard.
- Sign in with the local owner account.
- See the current quota and deadline.
- Add income.
- Change mood and quota.
- Add exceptions.
- Import income from CSV exports.
- Refresh read-only external data signals.
- Draft and review human-approved actions before manual use.
- See live daemon health.
- Review temple logs.
- Receive practical next-action recommendations.
- Restart the app without losing state.
- Run the web and daemon services on a host with persistent state.
- Check production readiness before public exposure.
- Take a portable backup of the state directory.
- Create and switch between multiple temples.
- Keep separate ledgers and approval queues per temple.
- Review aggregate quota progress across all temples.

## Recommended Next Build Step

Build Phase 5, Stage 5.1 next:

- Add a lead pipeline per temple.
- Track offer, value, source, stage, next step, and follow-up date.
- Score leads against the active quota gap.
- Connect completed leads to income entries.

That turns the multi-temple operating system into a real growth pipeline.
