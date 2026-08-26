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
- `v2.3.0`: React, TypeScript, and Tailwind frontend foundation for the Digital Temple dashboard.
- `v2.3.1`: local owner password reset support for forgotten passwords.
- `v2.3.2`: shared React component system and layout shell for the dashboard.
- `v2.3.3`: primary navigation and information architecture across focused dashboard views.
- `v2.3.4`: auth UX and account recovery readiness.
- `v2.3.5`: workflow form validation, inline feedback, and safer actions.
- `v2.3.6`: responsive design, accessibility, keyboard focus, and overflow hardening.
- `v2.3.7`: visual QA readiness, static frontend checks, and Lead Pipeline route/API planning.
- `v2.4.0` or later: growth operations such as leads, conversion tracking, and revenue pipelines.

## Current Status

Current version: `v2.3.7`.

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
- Patch `v2.2.1`: fixed dashboard stylesheet/script asset paths that could leave the website on a blank screen.
- Roadmap 2.0 Stage 2.0.1: React, TypeScript, Tailwind CSS, and Vite frontend foundation while preserving the existing Python API and daemon.
- Patch `v2.3.1`: added a local owner password reset command that rotates the password hash and signs out old sessions.
- Roadmap 2.0 Stage 2.0.2: split the dashboard into reusable React components and a stronger layout shell.
- Roadmap 2.0 Stage 2.0.3: added primary navigation, focused dashboard views, and refresh-safe hash view state.
- Roadmap 2.0 Stage 2.0.4: added recovery-aware auth screens, recovery email metadata, and Settings recovery commands.
- Roadmap 2.0 Stage 2.0.5: added workflow validation, inline notices, progress states, import confirmation, and approval safeguards.
- Roadmap 2.0 Stage 2.0.6: added responsive layout hardening, skip navigation, visible focus states, live status semantics, reduced-motion support, and overflow-safe dense content.
- Roadmap 2.0 Stage 2.0.7: added a repeatable static frontend QA routine, reserved the `#/leads` Lead Pipeline route, and documented the Phase 5 UI slots and API contract.

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

## Roadmap 2.0: Frontend Rebuild

Goal: modernize the browser app before adding larger growth workflows, while keeping the existing Python backend, SQLite state, API routes, and daemon worker intact.

Rationale:

- The `v2.2.1` UI is visually healthy and usable.
- The old frontend was a single static HTML/CSS/JS surface.
- Phase 5 Lead Pipeline will add heavier state, filtering, forms, and workflow screens.
- A React foundation reduces frontend risk before those features are added.

Sequencing rule:

- Roadmap 2.0 does not renumber the product roadmap.
- Phase 5, Stage 5.1 remains the next product-growth phase.
- Phase 5 stays paused until Roadmap 2.0 reaches its completion gate.
- Backend Roadmap 3.0 waits unless a Roadmap 2.0 or Phase 5 feature exposes a real backend blocker.

### Stage 2.0.1: React Frontend Foundation

Status: complete.

Deliverables:

- Vite build pipeline.
- React app shell.
- TypeScript frontend data contracts.
- Tailwind CSS design foundation.
- Existing dashboard behavior preserved against the current API.
- Compiled static bundle served by the Python web app.

Release target:

- `v2.3.0`.

Release status: shipped.

### Stage 2.0.2: Component System And Layout Shell

Status: complete.

Deliverables:

- Shared cards, panels, buttons, fields, status badges, and list components.
- Consistent icon usage across dashboard actions.
- Reusable page header, toolbar, section, drawer, modal, and toast patterns.
- Layout shell that can support multiple views without nested card clutter.
- Reduced duplication in frontend markup.

Release target:

- `v2.3.2`.

Release status: shipped.

### Stage 2.0.3: Navigation And Information Architecture

Status: complete.

Deliverables:

- Primary navigation for overview, temples, strategies, imports, approvals, reports, and settings.
- First-screen dashboard focused on quota health, worker state, top action, and urgent approvals.
- Deeper workflow views for long forms and dense lists.
- URL-aware routes or view state so the app can return to the same workflow after refresh.
- Clear empty states that explain what is missing without becoming marketing copy.

