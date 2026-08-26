import { Activity, Coins, Gauge, Target } from "lucide-react";
import type { FormEvent } from "react";
import type { WorkflowFeedbackMap } from "../lib/forms";
import type { DashboardView } from "../lib/navigation";
import { capitalize, runningStrategyCount } from "../lib/format";
import type { DashboardPayload, ExternalSnapshot, ImportResult, ReportPayload } from "../types";
import {
  AccountRecoveryPanel,
  ApprovalQueuePanel,
  CommandAltarPanel,
  ConfigPanel,
  ExternalSignalsPanel,
  ImportAltarPanel,
  LeadPipelinePanel,
  MercyExceptionPanel,
  PriorityCallsPanel,
  QuotaControlPanel,
  QuotaProgressPanel,
  RecentIncomePanel,
  ReportForgePanel,
  StrategiesPanel,
  StrategyRoiPanel,
  TempleLogPanel,
  TempleSwitchboardPanel,
  TopOffering,
  UpgradePathPanel,
  UrgentApprovalsPanel,
} from "./dashboard-panels";
import { DashboardGrid, MetricGrid, ViewHeader } from "./layout";
import { MetricCard } from "./ui";

type JsonFormHandler = (event: FormEvent<HTMLFormElement>, path: string, success: string, resetForm?: boolean) => void;

interface DashboardViewContentProps {
  view: DashboardView;
  dashboard: DashboardPayload;
  external: ExternalSnapshot | null;
  report: ReportPayload;
  importResult: ImportResult | null;
  busy: string;
  feedback: WorkflowFeedbackMap;
  onJsonForm: JsonFormHandler;
  onImport: (event: FormEvent<HTMLFormElement>) => void;
  onReviewApproval: (id: number, decision: string) => Promise<void>;
  onAdvanceLead: (id: number, stage: string) => Promise<void>;
  onPulseWorker: () => void;
  onRefreshExternal: () => void;
  onGenerateReport: () => void;
  onDownloadReport: () => void;
}

export function DashboardViewContent(props: DashboardViewContentProps) {
  return (
    <>
      <ViewHeader view={props.view} />
      {props.view === "overview" ? <OverviewView {...props} /> : null}
      {props.view === "temples" ? <TemplesView {...props} /> : null}
      {props.view === "strategies" ? <StrategiesView {...props} /> : null}
      {props.view === "leads" ? <LeadsView {...props} /> : null}
      {props.view === "imports" ? <ImportsView {...props} /> : null}
      {props.view === "approvals" ? <ApprovalsView {...props} /> : null}
      {props.view === "reports" ? <ReportsView {...props} /> : null}
      {props.view === "settings" ? <SettingsView {...props} /> : null}
    </>
  );
}

function OverviewView({ dashboard, busy, onReviewApproval, onPulseWorker }: DashboardViewContentProps) {
  return (
    <>
      <MetricGrid>
        <MetricCard
          accent="gold"
          icon={Target}
          label="Current Quota"
          value={dashboard.status.remaining}
          detail={`${capitalize(dashboard.status.period.name)} target: ${dashboard.status.quota}`}
        />
        <MetricCard
          accent="green"
          icon={Coins}
          label="Income This Period"
          value={dashboard.status.earned}
          detail={`Progress: ${dashboard.status.progress_pct}%`}
        />
        <MetricCard
          accent="blue"
          icon={Activity}
          label="Active Modules"
          value={String(dashboard.config.channels.length)}
          detail={`${runningStrategyCount(dashboard)} active strategy signals`}
        />
        <MetricCard
          accent="violet"
          icon={Gauge}
          label="Temple Level"
          value={dashboard.version}
          detail={dashboard.status.remaining_minor === 0 ? "Upgrade window unlocked" : "Next: v2.4 growth track"}
        />
      </MetricGrid>
      <QuotaProgressPanel dashboard={dashboard} />
      <TopOffering item={dashboard.top_opportunity} />
      <DashboardGrid>
        <PriorityCallsPanel dashboard={dashboard} />
        <UrgentApprovalsPanel dashboard={dashboard} busy={busy} onReview={onReviewApproval} />
        <TempleLogPanel dashboard={dashboard} busy={busy} onPulse={onPulseWorker} />
      </DashboardGrid>
    </>
  );
}

