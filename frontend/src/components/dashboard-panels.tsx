import {
  Activity,
  Archive,
  ArrowRight,
  BarChart3,
  Check,
  CirclePause,
  CirclePlay,
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
  ShieldAlert,
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
  ConversionSummary,
  DashboardPayload,
  ExternalSnapshot,
  ImportResult,
  LeadEntry,
  Opportunity,
  ReportPayload,
  RevenueRuleEntry,
  RevenueRulesSummary,
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

const nextLeadStage: Record<string, string> = {
  new: "contacted",
  contacted: "qualified",
  qualified: "proposal",
  proposal: "won",
};

export function LeadPipelinePanel({
  dashboard,
  busy,
  feedback,
  onSubmit,
  onAdvance,
}: {
  dashboard: DashboardPayload;
  busy: string;
  feedback: WorkflowFeedbackMap;
  onSubmit: (event: FormEvent<HTMLFormElement>, path: string, success: string) => void;
  onAdvance: (id: number, stage: string) => Promise<void>;
}) {
  const loadedCount = dashboard.leads.rows.length;
  const totalCount = dashboard.leads.pagination?.total ?? dashboard.leads.total_count;
  const loadedLabel = loadedCount < totalCount ? ` - ${loadedCount} of ${totalCount} loaded` : "";
  return (
    <Panel
      title="Lead Pipeline"
      icon={Target}
      wide
      meta={`${dashboard.leads.open_count} open - ${dashboard.leads.weighted_value} weighted${loadedLabel}`}
    >
      <div className="grid gap-2.5 md:grid-cols-3">
        <MiniMetric label="Open Leads" value={String(dashboard.leads.open_count)} />
        <MiniMetric label="Weighted Value" value={dashboard.leads.weighted_value} />
        <MiniMetric label="Due Now" value={String(dashboard.leads.due_count)} />
      </div>
      <LeadIntakeForm dashboard={dashboard} busy={busy === "/api/leads"} feedback={feedback["/api/leads"]} onSubmit={onSubmit} />
      <ConversionTrackingPanel
        dashboard={dashboard}
        busy={busy}
        feedback={feedback["/api/conversions/record"]}
        onSubmit={onSubmit}
      />
      <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(280px,0.45fr)]">
        <LeadBoard leads={dashboard.leads.rows} stages={dashboard.leads.stages} busy={busy} onAdvance={onAdvance} />
        <div className="grid content-start gap-3">
          <LeadQueue title="Priority Leads" items={dashboard.leads.top} empty="No active leads yet." busy={busy} onAdvance={onAdvance} />
          <LeadQueue title="Due Follow-ups" items={dashboard.leads.due} empty="No lead follow-ups due." busy={busy} onAdvance={onAdvance} />
        </div>
      </div>
    </Panel>
  );
}

