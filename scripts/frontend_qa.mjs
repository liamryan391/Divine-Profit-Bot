import { readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = dirname(dirname(fileURLToPath(import.meta.url)));
const staticDir = join(rootDir, "divine_tool", "static");
const indexPath = join(staticDir, "index.html");
const appSourcePath = join(rootDir, "frontend", "src", "App.tsx");
const html = readFileSync(indexPath, "utf8");
const appSource = readFileSync(appSourcePath, "utf8");

function fail(message) {
  console.error(`frontend QA failed: ${message}`);
  process.exit(1);
}

function assetPath(pattern, label) {
  const match = html.match(pattern);
  if (!match) {
    fail(`missing ${label} asset reference`);
  }
  return join(staticDir, match[1]);
}

const cssPath = assetPath(/href="\/(assets\/index-[^"]+\.css)"/, "CSS");
const jsPath = assetPath(/src="\/(assets\/index-[^"]+\.js)"/, "JS");
const css = readFileSync(cssPath, "utf8");
const js = readFileSync(jsPath, "utf8");

for (const [file, label] of [
  [cssPath, "CSS"],
  [jsPath, "JS"],
]) {
  if (statSync(file).size <= 0) {
    fail(`${label} asset is empty`);
  }
}

const requiredHtml = ["Divine Income Engine", "/assets/"];
const requiredCss = [".temple-shell", ".skip-link", "prefers-reduced-motion", "focus-visible"];
const requiredJs = [
  "Opening the temple",
  "Skip to dashboard content",
  "Lead Pipeline",
  "Conversion Tracking",
  "Revenue Rules",
  "Worker Operations",
  "Recent Worker Cycles",
  "Restart the web server",
  "Create Lead",
  "Create Rule",
  "/api/leads",
  "/api/conversions/record",
  "/api/revenue-rules",
  "/api/worker/status",
  "/api/daemon/run-once",
  "Lead intake",
  "due follow-ups",
  "No report has been generated for this session.",
  "CSV files must be 4 MiB or smaller.",
];

for (const token of requiredHtml) {
  if (!html.includes(token)) {
    fail(`index.html missing ${token}`);
  }
}

for (const token of requiredCss) {
  if (!css.includes(token)) {
    fail(`CSS missing ${token}`);
  }
}

for (const token of requiredJs) {
  if (!js.includes(token)) {
    fail(`JS missing ${token}`);
  }
}

if (!appSource.includes('apiRequest<{ worker: DashboardPayload["worker"] }>("/api/worker/status")')) {
  fail("worker polling does not use the lightweight status endpoint");
}

if (!appSource.includes("void refreshWorker();") || appSource.includes("void refreshDashboard(false);")) {
  fail("10-second polling is not isolated to worker status");
}

console.log("frontend QA passed");
