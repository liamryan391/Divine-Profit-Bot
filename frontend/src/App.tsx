import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, apiRequest } from "./api";
import { AuthGate } from "./components/auth";
import { DashboardViewContent } from "./components/dashboard-views";
import { DashboardShell, LoadingPanel, ScreenFrame } from "./components/layout";
import { Toast } from "./components/ui";
import { actionPastTense, authFromPayload, canLoadDashboard, formPayload, slugify } from "./lib/format";
import { defaultDashboardView, type DashboardView, viewFromHash } from "./lib/navigation";
import type {
  ApprovalAction,
  AuthResponse,
  AuthStatus,
  DashboardPayload,
  ExternalSnapshot,
  ImportResult,
  ReportPayload,
} from "./types";

function App() {
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [external, setExternal] = useState<ExternalSnapshot | null>(null);
  const [report, setReport] = useState<ReportPayload | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [activeView, setActiveView] = useState<DashboardView>(() =>
    typeof window === "undefined" ? defaultDashboardView : viewFromHash(window.location.hash),
  );
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

  useEffect(() => {
    if (!window.location.hash) {
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#/${defaultDashboardView}`);
    }
    const syncView = () => setActiveView(viewFromHash(window.location.hash));
    syncView();
    window.addEventListener("hashchange", syncView);
    return () => window.removeEventListener("hashchange", syncView);
  }, []);

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

  async function handleJsonForm(event: FormEvent<HTMLFormElement>, path: string, success: string, resetForm = true) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(path);
    try {
      const payload = await apiRequest<{ ok: boolean; state: DashboardPayload }>(path, {
        method: "POST",
        body: JSON.stringify(formPayload(form)),
      });
      applyDashboard(payload.state);
      if (resetForm) {
        form.reset();
      }
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
    const currentReport = report ?? dashboard?.report;
    if (!currentReport) {
      showToast("Generate a report first");
      return;
    }
    const filename = `${slugify(currentReport.title)}_${currentReport.period.start}_${currentReport.period.end}.md`;
    const blob = new Blob([currentReport.markdown], { type: "text/markdown;charset=utf-8" });
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
  const pendingApprovals = dashboard.approvals.counts.pending || 0;

  return (
    <DashboardShell
      auth={dashboard.auth}
      activeView={activeView}
      activeTempleId={activeTempleId}
      temples={dashboard.config.temples}
      worker={dashboard.worker}
      busy={busy}
      pendingApprovals={pendingApprovals}
      onTempleChange={(templeId) => void switchTemple(templeId)}
      onLogout={() => void logout()}
    >
      <DashboardViewContent
        view={activeView}
        dashboard={dashboard}
        external={external}
        report={reportView}
        importResult={importResult}
        busy={busy}
        onJsonForm={(event, path, success, resetForm) => void handleJsonForm(event, path, success, resetForm)}
        onImport={(event) => void importCsv(event)}
        onReviewApproval={reviewApproval}
        onPulseWorker={() => void pulseWorker()}
        onRefreshExternal={() => void refreshExternalConnections()}
        onGenerateReport={() => void generateReport()}
        onDownloadReport={downloadReport}
      />

      <Toast message={toast} />
    </DashboardShell>
  );
}

export default App;
