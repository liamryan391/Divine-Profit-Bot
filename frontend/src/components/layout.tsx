import { ClipboardList, FileText, Landmark, LayoutDashboard, LogOut, Settings, TrendingUp, Upload } from "lucide-react";
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
  imports: Upload,
  approvals: ClipboardList,
  reports: FileText,
  settings: Settings,
};

export function ScreenFrame({ children }: { children: ReactNode }) {
  return <main className="grid min-h-screen place-items-center px-6 py-8">{children}</main>;
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
      <header className="flex min-h-[132px] flex-col gap-5 py-3 pb-6 lg:flex-row lg:items-center lg:justify-between">
        <BrandLockup size="large" />
        <Toolbar className="lg:justify-end">
          <SelectField
            className="w-auto min-w-[210px]"
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
      {children}
    </main>
  );
}

function PrimaryNavigation({ activeView, pendingApprovals }: { activeView: DashboardView; pendingApprovals: number }) {
  return (
    <nav className="mb-4 overflow-x-auto pb-2" aria-label="Primary dashboard">
      <div className="flex min-w-max gap-2">
        {dashboardViews.map((view) => {
          const Icon = navIcons[view.id];
          const isActive = activeView === view.id;
          return (
            <a
              key={view.id}
              className={cx(
                "inline-flex min-h-11 items-center gap-2 rounded-lg border px-3.5 py-2.5 text-sm font-black transition",
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
                <span className={cx("rounded-md px-1.5 py-0.5 text-xs", isActive ? "bg-[#07101c] text-temple-gold" : "bg-temple-gold text-[#07101c]")}>
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
    <section className="mb-4 grid gap-3 rounded-lg border border-white/5 bg-temple-surface/45 px-4 py-3 sm:flex sm:items-center sm:justify-between">
      <div>
        <p className="mb-1 text-xs font-black uppercase tracking-[0.08em] text-temple-muted">{meta.kicker}</p>
        <h2 className="text-2xl font-black text-temple-text">{meta.label}</h2>
      </div>
      <p className="max-w-2xl text-sm leading-6 text-temple-muted">{meta.summary}</p>
    </section>
  );
}

export function MetricGrid({ children }: { children: ReactNode }) {
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="Temple status">
      {children}
    </section>
  );
}

export function DashboardGrid({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={cx("mt-4 grid gap-4 lg:grid-cols-3", className)}>{children}</section>;
}
