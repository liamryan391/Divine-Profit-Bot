import {
  Activity,
  ArrowRight,
  BarChart3,
  Check,
  ClipboardList,
  Coins,
  Download,
  FileText,
  Gauge,
  KeyRound,
  Landmark,
  Mail,
  Plus,
  RefreshCcw,
  Send,
  Settings,
  ShieldCheck,
  Target,
  TrendingUp,
  Upload,
  X,
} from "lucide-react";
import type { FormEvent } from "react";
import type {
  ApprovalAction,
  ApprovalSummary,
  DashboardPayload,
  ExternalSnapshot,
  ImportResult,
  Opportunity,
  ReportPayload,
  StrategyRoi,
} from "../types";
import {
  approvalBorder,
  capitalize,
  cx,
  externalBorder,
  externalItemText,
  formatTime,
  importBorder,
  recommendationBorder,
  riskLabel,
  shortDate,
  slugify,
  titleCase,
} from "../lib/format";
import type { WorkflowFeedback, WorkflowFeedbackMap } from "../lib/forms";
import { ActionLink, Badge, Button, EmptyRow, Field, FormNotice, MiniMetric, MoodSelect, Panel, SelectField, StrategySelect, Toolbar } from "./ui";

export function QuotaProgressPanel({ dashboard }: { dashboard: DashboardPayload }) {
  const progress = Math.min(Math.max(dashboard.status.progress_pct, 0), 100);
  return (
    <section className="temple-panel mt-4">
      <div className="section-heading">
        <h2 className="text-lg font-black">Quota Progress</h2>
        <Badge>{titleCase(dashboard.status.judgement)}</Badge>
      </div>
      <div
        className="h-6 overflow-hidden rounded-lg border border-[#141f33] bg-[#0b1120]"
        role="progressbar"
        aria-label="Quota progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
        aria-valuetext={`${dashboard.status.progress_pct}% of ${dashboard.status.quota}`}
      >
        <div
          className="h-full rounded-lg bg-gradient-to-r from-temple-gold via-temple-green to-temple-blue transition-[width] duration-300"
          style={{ width: `${progress}%` }}
          aria-hidden="true"
        />
      </div>
      <p className="mt-2 text-temple-muted">
        Time remaining: {dashboard.status.days_left} day{dashboard.status.days_left === 1 ? "" : "s"}
      </p>
    </section>
  );
}

export function TopOffering({ item }: { item: Opportunity | null }) {
  return (
    <section className="temple-panel mt-4">
      <div className="section-heading">
        <h2 className="text-lg font-black">Top Offering</h2>
        <Badge>{item ? `${item.score}/100 - ${titleCase(item.score_label)}` : "score --"}</Badge>
      </div>
      <strong className="mb-2 block break-words text-2xl text-temple-gold sm:text-3xl">
        {item ? `#${item.rank} ${item.name}` : "No recommendation available"}
      </strong>
      <p className="text-temple-muted">
        {item
          ? `${item.rationale} Next action: ${item.next_action}`
          : "Configure at least one strategy to generate a ranked offering."}
      </p>
      <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-7">
        {item
          ? Object.entries(item.components).map(([label, value]) => (
              <div key={label} className="min-h-[74px] rounded-lg border border-white/5 bg-temple-panelDeep p-2.5">
                <span className="block text-xs font-black uppercase text-temple-muted">{label}</span>
                <strong className="mt-2 block text-lg text-temple-text">{value}</strong>
              </div>
            ))
          : null}
      </div>
    </section>
  );
}

export function TempleSwitchboardPanel({
  dashboard,
  busy,
  feedback,
  onSubmit,
}: {
  dashboard: DashboardPayload;
  busy: string;
  feedback?: WorkflowFeedback;
  onSubmit: (event: FormEvent<HTMLFormElement>, path: string, success: string) => void;
}) {
  return (
    <Panel
      title="Temple Switchboard"
      icon={Landmark}
      wide
      meta={`${dashboard.temples.temple_count} temples - ${dashboard.temples.overall_progress_pct}% overall`}
    >
      <TempleSummaryList summary={dashboard.temples} />
      <form
        noValidate
        className="mt-4 grid gap-3 border-t border-temple-line pt-4 md:grid-cols-3"
        onSubmit={(event) => onSubmit(event, "/api/temple/create", "Temple created")}
      >
        <Field label="Temple Name" name="name" placeholder="New Revenue Temple" required />
        <Field label="Temple ID" name="temple_id" placeholder="optional-stable-id" />
        <SelectField label="Template" name="template" defaultValue="balanced">
          <option value="balanced">Balanced</option>
          <option value="services">Services</option>
          <option value="products">Products</option>
        </SelectField>
        <Field
          className="md:col-span-2"
          label="Description"
          name="description"
          placeholder="What this temple is trying to earn from"
        />
        <div className="md:col-span-3">
          <FormNotice feedback={feedback} />
        </div>
        <div className="flex items-end">
          <Button icon={Plus} disabled={busy === "/api/temple/create"} type="submit">
            {busy === "/api/temple/create" ? "Creating..." : "Create Temple"}
          </Button>
        </div>
      </form>
    </Panel>
  );
}