export function RevenueRulesPanel({
  dashboard,
  busy,
  feedback,
  onSubmit,
  onStatus,
}: {
  dashboard: DashboardPayload;
  busy: string;
  feedback?: WorkflowFeedback;
  onSubmit: (event: FormEvent<HTMLFormElement>, path: string, success: string) => void;
  onStatus: (id: number, status: string) => Promise<void>;
}) {
  const hasRevenueRulesPayload = Boolean(dashboard.revenue_rules);
  const summary = revenueRulesFor(dashboard);
  return (
    <Panel
      title="Revenue Rules"
      icon={ShieldAlert}
      wide
      meta={`${summary.triggered_count} triggered - ${summary.active_count} active`}
    >
      <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
        <MiniMetric label="Active Rules" value={String(summary.active_count)} />
        <MiniMetric label="Triggered" value={String(summary.triggered_count)} />
        <MiniMetric label="Approval Gates" value={String(summary.approval_required_count)} />
        <MiniMetric label="Blocks" value={String(summary.blocked_count)} />
      </div>
      {!hasRevenueRulesPayload ? (
        <div className="mt-4">
          <EmptyRow>Restart the web server to load the v2.6 revenue rules API.</EmptyRow>
        </div>
      ) : (
        <>
          <form
            noValidate
            className="mt-4 grid gap-3 border-t border-temple-line pt-4 md:grid-cols-4"
            onSubmit={(event) => onSubmit(event, "/api/revenue-rules", "Revenue rule created")}
          >
            <Field label="Rule Name" name="name" placeholder="Prioritise strong service pipeline" required />
            <StrategySelect label="Strategy" name="strategy" channels={dashboard.config.channels} emptyLabel="All strategies" />
            <SelectField label="Decision" name="rule_type" defaultValue="require_approval">
              <option value="promote">Promote</option>
              <option value="require_approval">Require Approval</option>
              <option value="pause">Pause</option>
              <option value="block">Block</option>
            </SelectField>
            <SelectField label="Metric" name="metric" defaultValue="open_weighted_value">
              <option value="open_weighted_value">Open Weighted Pipeline</option>
              <option value="conversion_rate_pct">Conversion Rate</option>
              <option value="win_rate_pct">Win Rate</option>
              <option value="lost_value">Lost Value</option>
              <option value="due_follow_ups">Due Follow-ups</option>
              <option value="open_leads">Open Leads</option>
              <option value="opportunity_score">Opportunity Score</option>
            </SelectField>
            <SelectField label="Condition" name="operator" defaultValue="gte">
              <option value="gte">At least</option>
              <option value="lte">At or below</option>
            </SelectField>
            <Field label="Threshold" name="threshold" inputMode="decimal" placeholder="500.00 or 60" required />
            <Field
              className="md:col-span-2"
              label="Approved Action"
              name="action"
              placeholder="Follow up the highest-value proposal"
              required
            />
            <input name="approval_required" type="hidden" value="false" />
            <label className="field-label flex flex-row items-center gap-2 self-end rounded-lg border border-temple-line bg-temple-panelDeep px-3 py-2.5">
              <input className="h-5 w-5 accent-temple-gold" name="approval_required" type="checkbox" value="true" defaultChecked />
              Human approval required
            </label>
            <Field className="md:col-span-3" label="Notes" name="notes" placeholder="Evidence, limits, or exception context" />
            <div className="md:col-span-4">
              <FormNotice feedback={feedback} />
            </div>
            <div className="md:col-span-4">
              <Button icon={Plus} disabled={busy === "/api/revenue-rules"} type="submit">
                {busy === "/api/revenue-rules" ? "Creating..." : "Create Rule"}
              </Button>
            </div>
          </form>
          <RevenueRuleList rules={summary.rows} busy={busy} onStatus={onStatus} />
          <RevenueRuleRunList summary={summary} />
        </>
      )}
    </Panel>
  );
}

