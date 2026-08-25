import { Activity, Coins, Gauge, Target } from "lucide-react";
import type { FormEvent } from "react";
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
  onJsonForm: JsonFormHandler;
  onImport: (event: FormEvent<HTMLFormElement>) => void;
  onReviewApproval: (id: number, decision: string) => Promise<void>;
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

function TemplesView({ dashboard, busy, onJsonForm }: DashboardViewContentProps) {
  return (
    <DashboardGrid>
      <TempleSwitchboardPanel dashboard={dashboard} busy={busy} onSubmit={onJsonForm} />
      <QuotaControlPanel dashboard={dashboard} busy={busy} onSubmit={onJsonForm} />
      <MercyExceptionPanel busy={busy} onSubmit={onJsonForm} />
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

function ImportsView({ dashboard, external, importResult, busy, onJsonForm, onImport, onRefreshExternal }: DashboardViewContentProps) {
  return (
    <DashboardGrid>
      <CommandAltarPanel dashboard={dashboard} busy={busy} onSubmit={onJsonForm} />
      <ImportAltarPanel dashboard={dashboard} busy={busy} importResult={importResult} onImport={onImport} />
      <ExternalSignalsPanel external={external} busy={busy} onRefresh={onRefreshExternal} />
      <RecentIncomePanel dashboard={dashboard} />
    </DashboardGrid>
  );
}

function ApprovalsView({ dashboard, busy, onJsonForm, onReviewApproval, onPulseWorker }: DashboardViewContentProps) {
  return (
    <DashboardGrid>
      <ApprovalQueuePanel dashboard={dashboard} busy={busy} onSubmit={onJsonForm} onReview={onReviewApproval} />
      <TempleLogPanel dashboard={dashboard} busy={busy} onPulse={onPulseWorker} />
    </DashboardGrid>
  );
}

function ReportsView({ dashboard, report, busy, onGenerateReport, onDownloadReport }: DashboardViewContentProps) {
  return (
    <DashboardGrid>
      <ReportForgePanel report={report} busy={busy} onGenerate={onGenerateReport} onDownload={onDownloadReport} />
      <StrategyRoiPanel dashboard={dashboard} />
      <UpgradePathPanel dashboard={dashboard} />
    </DashboardGrid>
  );
}

function SettingsView({ dashboard, external, busy, onJsonForm, onPulseWorker, onRefreshExternal }: DashboardViewContentProps) {
  return (
    <DashboardGrid>
      <ConfigPanel dashboard={dashboard} />
      <AccountRecoveryPanel dashboard={dashboard} busy={busy} onSubmit={onJsonForm} />
      <QuotaControlPanel dashboard={dashboard} busy={busy} onSubmit={onJsonForm} />
      <MercyExceptionPanel busy={busy} onSubmit={onJsonForm} />
      <ExternalSignalsPanel external={external} busy={busy} onRefresh={onRefreshExternal} />
      <TempleLogPanel dashboard={dashboard} busy={busy} onPulse={onPulseWorker} />
    </DashboardGrid>
  );
}
