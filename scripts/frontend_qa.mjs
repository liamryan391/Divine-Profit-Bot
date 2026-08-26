import { readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = dirname(dirname(fileURLToPath(import.meta.url)));
const staticDir = join(rootDir, "divine_tool", "static");
const indexPath = join(staticDir, "index.html");
const html = readFileSync(indexPath, "utf8");

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
  "Create Lead",
  "/api/leads",
  "Lead intake",
  "due follow-ups",
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

console.log("frontend QA passed");