export function StrategiesPanel({ dashboard }: { dashboard: DashboardPayload }) {
  return (
    <Panel title="Active Strategies" icon={TrendingUp}>
      <StrategyList items={dashboard.opportunities} />
    </Panel>
  );
}

export function StrategyRoiPanel({ dashboard }: { dashboard: DashboardPayload }) {
  return (
    <Panel
      title="Strategy ROI"
      icon={BarChart3}
      wide
      meta={
        dashboard.strategy_roi.rows.length
          ? `${shortDate(dashboard.strategy_roi.period.start)} to ${shortDate(dashboard.strategy_roi.period.end)}`
          : "no data"
      }
    >
      <StrategyRoiList roi={dashboard.strategy_roi} />
    </Panel>
  );
}

export function PriorityCallsPanel({ dashboard }: { dashboard: DashboardPayload }) {
  return (
    <Panel title="Priority Calls" icon={Gauge}>
      <PriorityCalls roi={dashboard.strategy_roi} />
    </Panel>
  );
}

export function ConfigPanel({ dashboard }: { dashboard: DashboardPayload }) {
  return (
    <Panel title="Divine Configuration" icon={Settings}>
      <ConfigList dashboard={dashboard} />
    </Panel>
  );
}

export function AccountRecoveryPanel({
  dashboard,
  busy,
  feedback,
  onSubmit,
}: {
  dashboard: DashboardPayload;
  busy: string;
  feedback?: WorkflowFeedback;
  onSubmit: (event: FormEvent<HTMLFormElement>, path: string, success: string, resetForm?: boolean) => void;
}) {
  const account = dashboard.auth.account;
  const username = account?.username || "owner";
  const displayName = account?.display_name || "";
  const recoveryEmail = account?.recovery_email || "";
  return (
    <Panel
      title="Account Recovery"
      icon={KeyRound}
      wide
      meta={recoveryEmail ? "email linked" : "email not set"}
    >
      <div className="grid gap-2.5 md:grid-cols-3">
        <MiniMetric label="Username" value={username} />
        <MiniMetric label="Display Name" value={displayName || "Creator"} />
        <MiniMetric label="Recovery Email" value={recoveryEmail || "Not set"} />
      </div>
      <form
        noValidate
        key={`account-${account?.id || "local"}-${displayName}-${recoveryEmail}`}
        className="mt-4 grid gap-3 border-t border-temple-line pt-4 md:grid-cols-3"
        onSubmit={(event) => onSubmit(event, "/api/account/profile", "Recovery profile updated", false)}
      >
        <Field label="Display Name" name="display_name" autoComplete="name" defaultValue={displayName} placeholder="Creator" />
        <Field
          label="Recovery Email"
          name="recovery_email"
          type="email"
          autoComplete="email"
          defaultValue={recoveryEmail}
          placeholder="owner@example.com"
        />
        <div className="flex items-end">
          <Button icon={Mail} disabled={busy === "/api/account/profile"} type="submit">
            {busy === "/api/account/profile" ? "Saving..." : "Save Recovery"}
          </Button>
        </div>
        <div className="md:col-span-3">
          <FormNotice feedback={feedback} />
        </div>
      </form>
      <div className="mt-4 grid gap-2.5">
        <div className="temple-row grid gap-2 border-l-4 border-l-temple-gold">
          <strong>Username reminder</strong>
          <code className="break-words rounded-md bg-[#091020] px-2.5 py-2 font-mono text-xs leading-5 text-[#d9e5ff]">
            python -m divine_tool account list
          </code>
        </div>
        <div className="temple-row grid gap-2 border-l-4 border-l-temple-blue">
          <strong>Password reset</strong>
          <code className="break-words rounded-md bg-[#091020] px-2.5 py-2 font-mono text-xs leading-5 text-[#d9e5ff]">
            python -m divine_tool account reset-password {username}
          </code>
          <span className="text-sm leading-6 text-temple-muted">
            Existing passwords cannot be displayed; reset rotates the hash and signs out active sessions.
          </span>
        </div>
      </div>
    </Panel>
  );
}