function RevenueRuleList({
  rules,
  busy,
  onStatus,
}: {
  rules: RevenueRuleEntry[];
  busy: string;
  onStatus: (id: number, status: string) => Promise<void>;
}) {
  if (!rules.length) {
    return (
      <div className="mt-4">
        <EmptyRow>No revenue rules yet.</EmptyRow>
      </div>
    );
  }
  return (
    <div className="mt-4 grid gap-3 xl:grid-cols-2">
      {rules.slice(0, 10).map((rule) => {
        const nextStatus = rule.status === "active" ? "paused" : "active";
        const statusBusy = busy === `revenue-rule-${rule.id}-${nextStatus}`;
        const retireBusy = busy === `revenue-rule-${rule.id}-retired`;
        return (
          <article key={rule.id} className={cx("temple-row grid gap-2 border-l-4", revenueRuleBorder(rule))}>
            <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
              <div className="grid min-w-0 gap-1">
                <strong className="break-words">#{rule.id} {rule.name}</strong>
                <span className="text-sm text-temple-muted">{rule.strategy_label} - {rule.rule_type_label}</span>
              </div>
              <Badge>{rule.evaluation.decision}</Badge>
            </div>
            <p className="text-sm leading-6 text-temple-muted">{rule.evaluation.message}</p>
            <div className="grid gap-2 sm:grid-cols-2">
              <MiniMetric label="Observed" value={rule.evaluation.metric_value_display} />
              <MiniMetric label={`${rule.evaluation.operator_label} threshold`} value={rule.threshold_display} />
            </div>
            <div className="grid gap-1 border-t border-temple-line pt-2">
              <span className="text-xs font-black uppercase text-temple-muted">Action</span>
              <strong className="break-words text-sm">{rule.action}</strong>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge>{rule.status_label}</Badge>
              <Badge>{rule.metric_label}</Badge>
              {rule.approval_required ? <Badge>approval</Badge> : null}
              {rule.status !== "retired" ? (
                <Button
                  icon={rule.status === "active" ? CirclePause : CirclePlay}
                  variant="secondary"
                  disabled={statusBusy || retireBusy}
                  onClick={() => void onStatus(rule.id, nextStatus)}
                >
                  {statusBusy ? "Updating..." : rule.status === "active" ? "Pause" : "Activate"}
                </Button>
              ) : null}
              {rule.status !== "retired" ? (
                <Button
                  icon={Archive}
                  variant="ghost"
                  disabled={statusBusy || retireBusy}
                  onClick={() => void onStatus(rule.id, "retired")}
                >
                  {retireBusy ? "Retiring..." : "Retire"}
                </Button>
              ) : null}
            </div>
          </article>
        );
      })}
    </div>
  );
}

function revenueRulesFor(dashboard: DashboardPayload): RevenueRulesSummary {
  if (dashboard.revenue_rules) {
    return dashboard.revenue_rules;
  }
  return {
    temple_id: dashboard.status.temple?.id || dashboard.config.active_temple?.id || "main",
    total_count: 0,
    active_count: 0,
    paused_count: 0,
    triggered_count: 0,
    approval_required_count: 0,
    blocked_count: 0,
    apply_count: 0,
    rows: [],
    top_actions: [],
    recent_runs: [],
    policy: [],
  };
}