function TemplesView({ dashboard, busy, feedback, onJsonForm }: DashboardViewContentProps) {
  return (
    <DashboardGrid>
      <TempleSwitchboardPanel dashboard={dashboard} busy={busy} feedback={feedback["/api/temple/create"]} onSubmit={onJsonForm} />
      <QuotaControlPanel dashboard={dashboard} busy={busy} feedback={feedback} onSubmit={onJsonForm} />
      <MercyExceptionPanel busy={busy} feedback={feedback["/api/exception"]} onSubmit={onJsonForm} />
      <ConfigPanel dashboard={dashboard} />
      <RecentIncomePanel dashboard={dashboard} />
    </DashboardGrid>
  );
}

function StrategiesView({ dashboard }: DashboardViewContentProps) {
  return (
    <>
      <TopOffering item={dashboard.top_opportunity} />
      <DashboardGrid>
        <StrategiesPanel dashboard={dashboard} />
        <StrategyRoiPanel dashboard={dashboard} />
        <PriorityCallsPanel dashboard={dashboard} />
        <RecentIncomePanel dashboard={dashboard} />
      </DashboardGrid>
    </>
  );
}

function LeadsView({ dashboard, busy, feedback, onJsonForm, onAdvanceLead }: DashboardViewContentProps) {
  return (
    <>
      <div className="mt-4">
        <LeadPipelinePanel
          dashboard={dashboard}
          busy={busy}
          feedback={feedback["/api/leads"]}
          onSubmit={onJsonForm}
          onAdvance={onAdvanceLead}
        />
      </div>
      <DashboardGrid>
        <StrategiesPanel dashboard={dashboard} />
        <RecentIncomePanel dashboard={dashboard} />
      </DashboardGrid>
    </>
  );
}

function ImportsView({ dashboard, external, importResult, busy, feedback, onJsonForm, onImport, onRefreshExternal }: DashboardViewContentProps) {
  return (
    <DashboardGrid>
      <CommandAltarPanel dashboard={dashboard} busy={busy} feedback={feedback["/api/income"]} onSubmit={onJsonForm} />
      <ImportAltarPanel dashboard={dashboard} busy={busy} feedback={feedback.import} importResult={importResult} onImport={onImport} />
      <ExternalSignalsPanel external={external} busy={busy} onRefresh={onRefreshExternal} />
      <RecentIncomePanel dashboard={dashboard} />
    </DashboardGrid>
  );
}

function ApprovalsView({ dashboard, busy, feedback, onJsonForm, onReviewApproval, onPulseWorker }: DashboardViewContentProps) {
  return (
    <DashboardGrid>
      <ApprovalQueuePanel dashboard={dashboard} busy={busy} feedback={feedback["/api/approval/draft"]} onSubmit={onJsonForm} onReview={onReviewApproval} />
      <TempleLogPanel dashboard={dashboard} busy={busy} onPulse={onPulseWorker} />
    </DashboardGrid>
  );
}

function ReportsView({ dashboard, report, busy, feedback, onGenerateReport, onDownloadReport }: DashboardViewContentProps) {
  return (
    <DashboardGrid>
      <ReportForgePanel report={report} busy={busy} feedback={feedback.report} onGenerate={onGenerateReport} onDownload={onDownloadReport} />
      <StrategyRoiPanel dashboard={dashboard} />
      <UpgradePathPanel dashboard={dashboard} />
    </DashboardGrid>
  );
}

function SettingsView({ dashboard, external, busy, feedback, onJsonForm, onPulseWorker, onRefreshExternal }: DashboardViewContentProps) {
  return (
    <DashboardGrid>
      <ConfigPanel dashboard={dashboard} />
      <AccountRecoveryPanel dashboard={dashboard} busy={busy} feedback={feedback["/api/account/profile"]} onSubmit={onJsonForm} />
      <QuotaControlPanel dashboard={dashboard} busy={busy} feedback={feedback} onSubmit={onJsonForm} />
      <MercyExceptionPanel busy={busy} feedback={feedback["/api/exception"]} onSubmit={onJsonForm} />
      <ExternalSignalsPanel external={external} busy={busy} onRefresh={onRefreshExternal} />
      <TempleLogPanel dashboard={dashboard} busy={busy} onPulse={onPulseWorker} />
    </DashboardGrid>
  );
}