export function ExternalSignalsPanel({
  external,
  busy,
  onRefresh,
}: {
  external: ExternalSnapshot | null;
  busy: string;
  onRefresh: () => void;
}) {
  return (
    <Panel
      title="External Signals"
      icon={RefreshCcw}
      wide
      meta={`${external?.connected_count ?? 0} connected`}
      actions={
        <Button icon={RefreshCcw} variant="secondary" disabled={busy === "external"} onClick={onRefresh}>
          Refresh
        </Button>
      }
    >
      <ExternalList snapshot={external} />
    </Panel>
  );
}

export function ApprovalQueuePanel({
  dashboard,
  busy,
  feedback,
  onSubmit,
  onReview,
}: {
  dashboard: DashboardPayload;
  busy: string;
  feedback?: WorkflowFeedback;
  onSubmit: (event: FormEvent<HTMLFormElement>, path: string, success: string) => void;
  onReview: (id: number, decision: string) => Promise<void>;
}) {
  return (
    <Panel
      title="Approval Queue"
      icon={ClipboardList}
      wide
      meta={`${dashboard.approvals.counts.pending || 0} pending - ${dashboard.approvals.counts.approved || 0} approved`}
    >
      <ApprovalForm
        channels={dashboard.config.channels}
        busy={busy === "/api/approval/draft"}
        feedback={feedback}
        onSubmit={(event) => onSubmit(event, "/api/approval/draft", "Draft queued for approval")}
      />
      <ApprovalList approvals={dashboard.approvals} busy={busy} onReview={onReview} />
    </Panel>
  );
}

export function UrgentApprovalsPanel({
  dashboard,
  busy,
  onReview,
}: {
  dashboard: DashboardPayload;
  busy: string;
  onReview: (id: number, decision: string) => Promise<void>;
}) {
  const pending = (dashboard.approvals.recent || []).filter((item) => item.status === "pending").slice(0, 4);
  return (
    <Panel
      title="Urgent Approvals"
      icon={ClipboardList}
      wide
      actions={
        <Toolbar>
          <Badge>{pending.length} pending</Badge>
          <ActionLink href="#/approvals" icon={ArrowRight}>
            Queue
          </ActionLink>
        </Toolbar>
      }
    >
      {pending.length ? (
        <div className="grid gap-2.5">
          {pending.map((item) => (
            <div key={item.id} className={cx("temple-row grid gap-3 border-l-4", approvalBorder(item.status))}>
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
                <div className="grid min-w-0 gap-1">
                  <strong className="break-words">
                    #{item.id} {item.title}
                  </strong>
                  <span className="text-sm text-temple-muted">
                    {item.kind_label} - {item.strategy || "unassigned"}
                  </span>
                </div>
                <b className="text-xs font-black uppercase text-temple-gold sm:text-right">{item.status}</b>
              </div>
              <p className="line-clamp-3 text-sm leading-6 text-temple-muted">{item.body}</p>
              <ApprovalActions item={item} busy={busy} onReview={onReview} />
            </div>
          ))}
        </div>
      ) : (
        <EmptyRow>No pending approval actions.</EmptyRow>
      )}
    </Panel>
  );
}

export function TempleLogPanel({
  dashboard,
  busy,
  onPulse,
}: {
  dashboard: DashboardPayload;
  busy: string;
  onPulse: () => void;
}) {
  return (
    <Panel
      title="Temple Log"
      icon={FileText}
      wide
      actions={
        <Button icon={Activity} variant="secondary" disabled={busy === "pulse"} onClick={onPulse}>
          Pulse Worker
        </Button>
      }
    >
      <TempleLog events={dashboard.events} />
    </Panel>
  );
}

