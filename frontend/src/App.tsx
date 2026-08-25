import {
  Activity,
  BarChart3,
  Check,
  ClipboardList,
  Coins,
  Download,
  FileText,
  Gauge,
  Landmark,
  LogOut,
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
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type FormEvent,
  type ReactNode,
} from "react";
import { ApiError, apiRequest } from "./api";
import type {
  ApprovalAction,
  ApprovalSummary,
  AuthResponse,
  AuthStatus,
  DashboardPayload,
  ExternalSnapshot,
  ImportResult,
  Opportunity,
  ReportPayload,
  StrategyRoi,
  StrategyRoiRow,
  WorkerStatus,
} from "./types";

type ButtonVariant = "primary" | "secondary" | "ghost";
type Accent = "gold" | "green" | "blue" | "violet" | "red";
type IconType = typeof Activity;

const buttonVariants: Record<ButtonVariant, string> = {
  primary: "temple-button-primary",
  secondary: "temple-button-secondary",
  ghost: "temple-button-ghost",
};

const accentText: Record<Accent, string> = {
  gold: "text-temple-gold",
  green: "text-temple-green",
  blue: "text-temple-blue",
  violet: "text-temple-violet",
  red: "text-temple-red",
};

const accentBorder: Record<Accent, string> = {
  gold: "border-l-temple-gold",
  green: "border-l-temple-green",
  blue: "border-l-temple-blue",
  violet: "border-l-temple-violet",
  red: "border-l-temple-red",
};

