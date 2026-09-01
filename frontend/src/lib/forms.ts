export type WorkflowFeedbackTone = "info" | "success" | "warning" | "error";

export interface WorkflowFeedback {
  tone: WorkflowFeedbackTone;
  message: string;
  details?: string[];
}

export type WorkflowFeedbackMap = Record<string, WorkflowFeedback | undefined>;

export interface WorkflowIssue {
  field?: string;
  label?: string;
  message: string;
}

type FormControl = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

const MONEY_RE = /^\d+(?:[.,]\d+)?$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const TEMPLE_ID_RE = /^[a-z0-9][a-z0-9_-]{1,38}[a-z0-9]$/;
const PERCENT_RE = /^\d+(?:[.,]\d+)?$/;
const DAY_LIST_RE = /^\d+(?:\s*,\s*\d+)*$/;

export function clearWorkflowFormValidity(form: HTMLFormElement) {
  for (const element of Array.from(form.elements)) {
    if (isFormControl(element)) {
      element.setCustomValidity("");
      element.removeAttribute("aria-invalid");
    }
  }
}

export function clearWorkflowFieldError(target: EventTarget | null) {
  if (isFormControl(target)) {
    target.setCustomValidity("");
    target.removeAttribute("aria-invalid");
  }
}

export function applyWorkflowIssues(form: HTMLFormElement, issues: WorkflowIssue[]) {
  for (const issue of issues) {
    if (!issue.field) {
      continue;
    }
    const control = getControl(form, issue.field);
    if (control) {
      control.setCustomValidity(issue.message);
      control.setAttribute("aria-invalid", "true");
    }
  }
}

export function focusFirstWorkflowIssue(form: HTMLFormElement, issues: WorkflowIssue[]) {
  const firstNamed = issues.find((issue) => issue.field);
  const control = firstNamed?.field ? getControl(form, firstNamed.field) : null;
  control?.focus();
}

export function summarizeWorkflowIssues(issues: WorkflowIssue[]): WorkflowFeedback {
  const details = issues.map((issue) => (issue.label ? `${issue.label}: ${issue.message}` : issue.message));
  return {
    tone: "warning",
    message: issues.length === 1 ? "Review the highlighted field." : `Review ${issues.length} fields before submitting.`,
    details,
  };
}

