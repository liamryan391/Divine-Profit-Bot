import { LogOut } from "lucide-react";
import type { ReactNode } from "react";
import type { AuthStatus, Temple, WorkerStatus } from "../types";
import { accountLabel } from "../lib/format";
import { BrandLockup } from "./brand";
import { Button, SelectField, StatusPill, Toolbar, WorkerPill } from "./ui";

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
  activeTempleId,
  temples,
  worker,
  busy,
  onTempleChange,
  onLogout,
  children,
}: {
  auth: AuthStatus;
  activeTempleId: string;
  temples: Temple[];
  worker: WorkerStatus;
  busy: string;
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
      {children}
    </main>
  );
}

export function MetricGrid({ children }: { children: ReactNode }) {
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="Temple status">
      {children}
    </section>
  );
}

export function DashboardGrid({ children }: { children: ReactNode }) {
  return <section className="mt-4 grid gap-4 lg:grid-cols-3">{children}</section>;
}