export function CommandAltarPanel({
  dashboard,
  busy,
  feedback,
  onSubmit,
}: {
  dashboard: DashboardPayload;
  busy: string;
  feedback?: WorkflowFeedback;
  onSubmit: (event: FormEvent<HTMLFormElement>, path: string, success: string) => void;
}) {
  return (
    <Panel title="Command Altar" icon={Send}>
      <form noValidate className="grid gap-3" onSubmit={(event) => onSubmit(event, "/api/income", "Income recorded")}>
        <Field label="Amount" name="amount" inputMode="decimal" placeholder="75.00" required />
        <SelectField label="Currency" name="currency" defaultValue="GBP">
          <option value="GBP">GBP</option>
          <option value="USD">USD</option>
          <option value="EUR">EUR</option>
          <option value="BTC">BTC</option>
          <option value="LTC">LTC</option>
          <option value="XMR">XMR</option>
        </SelectField>
        <Field label="GBP Equivalent" name="gbp_equivalent" inputMode="decimal" placeholder="Required outside GBP" />
        <Field label="Source" name="source" placeholder="Paid consultation" required />
        <StrategySelect label="Strategy" name="strategy" channels={dashboard.config.channels} />
        <Field label="Note" name="note" placeholder="Optional" />
        <FormNotice feedback={feedback} />
        <Button icon={Coins} disabled={busy === "/api/income"} type="submit">
          {busy === "/api/income" ? "Recording..." : "Record Income"}
        </Button>
      </form>
    </Panel>
  );
}

export function ImportAltarPanel({
  dashboard,
  busy,
  feedback,
  importResult,
  onImport,
}: {
  dashboard: DashboardPayload;
  busy: string;
  feedback?: WorkflowFeedback;
  importResult: ImportResult | null;
  onImport: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <Panel title="Import Altar" icon={Upload}>
      <form noValidate className="grid gap-3" onSubmit={onImport}>
        <label className="field-label">
          CSV File
          <input
            className="temple-input aria-[invalid=true]:border-temple-red aria-[invalid=true]:ring-4 aria-[invalid=true]:ring-temple-red/20 file:mr-3 file:rounded-md file:border-0 file:bg-temple-gold file:px-3 file:py-1.5 file:text-sm file:font-bold file:text-[#07101c]"
            name="file"
            type="file"
            accept=".csv,text/csv"
            required
          />
        </label>
        <SelectField label="Import Type" name="source_type" defaultValue="generic">
          <option value="generic">Generic CSV</option>
          <option value="payment">Payment Export</option>
          <option value="affiliate">Affiliate Report</option>
        </SelectField>
        <StrategySelect
          label="Default Strategy"
          name="default_strategy"
          channels={dashboard.config.channels}
          emptyLabel="Auto / Unassigned"
        />
        <label className="flex items-center gap-3 text-sm font-bold text-temple-text">
          <input className="h-5 w-5 accent-temple-gold" name="dry_run" type="checkbox" defaultChecked />
          Dry run first
        </label>
        <FormNotice feedback={feedback} />
        <Button icon={Upload} disabled={busy === "import"} type="submit">
          {busy === "import" ? "Importing..." : "Import CSV"}
        </Button>
      </form>
      <ImportResultView result={importResult} />
    </Panel>
  );
}

export function QuotaControlPanel({
  dashboard,
  busy,
  feedback,
  onSubmit,
}: {
  dashboard: DashboardPayload;
  busy: string;
  feedback: WorkflowFeedbackMap;
  onSubmit: (event: FormEvent<HTMLFormElement>, path: string, success: string) => void;
}) {
  return (
    <Panel title="Quota Control" icon={Target}>
      <form
        noValidate
        key={`quota-${dashboard.config.active_mood}`}
        className="grid gap-3"
        onSubmit={(event) => onSubmit(event, "/api/quota", "Quota updated")}
      >
        <MoodSelect label="Mood" name="mood" moods={dashboard.config.moods} defaultValue={dashboard.config.active_mood} />
        <Field label="Target" name="amount" inputMode="decimal" placeholder="250.00" required />
        <SelectField label="Period" name="period" defaultValue={dashboard.status.period.name}>
          <option value="week">Week</option>
          <option value="month">Month</option>
        </SelectField>
        <FormNotice feedback={feedback["/api/quota"]} />
        <Button icon={Target} disabled={busy === "/api/quota"} type="submit">
          {busy === "/api/quota" ? "Saving..." : "Set Quota"}
        </Button>
      </form>
      <form
        noValidate
        key={`mood-${dashboard.config.active_mood}`}
        className="mt-4 grid gap-3 border-t border-temple-line pt-4"
        onSubmit={(event) => onSubmit(event, "/api/mood", "Mood updated")}
      >
        <MoodSelect label="Active Mood" name="mood" moods={dashboard.config.moods} defaultValue={dashboard.config.active_mood} />
        <FormNotice feedback={feedback["/api/mood"]} />
        <Button icon={Gauge} variant="secondary" disabled={busy === "/api/mood"} type="submit">
          {busy === "/api/mood" ? "Saving..." : "Set Mood"}
        </Button>
      </form>
    </Panel>
  );
}