export function validateWorkflowForm(form: HTMLFormElement, workflowKey: string): WorkflowIssue[] {
  const issues = nativeIssues(form);

  if (workflowKey === "/api/auth/setup") {
    requireMinLength(form, issues, "username", "Username", 3);
    requireMinLength(form, issues, "password", "Password", 10);
    validateOptionalEmail(form, issues, "recovery_email", "Recovery Email");
  }

  if (workflowKey === "/api/auth/login") {
    requireMinLength(form, issues, "username", "Username", 3);
  }

  if (workflowKey === "/api/account/profile") {
    validateOptionalEmail(form, issues, "recovery_email", "Recovery Email");
  }

  if (workflowKey === "/api/temple/create") {
    requireText(form, issues, "name", "Temple Name");
    const templeId = valueOf(form, "temple_id");
    if (templeId && !TEMPLE_ID_RE.test(templeId)) {
      issues.push({
        field: "temple_id",
        label: "Temple ID",
        message: "Use 3-40 lowercase letters, numbers, hyphens, or underscores.",
      });
    }
  }

  if (workflowKey === "/api/income") {
    requirePositiveMoney(form, issues, "amount", "Amount");
    requireText(form, issues, "source", "Source");
    const currency = valueOf(form, "currency").toUpperCase() || "GBP";
    const gbp = valueOf(form, "gbp_equivalent");
    if (currency !== "GBP" && !gbp) {
      issues.push({
        field: "gbp_equivalent",
        label: "GBP Equivalent",
        message: "Add a GBP equivalent for non-GBP income.",
      });
    }
    if (gbp) {
      requirePositiveMoney(form, issues, "gbp_equivalent", "GBP Equivalent");
    }
  }

  if (workflowKey === "/api/quota") {
    requirePositiveMoney(form, issues, "amount", "Target");
  }

  if (workflowKey === "/api/exception") {
    requireText(form, issues, "reason", "Reason");
    requireDate(form, issues, "until", "Until");
    const until = valueOf(form, "until");
    if (until && isPastDate(until)) {
      issues.push({ field: "until", label: "Until", message: "Choose today or a future date." });
    }
  }

  if (workflowKey === "/api/approval/draft") {
    validateApprovalDraft(form, issues);
  }

  if (workflowKey === "/api/leads") {
    validateLead(form, issues);
  }

  if (workflowKey === "/api/conversions/record") {
    validateConversion(form, issues);
  }

  if (workflowKey === "/api/receivables") {
    validateReceivable(form, issues);
  }

  if (workflowKey === "/api/receivables/payment") {
    validateReceivablePayment(form, issues);
  }

  if (workflowKey === "/api/recurring-revenue/templates") {
    validateRecurringRevenueTemplate(form, issues);
  }

  if (workflowKey === "/api/follow-ups/cadence") {
    validateFollowUpCadence(form, issues);
  }

  if (workflowKey === "/api/follow-ups/client") {
    validateFollowUpClient(form, issues);
  }

  if (workflowKey.startsWith("/api/follow-ups/") && workflowKey.endsWith("/outcome")) {
    validateFollowUpOutcome(form, issues);
  }

  if (workflowKey.startsWith("/api/reconciliation/") && workflowKey.endsWith("/confirm")) {
    requireText(form, issues, "receivable_id", "Receivable");
  }

  if (workflowKey.startsWith("/api/reconciliation/") && workflowKey.endsWith("/ignore")) {
    requireMinLength(form, issues, "reason", "Reason", 3);
  }

  if (workflowKey === "/api/revenue-rules") {
    validateRevenueRule(form, issues);
  }

  if (workflowKey === "import" || workflowKey === "reconciliation-import") {
    const file = fileOf(form, "file");
    if (!file) {
      issues.push({ field: "file", label: "CSV File", message: "Choose a CSV file first." });
    } else if (!file.name.toLowerCase().endsWith(".csv") && file.type !== "text/csv") {
      issues.push({ field: "file", label: "CSV File", message: "Use a CSV export file." });
    }
  }

  return dedupeIssues(issues);
}

function validateFollowUpCadence(form: HTMLFormElement, issues: WorkflowIssue[]) {
  for (const [field, label] of [["due_soon_days", "Days Before Due"], ["overdue_days", "Days Overdue"]] as const) {
    const value = valueOf(form, field);
    if (!value) {
      issues.push({ field, label, message: "Required." });
    } else if (!DAY_LIST_RE.test(value)) {
      issues.push({ field, label, message: "Use whole-day offsets separated by commas, such as 3, 7, 14." });
    } else if (value.split(",").some((part) => Number(part.trim()) > 365)) {
      issues.push({ field, label, message: "Each day offset must be 365 or less." });
    }
  }
  requireIntegerRange(form, issues, "minimum_gap_days", "Minimum Gap", 0, 90);
  requireIntegerRange(form, issues, "max_reminders", "Maximum Reminders", 1, 100);
  requireIntegerRange(form, issues, "stop_after_overdue_days", "Stop After Overdue Days", 1, 3650);
}