function RevenueRuleRunList({ summary }: { summary: RevenueRulesSummary }) {
  if (!summary.recent_runs.length) {
    return null;
  }
  return (
    <section className="mt-4 grid gap-2 border-t border-temple-line pt-4">
      <div className="section-heading">
        <h3 className="text-sm font-black uppercase text-temple-muted">Recent Worker Evaluations</h3>
        <Badge>{summary.recent_runs.length}</Badge>
      </div>
      <div className="grid gap-2 xl:grid-cols-2">
        {summary.recent_runs.slice(0, 6).map((run) => (
          <div key={run.id} className={cx("temple-row grid gap-1 border-l-4", run.triggered ? "border-l-temple-gold" : "border-l-temple-blue")}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <strong className="break-words">#{run.rule_id} {run.rule_name}</strong>
              <Badge>{run.decision}</Badge>
            </div>
            <span className="text-sm text-temple-muted">
              {run.metric_label}: {run.metric_value_display} / {run.threshold_display} - {formatTime(run.created_at)}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function revenueRuleBorder(rule: RevenueRuleEntry) {
  if (rule.status === "retired") return "border-l-temple-violet";
  if (rule.status === "paused") return "border-l-temple-blue";
  if (rule.evaluation.severity === "critical") return "border-l-temple-red";
  if (rule.evaluation.severity === "warning") return "border-l-temple-gold";
  if (rule.evaluation.severity === "positive") return "border-l-temple-green";
  return "border-l-temple-blue";
}

function ConversionTrackingPanel({
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
  const hasConversionPayload = Boolean(dashboard.conversions);
  const conversions = conversionSummaryFor(dashboard);
  const convertibleLeads = dashboard.leads.rows.filter((lead) => isConvertibleLead(lead));
  return (
    <section className="mt-4 grid gap-3 rounded-lg border border-temple-line bg-[#10192a] p-3">
      <div className="section-heading">
        <h3 className="flex items-center gap-2 text-base font-black">
          <Check aria-hidden="true" className="text-temple-green" size={18} />
          Conversion Tracking
        </h3>
        <Badge>{conversions.conversion_rate_pct}% booked</Badge>
      </div>
      <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-5">
        <MiniMetric label="Booked Leads" value={String(conversions.converted_count)} />
        <MiniMetric label="Linked Revenue" value={conversions.linked_revenue} />
        <MiniMetric label="Average Deal" value={conversions.average_deal} />
        <MiniMetric label="Win Rate" value={`${conversions.win_rate_pct}%`} />
        <MiniMetric label="Lost Value" value={conversions.lost_value} />
      </div>
      {!hasConversionPayload ? (
        <EmptyRow>Restart the web server to load the v2.5 conversion APIs before recording booked lead income.</EmptyRow>
      ) : convertibleLeads.length ? (
        <form
          noValidate
          className="grid gap-3 border-t border-temple-line pt-4 md:grid-cols-4"
          onSubmit={(event) => onSubmit(event, "/api/conversions/record", "Conversion recorded")}
        >
          <SelectField label="Lead" name="lead_id" defaultValue="">
            <option value="">Choose lead</option>
            {convertibleLeads.map((lead) => (
              <option key={lead.id} value={lead.id}>
                #{lead.id} {lead.title} - {lead.estimated_value}
              </option>
            ))}
          </SelectField>
          <Field label="Amount" name="amount" inputMode="decimal" placeholder="Booked amount" required />
          <SelectField label="Currency" name="currency" defaultValue="GBP">
            <option value="GBP">GBP</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
            <option value="BTC">BTC</option>
            <option value="LTC">LTC</option>
            <option value="XMR">XMR</option>
          </SelectField>
          <Field label="GBP Equivalent" name="gbp_equivalent" inputMode="decimal" placeholder="Required outside GBP" />
          <Field label="Date" name="date" type="date" />
          <Field className="md:col-span-2" label="Source" name="source" placeholder="Defaults to selected lead" />
          <Field label="Note" name="note" placeholder="Outcome note" />
          <div className="md:col-span-4">
            <FormNotice feedback={feedback} />
          </div>
          <div className="md:col-span-4">
            <Button icon={Coins} disabled={busy === "/api/conversions/record"} type="submit">
              {busy === "/api/conversions/record" ? "Recording..." : "Record Conversion"}
            </Button>
          </div>
        </form>
      ) : (
        <EmptyRow>Move a lead to qualified, proposal, or won before recording booked income.</EmptyRow>
      )}
      <div className="grid gap-3 xl:grid-cols-2">
        <ConversionStrategyList conversions={conversions} />
        <ConversionEvidenceList conversions={conversions} />
      </div>
    </section>
  );
}

function ConversionStrategyList({ conversions }: { conversions: ConversionSummary }) {
  const rows = conversions.by_strategy.slice(0, 5);
  if (!rows.length) {
    return <EmptyRow>No strategy conversion evidence yet.</EmptyRow>;
  }
  return (
    <section className="grid content-start gap-2">
      <h4 className="text-xs font-black uppercase text-temple-muted">Strategy Conversion</h4>
      {rows.map((row) => (
        <div key={row.id} className="temple-row grid gap-2">
          <div className="flex items-center justify-between gap-3">
            <strong className="break-words">{row.name}</strong>
            <b className="text-xs font-black uppercase text-temple-green">{row.conversion_rate_pct}%</b>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-[#172238]" aria-hidden="true">
            <span className="block h-full rounded-full bg-temple-green" style={{ width: `${Math.min(row.conversion_rate_pct, 100)}%` }} />
          </div>
          <span className="text-sm text-temple-muted">
            {row.converted_count}/{row.lead_count} booked - {row.linked_revenue} linked - {row.average_deal} avg
          </span>
        </div>
      ))}
    </section>
  );
}

function ConversionEvidenceList({ conversions }: { conversions: ConversionSummary }) {
  const recent = conversions.recent.slice(0, 3);
  const lost = conversions.lost_notes.slice(0, 3);
  return (
    <section className="grid content-start gap-2">
      <h4 className="text-xs font-black uppercase text-temple-muted">Evidence Notes</h4>
      {recent.length ? (
        recent.map((lead) => (
          <div key={`conversion-${lead.id}`} className="temple-row grid gap-1 border-l-4 border-l-temple-green">
            <strong className="break-words">Won: {lead.title}</strong>
            <span className="text-sm text-temple-muted">
              {lead.converted_at || lead.closed_at || "Booked"} - {lead.converted_source || lead.source || "lead conversion"}
            </span>
          </div>
        ))
      ) : (
        <EmptyRow>No booked lead conversions yet.</EmptyRow>
      )}
      {lost.length ? (
        lost.map((lead) => (
          <div key={`lost-${lead.id}`} className="temple-row grid gap-1 border-l-4 border-l-temple-gold">
            <strong className="break-words">Lost: {lead.title}</strong>
            <span className="text-sm text-temple-muted">
              {lead.estimated_value} at risk - {lead.notes || lead.next_action || "Capture a reason before retrying."}
            </span>
          </div>
        ))
      ) : null}
    </section>
  );
}

function isConvertibleLead(lead: LeadEntry) {
  return !lead.converted_income_id && ["qualified", "proposal", "won"].includes(lead.stage);
}

function conversionSummaryFor(dashboard: DashboardPayload): ConversionSummary {
  if (dashboard.conversions) {
    return dashboard.conversions;
  }
  const templeId = dashboard.status.temple?.id || dashboard.config.active_temple?.id || "main";
  return {
    temple_id: templeId,
    total_leads: dashboard.leads.total_count,
    open_count: dashboard.leads.open_count,
    won_count: dashboard.leads.counts.won || 0,
    lost_count: dashboard.leads.counts.lost || 0,
    closed_count: (dashboard.leads.counts.won || 0) + (dashboard.leads.counts.lost || 0),
    converted_count: 0,
    conversion_rate_pct: 0,
    win_rate_pct: 0,
    linked_revenue: "£0.00",
    linked_revenue_minor: 0,
    average_deal: "£0.00",
    average_deal_minor: 0,
    open_weighted_value: dashboard.leads.weighted_value,
    open_weighted_value_minor: dashboard.leads.weighted_value_minor,
    lost_value: "£0.00",
    lost_value_minor: 0,
    by_strategy: [],
    recent: [],
    lost_notes: [],
  };
}

function LeadIntakeForm({
  dashboard,
  busy,
  feedback,
  onSubmit,
}: {
  dashboard: DashboardPayload;
  busy: boolean;
  feedback?: WorkflowFeedback;
  onSubmit: (event: FormEvent<HTMLFormElement>, path: string, success: string) => void;
}) {
  return (
    <form
      noValidate
      className="mt-4 grid gap-3 border-t border-temple-line pt-4 md:grid-cols-4"
      onSubmit={(event) => onSubmit(event, "/api/leads", "Lead created")}
    >
      <Field label="Lead" name="title" placeholder="Client or opportunity name" required />
      <Field label="Contact" name="contact" placeholder="Person or company" />
      <Field label="Source" name="source" placeholder="Referral, inbound, marketplace" required />
      <StrategySelect label="Strategy" name="strategy" channels={dashboard.config.channels} />
      <Field label="Offer" name="offer" placeholder="Paid service, product, retainer" required />
      <Field label="Estimated Value" name="estimated_value" inputMode="decimal" placeholder="500.00" required />
      <Field label="Probability %" name="probability" inputMode="decimal" placeholder="60" defaultValue="50" required />
      <Field label="Follow Up" name="follow_up_on" type="date" />
      <Field className="md:col-span-2" label="Next Action" name="next_action" placeholder="Send proposal, call, reply, draft outreach" required />
      <SelectField label="Stage" name="stage" defaultValue="new">
        {dashboard.leads.stages.map((stage) => (
          <option key={stage.id} value={stage.id}>
            {stage.label}
          </option>
        ))}
      </SelectField>
      <Field label="Notes" name="notes" placeholder="Useful context" />
      <div className="md:col-span-4">
        <FormNotice feedback={feedback} />
      </div>
      <div className="md:col-span-4">
        <Button icon={Plus} disabled={busy} type="submit">
          {busy ? "Creating..." : "Create Lead"}
        </Button>
      </div>
    </form>
  );
}

function LeadBoard({
  leads,
  stages,
  busy,
  onAdvance,
}: {
  leads: LeadEntry[];
  stages: DashboardPayload["leads"]["stages"];
  busy: string;
  onAdvance: (id: number, stage: string) => Promise<void>;
}) {
  return (
    <div className="grid gap-3 xl:grid-cols-3">
      {stages.map((stage) => {
        const stageLeads = leads.filter((lead) => lead.stage === stage.id);
        return (
          <section key={stage.id} className="grid content-start gap-2 rounded-lg border border-temple-line bg-[#10192a] p-3">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-black uppercase text-temple-muted">{stage.label}</h3>
              <Badge>{stage.count}</Badge>
            </div>
            <span className="text-xs font-bold text-temple-muted">{stage.value} total value</span>
            {stageLeads.length ? (
              stageLeads.slice(0, 8).map((lead) => <LeadCard key={lead.id} lead={lead} busy={busy} onAdvance={onAdvance} />)
            ) : (
              <EmptyRow>No leads in this stage.</EmptyRow>
            )}
          </section>
        );
      })}
    </div>
  );
}

function LeadQueue({
  title,
  items,
  empty,
  busy,
  onAdvance,
}: {
  title: string;
  items: LeadEntry[];
  empty: string;
  busy: string;
  onAdvance: (id: number, stage: string) => Promise<void>;
}) {
  return (
    <section className="grid gap-2 rounded-lg border border-temple-line bg-[#10192a] p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-black uppercase text-temple-muted">{title}</h3>
        <Badge>{items.length}</Badge>
      </div>
      {items.length ? items.map((lead) => <LeadCard key={`${title}-${lead.id}`} lead={lead} busy={busy} compact onAdvance={onAdvance} />) : <EmptyRow>{empty}</EmptyRow>}
    </section>
  );
}

function LeadCard({
  lead,
  busy,
  compact = false,
  onAdvance,
}: {
  lead: LeadEntry;
  busy: string;
  compact?: boolean;
  onAdvance: (id: number, stage: string) => Promise<void>;
}) {
  const next = nextLeadStage[lead.stage];
  const isBusy = next ? busy === `lead-${lead.id}-${next}` : false;
  return (
    <article className={cx("temple-row grid gap-2 border-l-4", leadPriorityBorder(lead.priority_label))}>
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
        <div className="grid min-w-0 gap-1">
          <strong className="break-words">
            #{lead.id} {lead.title}
          </strong>
          <span className="text-sm text-temple-muted">
            {lead.offer} - {lead.weighted_value} weighted
          </span>
        </div>
        <b className="text-xs font-black uppercase text-temple-gold sm:text-right">{lead.priority_label}</b>
      </div>
      <div className="grid gap-2 text-sm text-temple-muted">
        <span>{lead.contact || lead.source || "No contact set"}</span>
        <span>{leadFollowUpText(lead)}</span>
        {!compact && lead.next_action ? <span>Next: {lead.next_action}</span> : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{lead.priority_score}/100</Badge>
        <Badge>{lead.probability_pct}%</Badge>
        <Badge>{lead.stage_label}</Badge>
        {next ? (
          <Button icon={ArrowRight} variant="secondary" disabled={isBusy} onClick={() => void onAdvance(lead.id, next)}>
            {isBusy ? "Moving..." : `Move to ${titleCase(next)}`}
          </Button>
        ) : null}
      </div>
    </article>
  );
}

function leadPriorityBorder(priority: string) {
  if (priority === "hot") {
    return "border-l-temple-green";
  }
  if (priority === "warm") {
    return "border-l-temple-gold";
  }
  if (priority === "nurture") {
    return "border-l-temple-blue";
  }
  return "border-l-temple-violet";
}

function leadFollowUpText(lead: LeadEntry) {
  if (!lead.follow_up_on) {
    return "Follow-up not scheduled";
  }
  if (lead.follow_up_state === "overdue") {
    return `Overdue follow-up: ${lead.follow_up_on}`;
  }
  if (lead.follow_up_state === "due_today") {
    return `Due today: ${lead.follow_up_on}`;
  }
  return `Follow-up: ${lead.follow_up_on}`;
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
  const worker = dashboard.worker;
  const recentCycles = worker.recent_cycles || [];
  const latestCycle = worker.latest_cycle || recentCycles[0];
  const liveness = worker.liveness?.state || worker.state;
  const readiness = worker.readiness?.state || (worker.state === "running" ? "ready" : "not ready");
  return (
    <Panel
      title="Worker Operations"
      icon={Activity}
      wide
      actions={
        <Button icon={Activity} variant="secondary" disabled={busy === "pulse"} onClick={onPulse}>
          {busy === "pulse" ? "Running..." : "Run Worker Cycle"}
        </Button>
      }
    >
      <div className="mb-4 grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
        <MiniMetric label="Liveness" value={titleCase(liveness.replace(/_/g, " "))} />
        <MiniMetric label="Readiness" value={titleCase(readiness.replace(/_/g, " "))} />
        <MiniMetric label="Latest Cycle" value={latestCycle ? `#${latestCycle.id} ${titleCase(latestCycle.status)}` : "No cycle"} />
        <MiniMetric label="Duration" value={latestCycle ? `${latestCycle.duration_ms.toFixed(2)} ms` : "Not measured"} />
      </div>
      <section className="mb-4 grid gap-2 border-y border-temple-line py-4">
        <div className="section-heading">
          <h3 className="text-sm font-black uppercase text-temple-muted">Recent Worker Cycles</h3>
          <Badge>{recentCycles.length}</Badge>
        </div>
        {recentCycles.length ? (
          <div className="grid gap-2 xl:grid-cols-2">
            {recentCycles.slice(0, 6).map((cycle) => (
              <div
                key={cycle.id}
                className={cx(
                  "temple-row grid gap-1 border-l-4",
                  cycle.status === "succeeded"
                    ? "border-l-temple-green"
                    : cycle.status === "partial" || cycle.status === "interrupted"
                      ? "border-l-temple-gold"
                      : "border-l-temple-red",
                )}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <strong>#{cycle.id} {titleCase(cycle.trigger)} Cycle</strong>
                  <Badge>{titleCase(cycle.status)}</Badge>
                </div>
                <span className="text-sm text-temple-muted">
                  {cycle.commands.succeeded}/{cycle.commands.total} commands; {cycle.rules.triggered}/{cycle.rules.evaluated} rules; {cycle.approvals.required} approval gates
                </span>
                <small className="text-temple-muted">
                  {formatTime(cycle.finished_at || cycle.started_at)} - {cycle.duration_ms.toFixed(2)} ms
                </small>
              </div>
            ))}
          </div>
        ) : (
          <EmptyRow>No worker cycles recorded yet.</EmptyRow>
        )}
      </section>
      <div className="section-heading">
        <h3 className="flex items-center gap-2 text-sm font-black uppercase text-temple-muted">
          <FileText aria-hidden="true" size={17} /> Temple Log
        </h3>
      </div>
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
  const isGenerated = report.generated !== false && Boolean(report.markdown);
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
          <Button icon={Download} disabled={!isGenerated} onClick={onDownload}>
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
      {isGenerated ? (
        <pre className="max-h-[520px] min-h-[320px] overflow-auto rounded-lg border border-temple-line bg-[#091020] p-4 text-sm leading-6 text-[#d9e5ff] whitespace-pre-wrap break-words">
          {report.markdown}
        </pre>
      ) : (
        <div className="grid min-h-[320px] place-items-center rounded-lg border border-dashed border-temple-line bg-[#091020] p-6 text-center text-sm text-temple-muted">
          No report has been generated for this session.
        </div>
      )}
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