export function MercyExceptionPanel({
  busy,
  feedback,
  onSubmit,
}: {
  busy: string;
  feedback?: WorkflowFeedback;
  onSubmit: (event: FormEvent<HTMLFormElement>, path: string, success: string) => void;
}) {
  return (
    <Panel title="Mercy Exception" icon={ShieldCheck}>
      <form noValidate className="grid gap-3" onSubmit={(event) => onSubmit(event, "/api/exception", "Exception added")}>
        <Field label="Reason" name="reason" placeholder="Payment processor outage" required />
        <Field label="Until" name="until" type="date" required />
        <FormNotice feedback={feedback} />
        <Button icon={ShieldCheck} variant="secondary" disabled={busy === "/api/exception"} type="submit">
          {busy === "/api/exception" ? "Adding..." : "Add Exception"}
        </Button>
      </form>
    </Panel>
  );
}

export function RecentIncomePanel({ dashboard }: { dashboard: DashboardPayload }) {
  return (
    <Panel title="Recent Income" icon={Coins}>
      <RecentIncome items={dashboard.income} />
    </Panel>
  );
}

export function UpgradePathPanel({ dashboard }: { dashboard: DashboardPayload }) {
  return (
    <Panel title="Upgrade Path" icon={TrendingUp} wide>
      <UpgradeGrid upgrades={dashboard.upgrades} />
    </Panel>
  );
}

export function ReportForgePanel({
  report,
  busy,
  feedback,
  onGenerate,
  onDownload,
}: {
  report: ReportPayload;
  busy: string;
  feedback?: WorkflowFeedback;
  onGenerate: () => void;
  onDownload: () => void;
}) {
  return (
    <Panel
      title="Report Forge"
      icon={FileText}
      wide
      actions={
        <Toolbar>
          <SelectField id="reportPeriod" className="w-full min-w-[132px] sm:w-auto" ariaLabel="Report period" defaultValue="week">
            <option value="week">Weekly</option>
            <option value="month">Monthly</option>
          </SelectField>
          <Button icon={FileText} variant="secondary" disabled={busy === "report"} onClick={onGenerate}>
            {busy === "report" ? "Generating..." : "Generate"}
          </Button>
          <Button icon={Download} onClick={onDownload}>
            Download
          </Button>
        </Toolbar>
      }
    >
      <div className="mb-3 grid gap-1 sm:flex sm:items-baseline sm:justify-between">
        <strong className="text-lg text-temple-gold">{report.title}</strong>
        <span className="text-temple-muted">
          {report.period.start} to {report.period.end} - {report.earned} earned of {report.quota}
        </span>
      </div>
      <div className="mb-3">
        <FormNotice feedback={feedback} />
      </div>
      <pre className="max-h-[520px] min-h-[320px] overflow-auto rounded-lg border border-temple-line bg-[#091020] p-4 text-sm leading-6 text-[#d9e5ff] whitespace-pre-wrap break-words">
        {report.markdown}
      </pre>
    </Panel>
  );
}

function TempleSummaryList({ summary }: { summary: DashboardPayload["temples"] }) {
  if (!summary.rows.length) {
    return <EmptyRow>No temples configured yet.</EmptyRow>;
  }
  return (
    <div className="grid gap-2.5">
      {summary.rows.map((item) => (
        <div
          key={item.id}
          className={cx("temple-row grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center", item.active && "border-l-4 border-l-temple-gold")}
        >
          <div className="grid min-w-0 gap-1">
            <strong className="break-words">{item.active ? `Active: ${item.name}` : item.name}</strong>
            <span className="text-sm text-temple-muted">
              {titleCase(item.judgement)} - top: {item.top_strategy}
            </span>
          </div>
          <div className="grid min-w-0 gap-1 sm:justify-items-end">
            <b className="break-words text-temple-green sm:text-right">
              {item.earned} / {item.quota}
            </b>
            <small className="text-temple-muted sm:text-right">
              {item.progress_pct}% - {item.mood}
            </small>
          </div>
        </div>
      ))}
    </div>
  );
}