function validateRecurringRevenueTemplate(form: HTMLFormElement, issues: WorkflowIssue[]) {
  requireMinLength(form, issues, "name", "Template Name", 2);
  requireMinLength(form, issues, "client", "Client", 2);
  requireMinLength(form, issues, "reference_prefix", "Reference Prefix", 2);
  requirePositiveMoney(form, issues, "amount", "Amount");
  validateCurrencyEquivalent(form, issues);
  requireDate(form, issues, "start_on", "First Issue Date");
  requireIntegerRange(form, issues, "payment_terms_days", "Payment Terms", 0, 365);
  requireIntegerRange(form, issues, "generate_ahead_days", "Generate Ahead", 0, 90);
  requireIntegerRange(form, issues, "renewal_notice_days", "Renewal Notice", 1, 365);

  const kind = valueOf(form, "kind");
  const occurrences = valueOf(form, "total_occurrences");
  if (kind === "instalment" && !occurrences) {
    issues.push({ field: "total_occurrences", label: "Total Occurrences", message: "Required for instalment plans." });
  }
  if (occurrences) {
    const numeric = Number(occurrences);
    if (!Number.isInteger(numeric) || numeric < 1 || numeric > 600) {
      issues.push({ field: "total_occurrences", label: "Total Occurrences", message: "Enter a whole number from 1 to 600." });
    }
  }

  const startOn = valueOf(form, "start_on");
  for (const [field, label] of [["end_on", "End Date"], ["renewal_on", "Renewal Date"]] as const) {
    const value = valueOf(form, field);
    if (value && Number.isNaN(new Date(`${value}T00:00:00`).getTime())) {
      issues.push({ field, label, message: "Use a valid date." });
    } else if (value && startOn && value < startOn) {
      issues.push({ field, label, message: "Choose the first issue date or a later date." });
    }
  }
}

function validateFollowUpClient(form: HTMLFormElement, issues: WorkflowIssue[]) {
  requireText(form, issues, "client", "Client");
  requireText(form, issues, "status", "Contact Status");
  const status = valueOf(form, "status");
  const until = valueOf(form, "suppress_until");
  if (until && Number.isNaN(new Date(`${until}T00:00:00`).getTime())) {
    issues.push({ field: "suppress_until", label: "Suppress Until", message: "Use a valid date." });
  }
  if (status !== "active") {
    requireMinLength(form, issues, "reason", "Reason", 3);
  }
}

function validateFollowUpOutcome(form: HTMLFormElement, issues: WorkflowIssue[]) {
  requireText(form, issues, "outcome", "Outcome");
  const outcome = valueOf(form, "outcome");
  if (["disputed", "wrong_contact", "other"].includes(outcome)) {
    requireMinLength(form, issues, "note", "Outcome Note", 3);
  }
}

function requireIntegerRange(
  form: HTMLFormElement,
  issues: WorkflowIssue[],
  field: string,
  label: string,
  minimum: number,
  maximum: number,
) {
  const value = valueOf(form, field);
  const numeric = Number(value);
  if (!value) {
    issues.push({ field, label, message: "Required." });
  } else if (!Number.isInteger(numeric) || numeric < minimum || numeric > maximum) {
    issues.push({ field, label, message: `Enter a whole number from ${minimum} to ${maximum}.` });
  }
}

function validateLead(form: HTMLFormElement, issues: WorkflowIssue[]) {
  requireText(form, issues, "title", "Lead");
  requireText(form, issues, "source", "Source");
  requireText(form, issues, "offer", "Offer");
  requirePositiveMoney(form, issues, "estimated_value", "Estimated Value");
  requireProbability(form, issues, "probability", "Probability");
  requireText(form, issues, "next_action", "Next Action");
  const followUp = valueOf(form, "follow_up_on");
  if (followUp && Number.isNaN(new Date(`${followUp}T00:00:00`).getTime())) {
    issues.push({ field: "follow_up_on", label: "Follow Up", message: "Use a valid date." });
  }
}

function validateConversion(form: HTMLFormElement, issues: WorkflowIssue[]) {
  requireText(form, issues, "lead_id", "Lead");
  requirePositiveMoney(form, issues, "amount", "Amount");
  const currency = valueOf(form, "currency").toUpperCase() || "GBP";
  const gbp = valueOf(form, "gbp_equivalent");
  if (currency !== "GBP" && !gbp) {
    issues.push({
      field: "gbp_equivalent",
      label: "GBP Equivalent",
      message: "Add a GBP equivalent for non-GBP income.",
    });
  }
  if (gbp) {
    requirePositiveMoney(form, issues, "gbp_equivalent", "GBP Equivalent");
  }
  const conversionDate = valueOf(form, "date");
  if (conversionDate && Number.isNaN(new Date(`${conversionDate}T00:00:00`).getTime())) {
    issues.push({ field: "date", label: "Date", message: "Use a valid date." });
  }
}