Release target:

- `v2.3.3`.

Release status: shipped.

### Stage 2.0.4: Auth UX And Account Recovery Readiness

Status: complete.

Deliverables:

- Cleaner login and owner setup screens.
- Username reminder path for local accounts.
- Optional recovery email field on owner account profile.
- Password reset design that never reveals stored passwords.
- Existing CLI password reset surfaced as the local fallback path.
- Local-owner recovery runbook for self-hosted installs.
- Frontend copy for forgotten username/password states.

Release target:

- `v2.3.4`.

Release status: shipped.

### Stage 2.0.5: Workflow Forms And Feedback

Status: complete.

Deliverables:

- Stronger client-side validation for quota, income, imports, approvals, reports, and temple creation.
- Better loading, disabled, success, warning, and failure states.
- Safer destructive or irreversible action confirmations.
- Inline field errors instead of toast-only feedback.
- Form state preservation for longer workflows.

Release target:

- `v2.3.5`.

Release status: shipped.

### Stage 2.0.6: Responsive Design And Accessibility

Status: complete.

Deliverables:

- Mobile, tablet, and desktop layout pass.
- Keyboard navigation pass for all interactive controls.
- Accessible labels and status regions for live updates.
- Contrast and focus-ring verification.
- Text wrapping and overflow checks for long strategy, temple, report, and approval content.

Release target:

- `v2.3.6`.

Release status: shipped.

### Stage 2.0.7: Visual QA And Phase 5 Readiness

Status: complete.

Deliverables:

- Browser smoke checks for auth, dashboard loading, report generation, imports, approvals, and core controls.
- Screenshot checks for desktop and mobile widths.
- Frontend build and static serving checks in CI or the local test routine.
- Lead Pipeline UI slots identified before backend work begins.
- API contract notes for the Phase 5 lead records and pipeline views.

Release target:

- `v2.3.7`.

Release status: shipped.

### Roadmap 2.0 Completion Gate

Status: complete.

Roadmap 2.0 is complete when:

- The React frontend is the only active dashboard implementation.
- Core workflows are visually checked in desktop and mobile widths.
- The frontend build is documented and repeatable.
- Tests cover static asset serving and API compatibility.
- Phase 5 Lead Pipeline can be added without expanding a single monolithic browser script.
- Login, forgotten-credential, and owner setup UX have a clear safe path.
- Navigation can support the Lead Pipeline as a first-class workflow.

## Phase 5: Growth Operations

Goal: help each temple convert legitimate opportunities into tracked revenue.

Status: ready to resume after Roadmap 2.0 completion.

### Stage 5.1: Lead Pipeline

Status: future.

Deliverables:

- Lead records per temple.
- Offer, value, source, and next-step fields.
- Follow-up dates.
- Pipeline stages.
- Priority scoring tied to quota gaps.

Release target:

- `v2.4.0`.

### Stage 5.2: Conversion Tracking

Status: future.

Deliverables:

- Link income entries back to leads, drafts, imports, or strategies.
- Conversion rate summaries.
- Average deal size by temple and strategy.
- Lost-opportunity notes.

Release target:

- `v2.5.0` or later.

### Stage 5.3: Revenue Rules

Status: future.

Deliverables:

- Configurable safe automation rules.
- Human approval gates for any external action.
- Rule run logs.
- Disable switches per temple.

Release target:

- `v2.6.0` or later.

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

Build Phase 5, Stage 5.1: Lead Pipeline next:

- Add the lead persistence model scoped by temple.
- Add API endpoints for lead list, create, update, notes, stage advance, and summary.
- Replace the `#/leads` readiness panel with the real pipeline board, intake form, follow-up queue, and lead detail workspace.
- Tie lead priority scoring to quota gap, expected value, probability, follow-up date, and strategy evidence.

Backend Roadmap 3.0 should wait until after Phase 5, Stage 5.1 unless the lead pipeline exposes a real backend blocker. The next best revenue move after Roadmap 2.0 is still the lead pipeline.
