import { CalendarClock, ClipboardList, FileText, Landmark, LayoutDashboard, ListChecks, LogOut, ReceiptText, Settings, Target, TrendingUp, Upload } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import type { AuthStatus, Temple, WorkerStatus } from "../types";
import { accountLabel, cx } from "../lib/format";
import { dashboardViewMeta, dashboardViews, type DashboardView, viewHref } from "../lib/navigation";
import { BrandLockup } from "./brand";
import { Button, SelectField, StatusPill, Toolbar, WorkerPill } from "./ui";

const navIcons: Record<DashboardView, LucideIcon> = {
  overview: LayoutDashboard,
  temples: Landmark,
  strategies: TrendingUp,
  leads: Target,
  receivables: ReceiptText,
  follow_ups: CalendarClock,
  reconciliation: ListChecks,
  imports: Upload,
  approvals: ClipboardList,
  reports: FileText,
  settings: Settings,
};

export function ScreenFrame({ children }: { children: ReactNode }) {
  return <main className="grid min-h-screen place-items-center px-4 py-8 sm:px-6">{children}</main>;
}

export function LoadingPanel() {
  return (
    <section className="temple-panel w-[min(520px,100%)]">
      <BrandLockup />
      <p className="mt-6 text-temple-muted">Opening the temple...</p>
    </section>
  );
}

export function DashboardShell({
  auth,
  activeView,
  activeTempleId,
  temples,
  worker,
  busy,
  pendingApprovals,
  onTempleChange,
  onLogout,
  children,
}: {
  auth: AuthStatus;
  activeView: DashboardView;
  activeTempleId: string;
  temples: Temple[];
  worker: WorkerStatus;
  busy: string;
  pendingApprovals: number;
  onTempleChange: (templeId: string) => void;
  onLogout: () => void;
  children: ReactNode;
}) {
  return (
    <main className="temple-shell">
      <a className="skip-link" href="#dashboard-content">
        Skip to dashboard content
      </a>
      <header className="grid min-h-[132px] min-w-0 gap-5 py-3 pb-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <div className="min-w-0">
          <BrandLockup size="large" />
        </div>
        <Toolbar className="min-w-0 lg:justify-end">
          <SelectField
            className="w-full min-w-0 sm:w-auto sm:min-w-[210px]"
            value={activeTempleId}
            ariaLabel="Active temple"
            onChange={(event) => onTempleChange(event.currentTarget.value)}
          >
            {temples.map((temple) => (
              <option key={temple.id} value={temple.id}>
                {temple.active ? `${temple.name} (active)` : temple.name}
              </option>
            ))}
          </SelectField>
          <StatusPill text={accountLabel(auth)} />
          <WorkerPill worker={worker} />
          <Button icon={LogOut} variant="ghost" disabled={busy === "logout"} onClick={onLogout}>
            Logout
          </Button>
        </Toolbar>
      </header>
      <PrimaryNavigation activeView={activeView} pendingApprovals={pendingApprovals} />
      <section id="dashboard-content" className="min-w-0 outline-none" tabIndex={-1} aria-live="polite" aria-busy={busy ? "true" : undefined}>
        {children}
      </section>
    </main>
  );
}

function PrimaryNavigation({ activeView, pendingApprovals }: { activeView: DashboardView; pendingApprovals: number }) {
  return (
    <nav className="mb-4 -mx-2 overflow-x-auto px-2 pb-2 [scrollbar-width:thin]" aria-label="Primary dashboard" aria-describedby="primary-dashboard-nav-help">
      <p id="primary-dashboard-nav-help" className="sr-only">
        Use these links to switch between dashboard workflow views.
      </p>
      <div className="flex min-w-max gap-2">
        {dashboardViews.map((view) => {
          const Icon = navIcons[view.id];
          const isActive = activeView === view.id;
          return (
            <a
              key={view.id}
              className={cx(
                "inline-flex min-h-11 items-center gap-2 rounded-lg border px-3.5 py-2.5 text-sm font-black transition focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-temple-gold/35 focus-visible:ring-offset-2 focus-visible:ring-offset-[#07101c]",
                isActive
                  ? "border-temple-gold bg-temple-gold text-[#07101c] shadow-glow"
                  : "border-temple-line bg-temple-surface/70 text-temple-muted hover:border-temple-blue hover:text-temple-text",
              )}
              href={viewHref(view.id)}
              aria-current={isActive ? "page" : undefined}
            >
              <Icon aria-hidden="true" size={17} strokeWidth={2.4} />
              <span>{view.label}</span>
              {view.id === "approvals" && pendingApprovals > 0 ? (
                <span
                  className={cx("rounded-md px-1.5 py-0.5 text-xs", isActive ? "bg-[#07101c] text-temple-gold" : "bg-temple-gold text-[#07101c]")}
                  aria-label={`${pendingApprovals} pending approvals`}
                >
                  {pendingApprovals}
                </span>
              ) : null}
            </a>
          );
        })}
      </div>
    </nav>
  );
}

export function ViewHeader({ view }: { view: DashboardView }) {
  const meta = dashboardViewMeta[view];
  return (
    <section className="mb-4 grid min-w-0 gap-3 rounded-lg border border-white/5 bg-temple-surface/45 px-4 py-3 sm:flex sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="mb-1 text-xs font-black uppercase text-temple-muted">{meta.kicker}</p>
        <h2 className="break-words text-2xl font-black text-temple-text">{meta.label}</h2>
      </div>
      <p className="max-w-2xl text-sm leading-6 text-temple-muted sm:text-right">{meta.summary}</p>
    </section>
  );
}

export function MetricGrid({ children }: { children: ReactNode }) {
  return (
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Temple status">
      {children}
    </section>
  );
}

export function DashboardGrid({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={cx("mt-4 grid min-w-0 gap-4 xl:grid-cols-3", className)}>{children}</section>;
}