function validateReceivable(form: HTMLFormElement, issues: WorkflowIssue[]) {
  requireText(form, issues, "client", "Client");
  requireText(form, issues, "reference", "Reference");
  requirePositiveMoney(form, issues, "amount", "Amount");
  requireDate(form, issues, "due_on", "Due Date");
  validateCurrencyEquivalent(form, issues);
  const issuedOn = valueOf(form, "issued_on");
  const dueOn = valueOf(form, "due_on");
  if (issuedOn && Number.isNaN(new Date(`${issuedOn}T00:00:00`).getTime())) {
    issues.push({ field: "issued_on", label: "Issue Date", message: "Use a valid date." });
  }
  if (issuedOn && dueOn && dueOn < issuedOn) {
    issues.push({ field: "due_on", label: "Due Date", message: "Choose the issue date or a later date." });
  }
}

function validateReceivablePayment(form: HTMLFormElement, issues: WorkflowIssue[]) {
  requireText(form, issues, "receivable_id", "Receivable");
  requirePositiveMoney(form, issues, "amount", "Amount");
  validateCurrencyEquivalent(form, issues);
  const occurredOn = valueOf(form, "occurred_on");
  if (occurredOn && Number.isNaN(new Date(`${occurredOn}T00:00:00`).getTime())) {
    issues.push({ field: "occurred_on", label: "Payment Date", message: "Use a valid date." });
  }
}

function validateCurrencyEquivalent(form: HTMLFormElement, issues: WorkflowIssue[]) {
  const currency = valueOf(form, "currency").toUpperCase() || "GBP";
  const gbp = valueOf(form, "gbp_equivalent");
  if (currency !== "GBP" && !gbp) {
    issues.push({
      field: "gbp_equivalent",
      label: "GBP Equivalent",
      message: "Add a GBP equivalent for non-GBP amounts.",
    });
  }
  if (gbp) {
    requirePositiveMoney(form, issues, "gbp_equivalent", "GBP Equivalent");
  }
}

function validateRevenueRule(form: HTMLFormElement, issues: WorkflowIssue[]) {
  requireText(form, issues, "name", "Rule Name");
  requireText(form, issues, "action", "Approved Action");
  const threshold = valueOf(form, "threshold");
  if (!threshold) {
    issues.push({ field: "threshold", label: "Threshold", message: "Required." });
    return;
  }
  const numericThreshold = Number(threshold.replace(",", ".").replace(/%$/, ""));
  if (!PERCENT_RE.test(threshold.replace(/%$/, "")) || numericThreshold < 0) {
    issues.push({ field: "threshold", label: "Threshold", message: "Enter zero or a positive number." });
    return;
  }
  const metric = valueOf(form, "metric");
  if (["conversion_rate_pct", "win_rate_pct", "opportunity_score"].includes(metric) && numericThreshold > 100) {
    issues.push({ field: "threshold", label: "Threshold", message: "Percent and score thresholds cannot exceed 100." });
  }
}

function validateApprovalDraft(form: HTMLFormElement, issues: WorkflowIssue[]) {
  const kind = valueOf(form, "kind");
  if (kind === "invoice_reminder") {
    requireText(form, issues, "target", "Target");
    requirePositiveMoney(form, issues, "amount", "Amount");
    requireDate(form, issues, "due", "Due");
    requireText(form, issues, "invoice", "Invoice");
    return;
  }
  if (kind === "outreach") {
    requireText(form, issues, "target", "Target");
    requireText(form, issues, "offer", "Offer");
    requireText(form, issues, "goal", "Goal");
    return;
  }
  if (kind === "content_prompt") {
    requireText(form, issues, "topic", "Topic");
    requireText(form, issues, "channel", "Channel");
    requireText(form, issues, "goal", "Goal");
  }
}

