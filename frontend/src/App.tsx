import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, apiRequest } from "./api";
import { AuthGate } from "./components/auth";
import { DashboardViewContent } from "./components/dashboard-views";
import { DashboardShell, LoadingPanel, ScreenFrame } from "./components/layout";
import { Toast } from "./components/ui";
import {
  applyWorkflowIssues,
  clearWorkflowFieldError,
  clearWorkflowFormValidity,
  focusFirstWorkflowIssue,
  summarizeWorkflowIssues,
  validateWorkflowForm,
  type WorkflowFeedback,
  type WorkflowFeedbackMap,
} from "./lib/forms";
import { actionPastTense, authFromPayload, canLoadDashboard, formPayload, slugify } from "./lib/format";
import { defaultDashboardView, type DashboardView, viewFromHash } from "./lib/navigation";
import type {
  ApprovalAction,
  AuthResponse,
  AuthStatus,
  DashboardPayload,
  ExternalSnapshot,
  ImportResult,
  LeadEntry,
  ReportPayload,
  RevenueRuleEntry,
  WorkerCycle,
} from "./types";

const MAX_CSV_FILE_BYTES = 4 * 1024 * 1024;

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : "Unexpected request failure";
}

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
  const [formFeedback, setFormFeedback] = useState<WorkflowFeedbackMap>({});
  const toastTimer = useRef<number | undefined>(undefined);

  const showToast = useCallback((message: string) => {
    setToast(message);
    if (toastTimer.current) {
      window.clearTimeout(toastTimer.current);
    }
    toastTimer.current = window.setTimeout(() => setToast(""), 2800);
  }, []);

  const setWorkflowFeedback = useCallback((key: string, feedback: WorkflowFeedback) => {
    setFormFeedback((current) => ({ ...current, [key]: feedback }));
  }, []);

  const applyDashboard = useCallback((payload: DashboardPayload) => {
    setDashboard(payload);
    setAuth(payload.auth);
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
          showToast(errorMessage(error));
        }
        return;
      }
      if (announce) {
        showToast(errorMessage(error));
      }
    },
    [showToast],
  );

  const validateBeforeSubmit = useCallback(
    (form: HTMLFormElement, workflowKey: string, pendingMessage: string) => {
      clearWorkflowFormValidity(form);
      const issues = validateWorkflowForm(form, workflowKey);
      if (issues.length) {
        const feedback = summarizeWorkflowIssues(issues);
        applyWorkflowIssues(form, issues);
        setWorkflowFeedback(workflowKey, feedback);
        showToast(feedback.message);
        form.reportValidity();
        focusFirstWorkflowIssue(form, issues);
        return false;
      }
      setWorkflowFeedback(workflowKey, { tone: "info", message: pendingMessage });
      return true;
    },
    [setWorkflowFeedback, showToast],
  );

  const refreshWorker = useCallback(async () => {
    try {
      const payload = await apiRequest<{ worker: DashboardPayload["worker"] }>("/api/worker/status");
      setDashboard((current) => (current ? { ...current, worker: payload.worker } : current));
    } catch (error) {
      handleApiError(error, false);
    }
  }, [handleApiError]);

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
    const clearField = (event: Event) => clearWorkflowFieldError(event.target);
    document.addEventListener("input", clearField, true);
    document.addEventListener("change", clearField, true);
    return () => {
      document.removeEventListener("input", clearField, true);
      document.removeEventListener("change", clearField, true);
    };
  }, []);

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
      void refreshWorker();
    }, 10000);
    return () => window.clearInterval(interval);
  }, [auth, needsGate, refreshWorker]);

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
    if (!validateBeforeSubmit(form, path, path === "/api/auth/login" ? "Signing in..." : "Creating owner account...")) {
      return;
    }
    setBusy(path);
    try {
      const payload = await apiRequest<{ ok: boolean; auth: AuthStatus; state: DashboardPayload }>(path, {
        method: "POST",
        body: JSON.stringify(formPayload(form)),
      });
      setAuth(payload.auth);
      applyDashboard(payload.state);
      form.reset();
      setWorkflowFeedback(path, { tone: "success", message: success });
      showToast(success);
      await refreshExternalConnections(false);
    } catch (error) {
      setWorkflowFeedback(path, { tone: "error", message: errorMessage(error) });
      handleApiError(error);
    } finally {
      setBusy("");
    }
  }

  async function handleJsonForm(event: FormEvent<HTMLFormElement>, path: string, success: string, resetForm = true) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!validateBeforeSubmit(form, path, "Saving changes...")) {
      return;
    }
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
      setWorkflowFeedback(path, { tone: "success", message: success });
      showToast(success);
    } catch (error) {
      setWorkflowFeedback(path, { tone: "error", message: errorMessage(error) });
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
      const payload = await apiRequest<{ ok: boolean; cycle: WorkerCycle; state: DashboardPayload }>("/api/daemon/run-once", {
        method: "POST",
        body: "{}",
      });
      applyDashboard(payload.state);
      showToast(
        `Worker cycle #${payload.cycle.id} ${payload.cycle.status}: ${payload.cycle.rules.triggered}/${payload.cycle.rules.evaluated} rules triggered`,
      );
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
      setReport(null);
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
    if (!validateBeforeSubmit(form, "import", "Reading CSV import...")) {
      return;
    }
    const fileInput = form.elements.namedItem("file") as HTMLInputElement | null;
    const file = fileInput?.files?.[0];
    if (!file) {
      return;
    }
    if (file.size > MAX_CSV_FILE_BYTES) {
      setWorkflowFeedback("import", {
        tone: "error",
        message: "CSV files must be 4 MiB or smaller.",
      });
      showToast("CSV file is too large");
      return;
    }
    const sourceType = form.elements.namedItem("source_type") as HTMLSelectElement | null;
    const defaultStrategy = form.elements.namedItem("default_strategy") as HTMLSelectElement | null;
    const dryRun = form.elements.namedItem("dry_run") as HTMLInputElement | null;
    if (!dryRun?.checked && !window.confirm("Import these CSV rows into the ledger now? Run a dry run first if you are unsure.")) {
      setWorkflowFeedback("import", { tone: "warning", message: "CSV import cancelled." });
      return;
    }
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
      setWorkflowFeedback("import", {
        tone: "success",
        message: dryRun?.checked ? "Dry run complete." : "CSV import complete.",
        details: [
          `${payload.import_result.imported_count} imported`,
          `${payload.import_result.duplicate_count} duplicate`,
          `${payload.import_result.skipped_count} skipped`,
        ],
      });
      showToast(dryRun?.checked ? "Import dry run complete" : "CSV import complete");
    } catch (error) {
      setWorkflowFeedback("import", { tone: "error", message: errorMessage(error) });
      handleApiError(error);
    } finally {
      setBusy("");
    }
  }

  async function generateReport() {
    const period = document.querySelector<HTMLSelectElement>("#reportPeriod")?.value || "week";
    setBusy("report");
    setWorkflowFeedback("report", { tone: "info", message: "Generating report..." });
    try {
      const payload = await apiRequest<{ report: ReportPayload }>(`/api/report?period=${encodeURIComponent(period)}`);
      setReport(payload.report);
      setWorkflowFeedback("report", { tone: "success", message: "Report generated." });
      showToast("Report generated");
    } catch (error) {
      setWorkflowFeedback("report", { tone: "error", message: errorMessage(error) });
      handleApiError(error);
    } finally {
      setBusy("");
    }
  }

  function downloadReport() {
    const currentReport = report;
    if (!currentReport?.markdown || currentReport.generated === false) {
      setWorkflowFeedback("report", { tone: "warning", message: "Generate a report before downloading." });
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
    if (decision === "reject" && !window.confirm("Reject this approval draft?")) {
      return;
    }
    if (decision === "complete" && !window.confirm("Mark this approved action complete?")) {
      return;
    }
    setBusy(`approval-${id}-${decision}`);
    setWorkflowFeedback("/api/approval/draft", { tone: "info", message: "Updating approval..." });
    try {
      const payload = await apiRequest<{ ok: boolean; approval: ApprovalAction; state: DashboardPayload }>(
        "/api/approval/review",
        {
          method: "POST",
          body: JSON.stringify({ id, decision }),
        },
      );
      applyDashboard(payload.state);
      setWorkflowFeedback("/api/approval/draft", { tone: "success", message: actionPastTense(decision) });
      showToast(actionPastTense(decision));
    } catch (error) {
      setWorkflowFeedback("/api/approval/draft", { tone: "error", message: errorMessage(error) });
      handleApiError(error);
    } finally {
      setBusy("");
    }
  }

  async function advanceLead(id: number, stage: string) {
    const busyKey = `lead-${id}-${stage}`;
    setBusy(busyKey);
    setWorkflowFeedback("/api/leads", { tone: "info", message: "Updating lead..." });
    try {
      const payload = await apiRequest<{ ok: boolean; lead: LeadEntry; state: DashboardPayload }>(
        `/api/leads/${id}/advance`,
        {
          method: "POST",
          body: JSON.stringify({ stage }),
        },
      );
      applyDashboard(payload.state);
      setWorkflowFeedback("/api/leads", { tone: "success", message: `Lead moved to ${stage}` });
      showToast(`Lead moved to ${stage}`);
    } catch (error) {
      setWorkflowFeedback("/api/leads", { tone: "error", message: errorMessage(error) });
      handleApiError(error);
    } finally {
      setBusy("");
    }
  }

  async function updateRevenueRuleStatus(id: number, status: string) {
    if (status === "retired" && !window.confirm("Retire this revenue rule? It will stop evaluating until recreated.")) {
      return;
    }
    const busyKey = `revenue-rule-${id}-${status}`;
    setBusy(busyKey);
    setWorkflowFeedback("/api/revenue-rules", { tone: "info", message: "Updating revenue rule..." });
    try {
      const payload = await apiRequest<{ ok: boolean; rule: RevenueRuleEntry; state: DashboardPayload }>(
        `/api/revenue-rules/${id}/status`,
        {
          method: "POST",
          body: JSON.stringify({ status }),
        },
      );
      applyDashboard(payload.state);
      const message = `Revenue rule ${status}`;
      setWorkflowFeedback("/api/revenue-rules", { tone: "success", message });
      showToast(message);
    } catch (error) {
      setWorkflowFeedback("/api/revenue-rules", { tone: "error", message: errorMessage(error) });
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
        <AuthGate auth={auth} busy={busy} feedback={formFeedback} onSubmit={handleAuthSubmit} />
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
        feedback={formFeedback}
        onJsonForm={(event, path, success, resetForm) => void handleJsonForm(event, path, success, resetForm)}
        onImport={(event) => void importCsv(event)}
        onReviewApproval={reviewApproval}
        onAdvanceLead={advanceLead}
        onRevenueRuleStatus={updateRevenueRuleStatus}
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
