import type { AuthStatus, DashboardPayload } from "../types";

export function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export function formPayload(form: HTMLFormElement): Record<string, string> {
  const data = new FormData(form);
  const payload: Record<string, string> = {};
  for (const [key, value] of data.entries()) {
    if (typeof value === "string" && value.trim() !== "") {
      payload[key] = value.trim();
    }
  }
  return payload;
}

export function authFromPayload(payload: unknown): AuthStatus | null {
  if (!payload || typeof payload !== "object" || !("auth" in payload)) {
    return null;
  }
  return (payload as { auth: AuthStatus }).auth;
}

export function canLoadDashboard(auth: AuthStatus) {
  return !auth.enabled || (auth.authenticated && !auth.setup_required);
}

export function accountLabel(auth: AuthStatus) {
  const account = auth.account;
  if (!account) {
    return "Account: local";
  }
  return `${account.display_name || account.username} - ${account.role}`;
}

export function runningStrategyCount(payload: DashboardPayload) {
  return payload.opportunities.filter((item) => item.score >= 50).length;
}

export function riskLabel(judgement: string) {
  if (judgement === "wrath risk") return "moderate";
  if (judgement === "needs offerings") return "elevated";
  if (judgement === "quota satisfied") return "low";
  return "managed";
}

export function externalItemText(item: Record<string, string>) {
  if (item.one_unit) return `${item.currency}: ${item.one_unit}`;
  if (item.net) return `${item.currency}: ${item.net} net (${item.transaction_count})`;
  if (item.label) return `${item.label}: ${item.value}`;
  return JSON.stringify(item);
}

export function actionPastTense(decision: string) {
  if (decision === "approve") return "Draft approved";
  if (decision === "reject") return "Draft rejected";
  if (decision === "complete") return "Draft completed";
  return "Draft updated";
}

export function recommendationBorder(recommendation: string) {
  if (recommendation === "push") return "border-l-temple-green";
  if (recommendation === "pause") return "border-l-temple-gold";
  return "border-l-temple-blue";
}

export function externalBorder(state: string) {
  if (state === "connected") return "border-l-temple-green";
  if (state === "ready" || state === "disabled") return "border-l-temple-gold";
  if (state === "error") return "border-l-temple-red";
  return "border-l-temple-blue";
}

export function approvalBorder(status: string) {
  if (status === "pending") return "border-l-temple-gold";
  if (status === "approved") return "border-l-temple-green";
  if (status === "rejected") return "border-l-temple-red";
  if (status === "completed") return "border-l-temple-violet";
  return "border-l-temple-blue";
}

export function importBorder(status: string) {
  if (status === "skipped") return "border-l-temple-gold";
  if (status === "duplicate") return "border-l-temple-violet";
  if (status === "imported" || status === "ready") return "border-l-temple-green";
  return "border-l-temple-blue";
}

export function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--:--:--";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function shortDate(value: string) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function capitalize(value: string) {
  return String(value).charAt(0).toUpperCase() + String(value).slice(1);
}

export function titleCase(value: string) {
  return String(value)
    .split(" ")
    .map(capitalize)
    .join(" ");
}

export function slugify(value: string) {
  return (
    String(value)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || "strategy"
  );
}