function nativeIssues(form: HTMLFormElement): WorkflowIssue[] {
  return Array.from(form.elements)
    .filter(isFormControl)
    .filter((control) => !control.validity.valid)
    .map((control) => ({
      field: control.name || control.id,
      label: labelFor(control),
      message: control.validationMessage || "Check this field.",
    }));
}

function dedupeIssues(issues: WorkflowIssue[]): WorkflowIssue[] {
  const byField = new Map<string, WorkflowIssue>();
  for (const issue of issues) {
    byField.set(issue.field || issue.message, issue);
  }
  return Array.from(byField.values());
}

function requireText(form: HTMLFormElement, issues: WorkflowIssue[], field: string, label: string) {
  if (!valueOf(form, field)) {
    issues.push({ field, label, message: "Required." });
  }
}

function requireMinLength(form: HTMLFormElement, issues: WorkflowIssue[], field: string, label: string, minLength: number) {
  const value = valueOf(form, field);
  if (value && value.length < minLength) {
    issues.push({ field, label, message: `Use at least ${minLength} characters.` });
  }
}

function requirePositiveMoney(form: HTMLFormElement, issues: WorkflowIssue[], field: string, label: string) {
  const value = valueOf(form, field);
  if (!value) {
    issues.push({ field, label, message: "Required." });
    return;
  }
  if (!MONEY_RE.test(value) || Number(value.replace(",", ".")) <= 0) {
    issues.push({ field, label, message: "Enter a positive amount." });
  }
}

function requireProbability(form: HTMLFormElement, issues: WorkflowIssue[], field: string, label: string) {
  const value = valueOf(form, field);
  if (!value) {
    issues.push({ field, label, message: "Required." });
    return;
  }
  if (!PERCENT_RE.test(value) || Number(value.replace(",", ".")) < 0 || Number(value.replace(",", ".")) > 100) {
    issues.push({ field, label, message: "Enter a percent from 0 to 100." });
  }
}

function requireDate(form: HTMLFormElement, issues: WorkflowIssue[], field: string, label: string) {
  const value = valueOf(form, field);
  if (!value) {
    issues.push({ field, label, message: "Required." });
    return;
  }
  if (Number.isNaN(new Date(`${value}T00:00:00`).getTime())) {
    issues.push({ field, label, message: "Use a valid date." });
  }
}

function validateOptionalEmail(form: HTMLFormElement, issues: WorkflowIssue[], field: string, label: string) {
  const value = valueOf(form, field);
  if (value && !EMAIL_RE.test(value)) {
    issues.push({ field, label, message: "Use an address like owner@example.com." });
  }
}

function valueOf(form: HTMLFormElement, field: string): string {
  const control = getControl(form, field);
  return control?.value.trim() || "";
}

function fileOf(form: HTMLFormElement, field: string): File | null {
  const control = getControl(form, field);
  if (control instanceof HTMLInputElement && control.type === "file") {
    return control.files?.[0] || null;
  }
  return null;
}

function getControl(form: HTMLFormElement, field: string): FormControl | null {
  const element = form.elements.namedItem(field);
  if (isFormControl(element)) {
    return element;
  }
  return null;
}

function labelFor(control: FormControl): string {
  const label = control.closest("label");
  if (!label) {
    return control.name || "Field";
  }
  return Array.from(label.childNodes)
    .filter((node) => node.nodeType === Node.TEXT_NODE)
    .map((node) => node.textContent?.trim() || "")
    .join(" ")
    .trim() || control.name || "Field";
}

function isPastDate(value: string): boolean {
  const selected = new Date(`${value}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return selected < today;
}

function isFormControl(element: unknown): element is FormControl {
  return element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement;
}