function App() {
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [external, setExternal] = useState<ExternalSnapshot | null>(null);
  const [report, setReport] = useState<ReportPayload | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState("");
  const toastTimer = useRef<number | undefined>(undefined);

  const showToast = useCallback((message: string) => {
    setToast(message);
    if (toastTimer.current) {
      window.clearTimeout(toastTimer.current);
    }
    toastTimer.current = window.setTimeout(() => setToast(""), 2800);
  }, []);

  const applyDashboard = useCallback((payload: DashboardPayload) => {
    setDashboard(payload);
    setAuth(payload.auth);
    setReport((current) => current ?? payload.report);
  }, []);

  const handleApiError = useCallback(
    (error: unknown, announce = true) => {
      if (error instanceof ApiError) {
        const authPayload = authFromPayload(error.payload);
        if (authPayload) {
          setAuth(authPayload);
          setDashboard(null);
          return;
        }
        if (announce) {
          showToast(error.message);
        }
        return;
      }
      if (announce) {
        showToast(error instanceof Error ? error.message : "Unexpected request failure");
      }
    },
    [showToast],
  );

  const refreshDashboard = useCallback(
    async (announceErrors = true) => {
      try {
        const payload = await apiRequest<DashboardPayload>("/api/status");
        applyDashboard(payload);
      } catch (error) {
        handleApiError(error, announceErrors);
      }
    },
    [applyDashboard, handleApiError],
  );

  const refreshExternalConnections = useCallback(
    async (announce = true) => {
      setBusy("external");
      try {
        const payload = await apiRequest<{ external: ExternalSnapshot }>("/api/external");
        setExternal(payload.external);
        if (announce) {
          showToast("External signals refreshed");
        }
      } catch (error) {
        handleApiError(error, announce);
      } finally {
        setBusy("");
      }
    },
    [handleApiError, showToast],
  );

  const boot = useCallback(async () => {
    try {
      const payload = await apiRequest<AuthResponse>("/api/auth/status");
      setAuth(payload.auth);
      if (canLoadDashboard(payload.auth)) {
        const state = await apiRequest<DashboardPayload>("/api/status");
        applyDashboard(state);
        try {
          const externalPayload = await apiRequest<{ external: ExternalSnapshot }>("/api/external");
          setExternal(externalPayload.external);
        } catch {
          setExternal(null);
        }
      }
    } catch (error) {
      handleApiError(error);
    }
  }, [applyDashboard, handleApiError]);

  useEffect(() => {
    void boot();
  }, [boot]);

  const needsGate = auth ? auth.enabled && (!auth.authenticated || auth.setup_required) : false;

  useEffect(() => {
    if (!auth || needsGate) {
      return undefined;
    }
    const interval = window.setInterval(() => {
      void refreshDashboard(false);
    }, 10000);
    return () => window.clearInterval(interval);
  }, [auth, needsGate, refreshDashboard]);

  useEffect(() => {
    return () => {
      if (toastTimer.current) {
        window.clearTimeout(toastTimer.current);
      }
    };
  }, []);

  async function handleAuthSubmit(event: FormEvent<HTMLFormElement>, path: string, success: string) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(path);
    try {
      const payload = await apiRequest<{ ok: boolean; auth: AuthStatus; state: DashboardPayload }>(path, {
        method: "POST",
        body: JSON.stringify(formPayload(form)),
      });
      setAuth(payload.auth);
      applyDashboard(payload.state);
      form.reset();
      showToast(success);
      await refreshExternalConnections(false);
    } catch (error) {
      handleApiError(error);
    } finally {
      setBusy("");
    }
  }

  async function handleJsonForm(event: FormEvent<HTMLFormElement>, path: string, success: string) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(path);
    try {
      const payload = await apiRequest<{ ok: boolean; state: DashboardPayload }>(path, {
        method: "POST",
        body: JSON.stringify(formPayload(form)),
      });
      applyDashboard(payload.state);
      form.reset();
      showToast(success);
    } catch (error) {
      handleApiError(error);
    } finally {
      setBusy("");
    }
  }

  async function logout() {
    setBusy("logout");
    try {
      const payload = await apiRequest<AuthResponse>("/api/auth/logout", { method: "POST", body: "{}" });
      setAuth(payload.auth);
      setDashboard(null);
      setExternal(null);
      setReport(null);
      showToast("Signed out");
    } catch (error) {
      handleApiError(error);
    } finally {
      setBusy("");
    }
  }

  async function pulseWorker() {
    setBusy("pulse");
    try {
      const payload = await apiRequest<{ ok: boolean; state: DashboardPayload }>("/api/daemon/run-once", {
        method: "POST",
        body: "{}",
      });
      applyDashboard(payload.state);
      showToast("Worker pulse complete");
    } catch (error) {
      handleApiError(error);
    } finally {
      setBusy("");
    }
  }

  async function switchTemple(templeId: string) {
    if (!templeId) {
      return;
    }
    setBusy("temple-switch");
    try {
      const payload = await apiRequest<{ ok: boolean; temple: { name: string }; state: DashboardPayload }>(
        "/api/temple/switch",
        {
          method: "POST",
          body: JSON.stringify({ temple_id: templeId }),
        },
      );
      applyDashboard(payload.state);
      await refreshExternalConnections(false);
      showToast(`Temple switched to ${payload.temple.name}`);
    } catch (error) {
      handleApiError(error);
    } finally {
      setBusy("");
    }
  }

  async function importCsv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fileInput = form.elements.namedItem("file") as HTMLInputElement | null;
    const file = fileInput?.files?.[0];
    if (!file) {
      showToast("Choose a CSV file first");
      return;
    }
    const sourceType = form.elements.namedItem("source_type") as HTMLSelectElement | null;
    const defaultStrategy = form.elements.namedItem("default_strategy") as HTMLSelectElement | null;
    const dryRun = form.elements.namedItem("dry_run") as HTMLInputElement | null;
    setBusy("import");
    try {
      const payload = await apiRequest<{ ok: boolean; import_result: ImportResult; state: DashboardPayload }>(
        "/api/import/csv",
        {
          method: "POST",
          body: JSON.stringify({
            csv_text: await file.text(),
            filename: file.name,
            source_type: sourceType?.value || "generic",
            default_strategy: defaultStrategy?.value || "",
            dry_run: Boolean(dryRun?.checked),
          }),
        },
      );
      applyDashboard(payload.state);
      setImportResult(payload.import_result);
      showToast(dryRun?.checked ? "Import dry run complete" : "CSV import complete");
    } catch (error) {
      handleApiError(error);
    } finally {
      setBusy("");
    }
  }

  async function generateReport() {
    const period = document.querySelector<HTMLSelectElement>("#reportPeriod")?.value || "week";
    setBusy("report");
    try {
      const payload = await apiRequest<{ report: ReportPayload }>(`/api/report?period=${encodeURIComponent(period)}`);
      setReport(payload.report);
      showToast("Report generated");
    } catch (error) {
      handleApiError(error);
    } finally {
      setBusy("");
    }
  }

  function downloadReport() {
    if (!report) {
      showToast("Generate a report first");
      return;
    }
    const filename = `${slugify(report.title)}_${report.period.start}_${report.period.end}.md`;
    const blob = new Blob([report.markdown], { type: "text/markdown;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
  }

  async function reviewApproval(id: number, decision: string) {
    setBusy(`approval-${id}-${decision}`);
    try {
      const payload = await apiRequest<{ ok: boolean; approval: ApprovalAction; state: DashboardPayload }>(
        "/api/approval/review",
        {
          method: "POST",
          body: JSON.stringify({ id, decision }),
        },
      );
      applyDashboard(payload.state);
      showToast(actionPastTense(decision));
    } catch (error) {
      handleApiError(error);
    } finally {
      setBusy("");
    }
  }

  if (!auth) {
    return (
      <ScreenFrame>
        <LoadingPanel />
        <Toast message={toast} />
      </ScreenFrame>
    );
  }

  if (needsGate) {
    return (
      <ScreenFrame>
        <AuthGate auth={auth} busy={busy} onSubmit={handleAuthSubmit} />
        <Toast message={toast} />
      </ScreenFrame>
    );
  }

  if (!dashboard) {
    return (
      <ScreenFrame>
        <LoadingPanel />
        <Toast message={toast} />
      </ScreenFrame>
    );
  }

  const activeTempleId = dashboard.config.active_temple?.id || dashboard.status.temple?.id || "";
  const reportView = report || dashboard.report;

  return (
    <main className="temple-shell">
      <header className="flex min-h-[132px] flex-col gap-5 py-3 pb-6 lg:flex-row lg:items-center lg:justify-between">
        <BrandLockup size="large" />
        <div className="flex flex-wrap items-center gap-2 lg:justify-end">
          <select
            className="temple-input w-auto min-w-[210px]"
            value={activeTempleId}
            aria-label="Active temple"
            onChange={(event) => void switchTemple(event.currentTarget.value)}
          >
            {dashboard.config.temples.map((temple) => (
              <option key={temple.id} value={temple.id}>
                {temple.active ? `${temple.name} (active)` : temple.name}
              </option>
            ))}
          </select>
          <StatusPill text={accountLabel(dashboard.auth)} />
          <WorkerPill worker={dashboard.worker} />
          <Button icon={LogOut} variant="ghost" disabled={busy === "logout"} onClick={() => void logout()}>
            Logout
          </Button>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="Temple status">
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
      </section>

      <section className="temple-panel mt-4">
        <div className="section-heading">
          <h2 className="text-lg font-black">Quota Progress</h2>
          <Badge>{titleCase(dashboard.status.judgement)}</Badge>
        </div>
        <div className="h-6 overflow-hidden rounded-lg border border-[#141f33] bg-[#0b1120]" aria-label="Quota progress">
          <div
            className="h-full rounded-lg bg-gradient-to-r from-temple-gold via-temple-green to-temple-blue transition-[width] duration-300"
            style={{ width: `${Math.min(dashboard.status.progress_pct, 100)}%` }}
          />
        </div>
        <p className="mt-2 text-temple-muted">
          Time remaining: {dashboard.status.days_left} day{dashboard.status.days_left === 1 ? "" : "s"}
        </p>
      </section>

      <TopOffering item={dashboard.top_opportunity} />

      <section className="mt-4 grid gap-4 lg:grid-cols-3">
        <Panel
          title="Temple Switchboard"
          icon={Landmark}
          wide
          meta={`${dashboard.temples.temple_count} temples - ${dashboard.temples.overall_progress_pct}% overall`}
        >
          <TempleSummaryList summary={dashboard.temples} />
          <form
            className="mt-4 grid gap-3 border-t border-temple-line pt-4 md:grid-cols-3"
            onSubmit={(event) => void handleJsonForm(event, "/api/temple/create", "Temple created")}
          >
            <Field label="Temple Name" name="name" placeholder="New Revenue Temple" required />
            <Field label="Temple ID" name="temple_id" placeholder="optional-stable-id" />
            <label className="field-label">
              Template
              <select className="temple-input" name="template" defaultValue="balanced">
                <option value="balanced">Balanced</option>
                <option value="services">Services</option>
                <option value="products">Products</option>
              </select>
            </label>
            <Field
              className="md:col-span-2"
              label="Description"
              name="description"
              placeholder="What this temple is trying to earn from"
            />
            <div className="flex items-end">
              <Button icon={Plus} disabled={busy === "/api/temple/create"} type="submit">
                Create Temple
              </Button>
            </div>
          </form>
        </Panel>

        <Panel title="Active Strategies" icon={TrendingUp}>
          <StrategyList items={dashboard.opportunities} />
        </Panel>

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

        <Panel title="Priority Calls" icon={Gauge}>
          <PriorityCalls roi={dashboard.strategy_roi} />
        </Panel>

        <Panel title="Divine Configuration" icon={Settings}>
          <ConfigList dashboard={dashboard} />
        </Panel>

        <Panel
          title="External Signals"
          icon={RefreshCcw}
          wide
          meta={`${external?.connected_count ?? 0} connected`}
          actions={
            <Button
              icon={RefreshCcw}
              variant="secondary"
              disabled={busy === "external"}
              onClick={() => void refreshExternalConnections()}
            >
              Refresh
            </Button>
          }
        >
          <ExternalList snapshot={external} />
        </Panel>

        <Panel
          title="Approval Queue"
          icon={ClipboardList}
          wide
          meta={`${dashboard.approvals.counts.pending || 0} pending - ${dashboard.approvals.counts.approved || 0} approved`}
        >
          <ApprovalForm
            channels={dashboard.config.channels}
            busy={busy === "/api/approval/draft"}
            onSubmit={(event) => void handleJsonForm(event, "/api/approval/draft", "Draft queued for approval")}
          />
          <ApprovalList approvals={dashboard.approvals} busy={busy} onReview={reviewApproval} />
        </Panel>

        <Panel
          title="Temple Log"
          icon={FileText}
          wide
          actions={
            <Button icon={Activity} variant="secondary" disabled={busy === "pulse"} onClick={() => void pulseWorker()}>
              Pulse Worker
            </Button>
          }
        >
          <TempleLog events={dashboard.events} />
        </Panel>

        <Panel title="Command Altar" icon={Send}>
          <form className="grid gap-3" onSubmit={(event) => void handleJsonForm(event, "/api/income", "Income recorded")}>
            <Field label="Amount" name="amount" inputMode="decimal" placeholder="75.00" required />
            <label className="field-label">
              Currency
              <select className="temple-input" name="currency" defaultValue="GBP">
                <option value="GBP">GBP</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="BTC">BTC</option>
                <option value="LTC">LTC</option>
                <option value="XMR">XMR</option>
              </select>
            </label>
            <Field label="GBP Equivalent" name="gbp_equivalent" inputMode="decimal" placeholder="Required outside GBP" />
            <Field label="Source" name="source" placeholder="Paid consultation" required />
            <StrategySelect label="Strategy" name="strategy" channels={dashboard.config.channels} />
            <Field label="Note" name="note" placeholder="Optional" />
            <Button icon={Coins} disabled={busy === "/api/income"} type="submit">
              Record Income
            </Button>
          </form>
        </Panel>

        <Panel title="Import Altar" icon={Upload}>
          <form className="grid gap-3" onSubmit={(event) => void importCsv(event)}>
            <label className="field-label">
              CSV File
              <input className="temple-input file:mr-3 file:rounded-md file:border-0 file:bg-temple-gold file:px-3 file:py-1.5 file:text-sm file:font-bold file:text-[#07101c]" name="file" type="file" accept=".csv,text/csv" required />
            </label>
            <label className="field-label">
              Import Type
              <select className="temple-input" name="source_type" defaultValue="generic">
                <option value="generic">Generic CSV</option>
                <option value="payment">Payment Export</option>
                <option value="affiliate">Affiliate Report</option>
              </select>
            </label>
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
            <Button icon={Upload} disabled={busy === "import"} type="submit">
              Import CSV
            </Button>
          </form>
          <ImportResultView result={importResult} />
        </Panel>

        <Panel title="Quota Control" icon={Target}>
          <form
            key={`quota-${dashboard.config.active_mood}`}
            className="grid gap-3"
            onSubmit={(event) => void handleJsonForm(event, "/api/quota", "Quota updated")}
          >
            <MoodSelect label="Mood" name="mood" moods={dashboard.config.moods} defaultValue={dashboard.config.active_mood} />
            <Field label="Target" name="amount" inputMode="decimal" placeholder="250.00" required />
            <label className="field-label">
              Period
              <select className="temple-input" name="period" defaultValue={dashboard.status.period.name}>
                <option value="week">Week</option>
                <option value="month">Month</option>
              </select>
            </label>
            <Button icon={Target} disabled={busy === "/api/quota"} type="submit">
              Set Quota
            </Button>
          </form>
          <form
            key={`mood-${dashboard.config.active_mood}`}
            className="mt-4 grid gap-3 border-t border-temple-line pt-4"
            onSubmit={(event) => void handleJsonForm(event, "/api/mood", "Mood updated")}
          >
            <MoodSelect
              label="Active Mood"
              name="mood"
              moods={dashboard.config.moods}
              defaultValue={dashboard.config.active_mood}
            />
            <Button icon={Gauge} variant="secondary" disabled={busy === "/api/mood"} type="submit">
              Set Mood
            </Button>
          </form>
        </Panel>

        <Panel title="Mercy Exception" icon={ShieldCheck}>
          <form
            className="grid gap-3"
            onSubmit={(event) => void handleJsonForm(event, "/api/exception", "Exception added")}
          >
            <Field label="Reason" name="reason" placeholder="Payment processor outage" required />
            <Field label="Until" name="until" type="date" required />
            <Button icon={ShieldCheck} variant="secondary" disabled={busy === "/api/exception"} type="submit">
              Add Exception
            </Button>
          </form>
        </Panel>

        <Panel title="Recent Income" icon={Coins}>
          <RecentIncome items={dashboard.income} />
        </Panel>

        <Panel title="Upgrade Path" icon={TrendingUp} wide>
          <UpgradeGrid upgrades={dashboard.upgrades} />
        </Panel>

        <Panel
          title="Report Forge"
          icon={FileText}
          wide
          actions={
            <div className="flex w-full flex-wrap gap-2 sm:w-auto">
              <select id="reportPeriod" className="temple-input w-full min-w-[132px] sm:w-auto" aria-label="Report period">
                <option value="week">Weekly</option>
                <option value="month">Monthly</option>
              </select>
              <Button icon={FileText} variant="secondary" disabled={busy === "report"} onClick={() => void generateReport()}>
                Generate
              </Button>
              <Button icon={Download} onClick={downloadReport}>
                Download
              </Button>
            </div>
          }
        >
          <div className="mb-3 grid gap-1 sm:flex sm:items-baseline sm:justify-between">
            <strong className="text-lg text-temple-gold">{reportView.title}</strong>
            <span className="text-temple-muted">
              {reportView.period.start} to {reportView.period.end} - {reportView.earned} earned of {reportView.quota}
            </span>
          </div>
          <pre className="max-h-[520px] min-h-[320px] overflow-auto rounded-lg border border-temple-line bg-[#091020] p-4 text-sm leading-6 text-[#d9e5ff] whitespace-pre-wrap">
            {reportView.markdown}
          </pre>
        </Panel>
      </section>

      <Toast message={toast} />
    </main>
  );
}

function ScreenFrame({ children }: { children: ReactNode }) {
  return <main className="grid min-h-screen place-items-center px-6 py-8">{children}</main>;
}

function LoadingPanel() {
  return (
    <section className="temple-panel w-[min(520px,100%)]">
      <BrandLockup />
      <p className="mt-6 text-temple-muted">Opening the temple...</p>
    </section>
  );
}

function AuthGate({
  auth,
  busy,
  onSubmit,
}: {
  auth: AuthStatus;
  busy: string;
  onSubmit: (event: FormEvent<HTMLFormElement>, path: string, success: string) => Promise<void>;
}) {
  return (
    <section className="temple-panel grid w-[min(520px,100%)] gap-6">
      <BrandLockup />
      {auth.setup_required ? (
        <form className="grid gap-3" onSubmit={(event) => void onSubmit(event, "/api/auth/setup", "Owner account created")}>
          <h2 className="text-xl font-black text-temple-gold">Owner Setup</h2>
          <Field label="Username" name="username" autoComplete="username" required />
          <Field label="Display Name" name="display_name" autoComplete="name" placeholder="Creator" />
          <Field label="Password" name="password" type="password" autoComplete="new-password" minLength={10} required />
          <Button icon={ShieldCheck} disabled={busy === "/api/auth/setup"} type="submit">
            Create Owner
          </Button>
        </form>
      ) : (
        <form className="grid gap-3" onSubmit={(event) => void onSubmit(event, "/api/auth/login", "Signed in")}>
          <h2 className="text-xl font-black text-temple-gold">Owner Login</h2>
          <Field label="Username" name="username" autoComplete="username" required />
          <Field label="Password" name="password" type="password" autoComplete="current-password" required />
          <Button icon={Landmark} disabled={busy === "/api/auth/login"} type="submit">
            Enter Temple
          </Button>
        </form>
      )}
    </section>
  );
}

function BrandLockup({ size = "default" }: { size?: "default" | "large" }) {
  return (
    <div className="flex min-w-0 items-center gap-4">
      <img
        className="shrink-0 rounded-lg shadow-glow"
        src="/assets/temple-mark.png"
        width={size === "large" ? 64 : 56}
        height={size === "large" ? 64 : 56}
        alt=""
      />
      <div className="min-w-0">
        <p className="mb-1 text-xs font-black uppercase tracking-[0.08em] text-temple-muted">Serving the Creator</p>
        <h1 className="max-w-[860px] text-[clamp(2rem,5vw,4.1rem)] font-black uppercase leading-none text-temple-gold">
          The Divine Income Engine
        </h1>
        {size === "large" ? (
          <p className="mt-2 text-base text-temple-muted">24/7 quota watch, lawful revenue tracking, eternal optimization.</p>
        ) : null}
      </div>
    </div>
  );
}

function Button({
  children,
  icon: Icon,
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { icon?: IconType; variant?: ButtonVariant }) {
  return (
    <button className={cx("temple-button", buttonVariants[variant], className)} type="button" {...props}>
      {Icon ? <Icon aria-hidden="true" size={17} strokeWidth={2.4} /> : null}
      <span>{children}</span>
    </button>
  );
}

function Badge({ children }: { children: ReactNode }) {
  return <span className="temple-badge">{children}</span>;
}

function StatusPill({ text }: { text: string }) {
  return <div className="temple-badge">{text}</div>;
}

function WorkerPill({ worker }: { worker: WorkerStatus }) {
  const color = worker.state === "running" ? "bg-temple-green" : worker.state === "stale" ? "bg-temple-gold" : "bg-temple-red";
  const age = worker.age_seconds === null ? "no heartbeat" : `${worker.age_seconds}s ago`;
  return (
    <div className="temple-badge">
      <span className={cx("h-2.5 w-2.5 rounded-full shadow-[0_0_16px_currentColor]", color)} />
      <span>
        Worker: {worker.state} ({age})
      </span>
    </div>
  );
}

function MetricCard({
  accent,
  icon: Icon,
  label,
  value,
  detail,
}: {
  accent: Accent;
  icon: IconType;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <article className={cx("temple-card min-h-[158px] border-l-4", accentBorder[accent])}>
      <div className={cx("mb-4 flex items-center gap-2 font-black", accentText[accent])}>
        <Icon aria-hidden="true" size={20} />
        <p className="m-0">{label}</p>
      </div>
      <strong className={cx("mb-2 block text-[clamp(1.65rem,4vw,2.35rem)] leading-none", accentText[accent])}>
        {value}
      </strong>
      <span className="text-temple-muted">{detail}</span>
    </article>
  );
}

function Panel({
  title,
  icon: Icon,
  meta,
  actions,
  wide,
  children,
}: {
  title: string;
  icon: IconType;
  meta?: string;
  actions?: ReactNode;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <article className={cx("temple-panel", wide && "lg:col-span-2")}>
      <div className="section-heading flex-col items-start sm:flex-row">
        <h2 className="flex items-center gap-2 text-lg font-black">
          <Icon aria-hidden="true" className="text-temple-gold" size={20} />
          {title}
        </h2>
        {actions || (meta ? <Badge>{meta}</Badge> : null)}
      </div>
      {children}
    </article>
  );
}

function TopOffering({ item }: { item: Opportunity | null }) {
  return (
    <section className="temple-panel mt-4">
      <div className="section-heading">
        <h2 className="text-lg font-black">Top Offering</h2>
        <Badge>{item ? `${item.score}/100 - ${titleCase(item.score_label)}` : "score --"}</Badge>
      </div>
      <strong className="mb-2 block text-[clamp(1.35rem,3vw,2rem)] text-temple-gold">
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

function TempleSummaryList({ summary }: { summary: DashboardPayload["temples"] }) {
  if (!summary.rows.length) {
    return <EmptyRow>No temples configured yet.</EmptyRow>;
  }
  return (
    <div className="grid gap-2.5">
      {summary.rows.map((item) => (
        <div
          key={item.id}
          className={cx("temple-row flex items-center justify-between gap-3", item.active && "border-l-4 border-l-temple-gold")}
        >
          <div className="grid min-w-0 gap-1">
            <strong>{item.active ? `Active: ${item.name}` : item.name}</strong>
            <span className="text-sm text-temple-muted">
              {titleCase(item.judgement)} - top: {item.top_strategy}
            </span>
          </div>
          <div className="grid shrink-0 justify-items-end gap-1">
            <b className="text-temple-green">
              {item.earned} / {item.quota}
            </b>
            <small className="text-temple-muted">
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
        <div key={item.id} className="temple-row grid grid-cols-[1fr_auto] items-start gap-3" title={item.next_action}>
          <div className="grid min-w-0 gap-1.5">
            <strong>{item.name}</strong>
            <span className="text-sm text-temple-muted">
              {item.expected} expected - {item.period_income} recorded this period
            </span>
            <small className="text-temple-muted">{item.rationale}</small>
          </div>
          <div className="grid min-w-24 justify-items-end gap-2">
            <b className={cx("text-xs font-black uppercase", item.fit === "deadline" || item.risk !== "low" ? "text-temple-gold" : "text-temple-green")}>
              {item.score}/100
            </b>
            <div className="h-2 w-24 overflow-hidden rounded-full bg-[#172238]">
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
          <div className="flex items-start justify-between gap-3">
            <div className="grid min-w-0 gap-1">
              <strong>
                #{row.roi_rank} {row.name}
              </strong>
              <span className="text-sm text-temple-muted">
                {titleCase(row.trend)} - {row.target_capture_pct}% of expected value
              </span>
            </div>
            <b className="shrink-0 text-xs font-black uppercase text-temple-green">{row.recommendation}</b>
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

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-h-[62px] rounded-lg bg-white/[0.035] p-2.5">
      <span className="mb-1.5 block text-xs font-black uppercase text-temple-muted">{label}</span>
      <strong>{value}</strong>
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
        <div key={label} className="temple-row flex items-center justify-between gap-3">
          <strong>{label}</strong>
          <span className="text-sm font-bold uppercase text-temple-muted">{value}</span>
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
        <div key={connection.id} className={cx("temple-row grid grid-cols-[1fr_auto] gap-x-3 gap-y-2 border-l-4", externalBorder(connection.state))}>
          <div className="grid min-w-0 gap-1">
            <strong>{connection.name}</strong>
            <span className="text-sm text-temple-muted">{connection.summary}</span>
          </div>
          <b className="text-xs font-black uppercase text-temple-green">{connection.state}</b>
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
  onSubmit,
}: {
  channels: DashboardPayload["config"]["channels"];
  busy: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <form className="grid gap-3 md:grid-cols-3" onSubmit={onSubmit}>
      <label className="field-label">
        Draft Type
        <select className="temple-input" name="kind" defaultValue="invoice_reminder">
          <option value="invoice_reminder">Invoice Reminder</option>
          <option value="outreach">Outreach Message</option>
          <option value="content_prompt">Content Prompt</option>
        </select>
      </label>
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
      <div className="flex items-end">
        <Button icon={Send} disabled={busy} type="submit">
          Queue Draft
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
          <div className="flex items-start justify-between gap-3">
            <div className="grid min-w-0 gap-1">
              <strong>
                #{item.id} {item.title}
              </strong>
              <span className="text-sm text-temple-muted">
                {item.kind_label} - {item.strategy || "unassigned"}
              </span>
            </div>
            <b className="text-xs font-black uppercase text-temple-green">{item.status}</b>
          </div>
          <pre className="max-h-[190px] overflow-auto rounded-lg bg-[#091020] p-3 text-sm leading-6 text-[#d9e5ff] whitespace-pre-wrap">
            {item.body}
          </pre>
          <div className="flex flex-wrap gap-2">
            {item.status === "pending" ? (
              <>
                <Button
                  icon={Check}
                  variant="secondary"
                  disabled={busy === `approval-${item.id}-approve`}
                  onClick={() => void onReview(item.id, "approve")}
                >
                  Approve
                </Button>
                <Button
                  icon={X}
                  variant="ghost"
                  disabled={busy === `approval-${item.id}-reject`}
                  onClick={() => void onReview(item.id, "reject")}
                >
                  Reject
                </Button>
              </>
            ) : null}
            {item.status === "approved" ? (
              <>
                <Button
                  icon={Check}
                  variant="secondary"
                  disabled={busy === `approval-${item.id}-complete`}
                  onClick={() => void onReview(item.id, "complete")}
                >
                  Complete
                </Button>
                <Button
                  icon={X}
                  variant="ghost"
                  disabled={busy === `approval-${item.id}-reject`}
                  onClick={() => void onReview(item.id, "reject")}
                >
                  Reject
                </Button>
              </>
            ) : null}
          </div>
        </div>
      ))}
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
      <strong>{message}</strong>
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
          <div key={item.id} className="temple-row flex items-center justify-between gap-3">
            <strong>{item.counted}</strong>
            <span className="text-right text-sm text-temple-muted">
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

function EmptyRow({ children }: { children: ReactNode }) {
  return (
    <div className="temple-row">
      <span className="text-temple-muted">{children}</span>
    </div>
  );
}

function Field({
  label,
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label: string; className?: string }) {
  return (
    <label className={cx("field-label", className)}>
      {label}
      <input className="temple-input" {...props} />
    </label>
  );
}

function StrategySelect({
  label,
  name,
  channels,
  emptyLabel = "Unassigned",
}: {
  label: string;
  name: string;
  channels: DashboardPayload["config"]["channels"];
  emptyLabel?: string;
}) {
  return (
    <label className="field-label">
      {label}
      <select className="temple-input" name={name} defaultValue="">
        <option value="">{emptyLabel}</option>
        {channels.map((channel) => (
          <option key={channel.id || slugify(channel.name)} value={channel.id || slugify(channel.name)}>
            {channel.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function MoodSelect({
  label,
  name,
  moods,
  defaultValue,
}: {
  label: string;
  name: string;
  moods: DashboardPayload["config"]["moods"];
  defaultValue: string;
}) {
  const moodNames = Object.keys(moods);
  return (
    <label className="field-label">
      {label}
      <select className="temple-input" name={name} defaultValue={defaultValue}>
        {moodNames.map((mood) => (
          <option key={mood} value={mood}>
            {capitalize(mood)}
          </option>
        ))}
      </select>
    </label>
  );
}

function Toast({ message }: { message: string }) {
  return (
    <div
      className={cx(
        "fixed bottom-5 right-5 z-50 max-w-[min(420px,calc(100%-36px))] rounded-lg bg-temple-text px-3.5 py-3 font-black text-[#08101c] shadow-2xl transition",
        message ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-4 opacity-0",
      )}
      role="status"
      aria-live="polite"
    >
      {message}
    </div>
  );
}

function formPayload(form: HTMLFormElement): Record<string, string> {
  const data = new FormData(form);
  const payload: Record<string, string> = {};
  for (const [key, value] of data.entries()) {
    if (typeof value === "string" && value.trim() !== "") {
      payload[key] = value.trim();
    }
  }
  return payload;
}

function authFromPayload(payload: unknown): AuthStatus | null {
  if (!payload || typeof payload !== "object" || !("auth" in payload)) {
    return null;
  }
  return (payload as { auth: AuthStatus }).auth;
}

function canLoadDashboard(auth: AuthStatus) {
  return !auth.enabled || (auth.authenticated && !auth.setup_required);
}

function accountLabel(auth: AuthStatus) {
  const account = auth.account;
  if (!account) {
    return "Account: local";
  }
  return `${account.display_name || account.username} - ${account.role}`;
}

function runningStrategyCount(payload: DashboardPayload) {
  return payload.opportunities.filter((item) => item.score >= 50).length;
}

function riskLabel(judgement: string) {
  if (judgement === "wrath risk") return "moderate";
  if (judgement === "needs offerings") return "elevated";
  if (judgement === "quota satisfied") return "low";
  return "managed";
}

function externalItemText(item: Record<string, string>) {
  if (item.one_unit) return `${item.currency}: ${item.one_unit}`;
  if (item.net) return `${item.currency}: ${item.net} net (${item.transaction_count})`;
  if (item.label) return `${item.label}: ${item.value}`;
  return JSON.stringify(item);
}

function actionPastTense(decision: string) {
  if (decision === "approve") return "Draft approved";
  if (decision === "reject") return "Draft rejected";
  if (decision === "complete") return "Draft completed";
  return "Draft updated";
}

function recommendationBorder(recommendation: string) {
  if (recommendation === "push") return "border-l-temple-green";
  if (recommendation === "pause") return "border-l-temple-gold";
  return "border-l-temple-blue";
}

function externalBorder(state: string) {
  if (state === "connected") return "border-l-temple-green";
  if (state === "ready" || state === "disabled") return "border-l-temple-gold";
  if (state === "error") return "border-l-temple-red";
  return "border-l-temple-blue";
}

function approvalBorder(status: string) {
  if (status === "pending") return "border-l-temple-gold";
  if (status === "approved") return "border-l-temple-green";
  if (status === "rejected") return "border-l-temple-red";
  if (status === "completed") return "border-l-temple-violet";
  return "border-l-temple-blue";
}

function importBorder(status: string) {
  if (status === "skipped") return "border-l-temple-gold";
  if (status === "duplicate") return "border-l-temple-violet";
  if (status === "imported" || status === "ready") return "border-l-temple-green";
  return "border-l-temple-blue";
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--:--:--";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function shortDate(value: string) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

function capitalize(value: string) {
  return String(value).charAt(0).toUpperCase() + String(value).slice(1);
}

function titleCase(value: string) {
  return String(value)
    .split(" ")
    .map(capitalize)
    .join(" ");
}

function slugify(value: string) {
  return (
    String(value)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || "strategy"
  );
}

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export default App;