function StrategyList({ items }: { items: Opportunity[] }) {
  if (!items.length) {
    return <EmptyRow>No strategies configured.</EmptyRow>;
  }
  return (
    <div className="grid gap-2.5">
      {items.slice(0, 5).map((item) => (
        <div key={item.id} className="temple-row grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start" title={item.next_action}>
          <div className="grid min-w-0 gap-1.5">
            <strong className="break-words">{item.name}</strong>
            <span className="text-sm text-temple-muted">
              {item.expected} expected - {item.period_income} recorded this period
            </span>
            <small className="text-temple-muted">{item.rationale}</small>
          </div>
          <div className="grid min-w-0 gap-2 sm:min-w-24 sm:justify-items-end">
            <b className={cx("text-xs font-black uppercase", item.fit === "deadline" || item.risk !== "low" ? "text-temple-gold" : "text-temple-green")}>
              {item.score}/100
            </b>
            <div className="h-2 w-full overflow-hidden rounded-full bg-[#172238] sm:w-24" aria-hidden="true">
              <span
                className="block h-full rounded-full bg-gradient-to-r from-temple-gold to-temple-green"
                style={{ width: `${Math.min(item.score, 100)}%` }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function StrategyRoiList({ roi }: { roi: StrategyRoi }) {
  if (!roi.rows.length) {
    return <EmptyRow>No strategy ROI data yet.</EmptyRow>;
  }
  return (
    <div className="grid gap-2.5">
      {roi.rows.map((row) => (
        <div key={row.id} className={cx("temple-row grid gap-3 border-l-4", recommendationBorder(row.recommendation))}>
          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
            <div className="grid min-w-0 gap-1">
              <strong className="break-words">
                #{row.roi_rank} {row.name}
              </strong>
              <span className="text-sm text-temple-muted">
                {titleCase(row.trend)} - {row.target_capture_pct}% of expected value
              </span>
            </div>
            <b className="text-xs font-black uppercase text-temple-green sm:text-right">{row.recommendation}</b>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <MiniMetric label="Current" value={row.current_period} />
            <MiniMetric label="Previous" value={row.previous_period} />
            <MiniMetric label="Delta" value={row.delta} />
            <MiniMetric label="Per Effort" value={row.roi_per_effort} />
          </div>
          <div className="grid gap-1">
            {row.notes.length ? (
              row.notes.map((note, index) => (
                <span key={`${row.id}-note-${index}`} className="text-sm text-temple-muted">
                  {note.amount} - {note.note}
                </span>
              ))
            ) : (
              <span className="text-sm text-temple-muted">No conversion notes recorded.</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function PriorityCalls({ roi }: { roi: StrategyRoi }) {
  if (!roi.rows.length) {
    return <EmptyRow>No recommendations yet.</EmptyRow>;
  }
  const calls = [
    ...roi.push_recommendations.map((item) => ({ ...item, call: "Push" })),
    ...roi.pause_recommendations.map((item) => ({ ...item, call: "Pause" })),
  ];
  const visible = calls.length ? calls.slice(0, 5) : roi.rows.slice(0, 3).map((item) => ({ ...item, call: "Watch" }));
  return (
    <div className="grid gap-2.5">
      {visible.map((item) => (
        <div key={`${item.call}-${item.id}`} className="temple-row grid gap-1">
          <strong className={item.call === "Pause" ? "text-temple-gold" : "text-temple-green"}>
            {item.call}: {item.name}
          </strong>
          <span className="text-sm text-temple-muted">{item.recommendation_reason}</span>
        </div>
      ))}
    </div>
  );
}

function ConfigList({ dashboard }: { dashboard: DashboardPayload }) {
  const temple = dashboard.status.temple || dashboard.config.active_temple;
  const rows = [
    ["Active Temple", temple?.name || temple?.id || "main"],
    ["Primary Currency", dashboard.config.base_currency],
    ["Active Mood", dashboard.status.mood],
    ["Risk Level", riskLabel(dashboard.status.judgement)],
    ["Worker State", dashboard.worker.state],
  ];
  return (
    <div className="grid gap-2.5">
      {rows.map(([label, value]) => (
        <div key={label} className="temple-row grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
          <strong className="break-words">{label}</strong>
          <span className="break-words text-sm font-bold uppercase text-temple-muted sm:text-right">{value}</span>
        </div>
      ))}
    </div>
  );
}

function ExternalList({ snapshot }: { snapshot: ExternalSnapshot | null }) {
  if (!snapshot) {
    return <EmptyRow>Refresh to check live external signals.</EmptyRow>;
  }
  return (
    <div className="grid gap-2.5">
      {snapshot.connections.map((connection) => (
        <div key={connection.id} className={cx("temple-row grid gap-x-3 gap-y-2 border-l-4 sm:grid-cols-[minmax(0,1fr)_auto]", externalBorder(connection.state))}>
          <div className="grid min-w-0 gap-1">
            <strong className="break-words">{connection.name}</strong>
            <span className="text-sm text-temple-muted">{connection.summary}</span>
          </div>
          <b className="text-xs font-black uppercase text-temple-green sm:text-right">{connection.state}</b>
          <small className="col-span-full text-temple-muted">
            {connection.items && connection.items.length
              ? connection.items.slice(0, 4).map(externalItemText).join(" - ")
              : connection.next_action || "No live values returned."}
          </small>
        </div>
      ))}
    </div>
  );
}

function ApprovalForm({
  channels,
  busy,
  feedback,
  onSubmit,
}: {
  channels: DashboardPayload["config"]["channels"];
  busy: boolean;
  feedback?: WorkflowFeedback;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <form noValidate className="grid gap-3 md:grid-cols-3" onSubmit={onSubmit}>
      <SelectField label="Draft Type" name="kind" defaultValue="invoice_reminder">
        <option value="invoice_reminder">Invoice Reminder</option>
        <option value="outreach">Outreach Message</option>
        <option value="content_prompt">Content Prompt</option>
      </SelectField>
      <Field label="Target" name="target" placeholder="Client, lead, or topic" />
      <Field label="Amount" name="amount" inputMode="decimal" placeholder="Invoice only" />
      <Field label="Due" name="due" type="date" />
      <Field label="Invoice" name="invoice" placeholder="INV-001" />
      <Field label="Offer" name="offer" placeholder="Outreach offer" />
      <Field label="Topic" name="topic" placeholder="Content topic" />
      <Field label="Goal" name="goal" placeholder="Booking, reply, purchase" />
      <Field label="Channel" name="channel" placeholder="Email, LinkedIn, blog" />
      <StrategySelect label="Strategy" name="strategy" channels={channels} />
      <Field className="md:col-span-2" label="Context" name="context" placeholder="Useful background" />
      <div className="md:col-span-3">
        <FormNotice feedback={feedback} />
      </div>
      <div className="flex items-end">
        <Button icon={Send} disabled={busy} type="submit">
          {busy ? "Queuing..." : "Queue Draft"}
        </Button>
      </div>
    </form>
  );
}

function ApprovalList({
  approvals,
  busy,
  onReview,
}: {
  approvals: ApprovalSummary;
  busy: string;
  onReview: (id: number, decision: string) => Promise<void>;
}) {
  const rows = approvals.recent || [];
  if (!rows.length) {
    return (
      <div className="mt-4">
        <EmptyRow>No approval drafts yet.</EmptyRow>
      </div>
    );
  }
  return (
    <div className="mt-4 grid gap-2.5">
      {rows.slice(0, 8).map((item) => (
        <div key={item.id} className={cx("temple-row grid gap-3 border-l-4", approvalBorder(item.status))}>
          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
            <div className="grid min-w-0 gap-1">
              <strong className="break-words">
                #{item.id} {item.title}
              </strong>
              <span className="text-sm text-temple-muted">
                {item.kind_label} - {item.strategy || "unassigned"}
              </span>
            </div>
            <b className="text-xs font-black uppercase text-temple-green sm:text-right">{item.status}</b>
          </div>
          <pre className="max-h-[190px] overflow-auto rounded-lg bg-[#091020] p-3 text-sm leading-6 text-[#d9e5ff] whitespace-pre-wrap break-words">
            {item.body}
          </pre>
          <ApprovalActions item={item} busy={busy} onReview={onReview} />
        </div>
      ))}
    </div>
  );
}

function ApprovalActions({
  item,
  busy,
  onReview,
}: {
  item: ApprovalAction;
  busy: string;
  onReview: (id: number, decision: string) => Promise<void>;
}) {
  if (item.status !== "pending" && item.status !== "approved") {
    return null;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {item.status === "pending" ? (
        <Button
          icon={Check}
          variant="secondary"
          disabled={busy === `approval-${item.id}-approve`}
          onClick={() => void onReview(item.id, "approve")}
        >
          Approve
        </Button>
      ) : null}
      {item.status === "approved" ? (
        <Button
          icon={Check}
          variant="secondary"
          disabled={busy === `approval-${item.id}-complete`}
          onClick={() => void onReview(item.id, "complete")}
        >
          Complete
        </Button>
      ) : null}
      <Button
        icon={X}
        variant="ghost"
        disabled={busy === `approval-${item.id}-reject`}
        onClick={() => void onReview(item.id, "reject")}
      >
        Reject
      </Button>
    </div>
  );
}

function TempleLog({ events }: { events: DashboardPayload["events"] }) {
  if (!events.length) {
    return (
      <div className="min-h-[214px] rounded-lg bg-[#091020] p-3.5 font-mono text-sm text-[#d9e5ff]">
        <LogLine time="--:--:--" category="system" message="Temple initialized. Awaiting command." />
      </div>
    );
  }
  return (
    <div className="grid max-h-80 min-h-[214px] gap-2 overflow-auto rounded-lg bg-[#091020] p-3.5 font-mono text-sm text-[#d9e5ff]">
      {events
        .slice()
        .reverse()
        .map((event, index) => (
          <LogLine
            key={`${event.created_at}-${index}`}
            time={formatTime(event.created_at)}
            category={event.category}
            message={event.message}
          />
        ))}
    </div>
  );
}

function LogLine({ time, category, message }: { time: string; category: string; message: string }) {
  return (
    <div className="grid gap-0 border-b border-white/5 pb-2 leading-6 md:grid-cols-[92px_90px_1fr] md:gap-3 md:border-b-0 md:pb-0">
      <time className="text-temple-green">{time}</time>
      <span className="text-temple-green">{category}</span>
      <strong className="break-words">{message}</strong>
    </div>
  );
}

function ImportResultView({ result }: { result: ImportResult | null }) {
  if (!result) {
    return null;
  }
  const primaryCount = result.dry_run ? `${result.ready_count || 0} ready` : `${result.imported_count} imported`;
  return (
    <div className="mt-4 grid gap-2.5">
      <div className="temple-row border-l-4 border-l-temple-green">
        <strong>{result.dry_run ? "Dry Run Complete" : "Import Complete"}</strong>
        <span className="mt-1 block text-sm text-temple-muted">
          {primaryCount}, {result.duplicate_count} duplicate, {result.skipped_count} skipped
        </span>
      </div>
      {result.rows
        .filter((row) => row.status !== "parsed")
        .slice(0, 8)
        .map((row, index) => (
          <div key={`${row.row_number || index}-${row.status}`} className={cx("temple-row border-l-4", importBorder(row.status))}>
            <strong>
              Row {row.row_number || "?"}: {titleCase(row.status)}
            </strong>
            <span className="mt-1 block text-sm text-temple-muted">
              {row.reason || (row.existing_id ? `Existing income #${row.existing_id}` : `${row.gbp || ""} ${row.source || ""}`)}
            </span>
          </div>
        ))}
    </div>
  );
}

function RecentIncome({ items }: { items: DashboardPayload["income"] }) {
  if (!items.length) {
    return <EmptyRow>No income recorded yet.</EmptyRow>;
  }
  return (
    <div className="grid gap-2.5">
      {items.map((item) => {
        const strategy = item.strategy ? ` [${item.strategy}]` : "";
        const note = item.note ? ` - ${item.note}` : "";
        return (
          <div key={item.id} className="temple-row grid gap-2 sm:grid-cols-[minmax(0,0.55fr)_minmax(0,1fr)] sm:items-center">
            <strong className="break-words">{item.counted}</strong>
            <span className="break-words text-sm text-temple-muted sm:text-right">
              {item.source}
              {strategy} - {item.occurred_at}
              {note}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function UpgradeGrid({ upgrades }: { upgrades: string[] }) {
  return (
    <div className="grid gap-2.5 md:grid-cols-2">
      {upgrades.slice(0, 6).map((item) => (
        <div key={item} className="temple-row">
          <span className="text-temple-muted">{item}</span>
        </div>
      ))}
    </div>
  );
}
