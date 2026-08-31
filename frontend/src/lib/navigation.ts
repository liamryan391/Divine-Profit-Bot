export type DashboardView = "overview" | "temples" | "strategies" | "leads" | "receivables" | "imports" | "approvals" | "reports" | "settings";

export interface DashboardViewMeta {
  id: DashboardView;
  label: string;
  kicker: string;
  summary: string;
}

export const defaultDashboardView: DashboardView = "overview";

export const dashboardViews: DashboardViewMeta[] = [
  {
    id: "overview",
    label: "Overview",
    kicker: "Command View",
    summary: "Quota health, top offering, worker state, and pending approvals.",
  },
  {
    id: "temples",
    label: "Temples",
    kicker: "Temple Ops",
    summary: "Temple switching, quota control, exceptions, and scoped status.",
  },
  {
    id: "strategies",
    label: "Strategies",
    kicker: "Revenue Signals",
    summary: "Ranked opportunities, ROI, priority calls, and recent income.",
  },
  {
    id: "leads",
    label: "Leads",
    kicker: "Pipeline",
    summary: "Lead intake, stage movement, weighted value, due follow-ups, and priority scoring.",
  },
  {
    id: "receivables",
    label: "Receivables",
    kicker: "Collection Desk",
    summary: "Money owed, due and overdue exposure, payment collection, and human-approved reminders.",
  },
  {
    id: "imports",
    label: "Imports",
    kicker: "Income Intake",
    summary: "Manual income entry, CSV import review, external signals, and ledger checks.",
  },
  {
    id: "approvals",
    label: "Approvals",
    kicker: "Human Gate",
    summary: "Draft review, approval status, and worker activity.",
  },
  {
    id: "reports",
    label: "Reports",
    kicker: "Review Forge",
    summary: "Weekly and monthly reports, ROI context, and upgrade path.",
  },
  {
    id: "settings",
    label: "Settings",
    kicker: "Control Room",
    summary: "Configuration, quotas, exceptions, external signals, and daemon log.",
  },
];

export const dashboardViewMeta: Record<DashboardView, DashboardViewMeta> = {
  overview: dashboardViews[0],
  temples: dashboardViews[1],
  strategies: dashboardViews[2],
  leads: dashboardViews[3],
  receivables: dashboardViews[4],
  imports: dashboardViews[5],
  approvals: dashboardViews[6],
  reports: dashboardViews[7],
  settings: dashboardViews[8],
};

export function viewHref(view: DashboardView) {
  return `#/${view}`;
}

export function viewFromHash(hash: string): DashboardView {
  const raw = hash.replace(/^#\/?/, "").split(/[/?]/)[0];
  return isDashboardView(raw) ? raw : defaultDashboardView;
}

function isDashboardView(value: string): value is DashboardView {
  return dashboardViews.some((view) => view.id === value);
}
