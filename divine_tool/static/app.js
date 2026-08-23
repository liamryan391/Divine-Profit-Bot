const state = {
  latest: null,
  report: null,
  importResult: null,
  toastTimer: null,
};

const $ = (selector) => document.querySelector(selector);

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

async function refresh() {
  try {
    const payload = await request("/api/status");
    state.latest = payload;
    render(payload);
  } catch (error) {
    showToast(error.message);
  }
}

function render(payload) {
  const status = payload.status;
  $("#remainingValue").textContent = status.remaining;
  $("#quotaTarget").textContent = `${capitalize(status.period.name)} target: ${status.quota}`;
  $("#incomeValue").textContent = status.earned;
  $("#incomeProgress").textContent = `Progress: ${status.progress_pct}%`;
  $("#modulesValue").textContent = payload.config.channels.length;
  $("#modulesDetail").textContent = `${runningStrategyCount(payload)} active strategy signals`;
  $("#templeLevel").textContent = payload.version;
  $("#templeNext").textContent = status.remaining_minor === 0 ? "Upgrade window unlocked" : "Next: v1.2 after scoring data";
  $("#progressFill").style.width = `${Math.min(status.progress_pct, 100)}%`;
  $("#timeRemaining").textContent = `Time remaining: ${status.days_left} day${status.days_left === 1 ? "" : "s"}`;
  $("#judgementBadge").textContent = titleCase(status.judgement);

  renderWorker(payload.worker);
  renderTopOpportunity(payload.top_opportunity);
  renderStrategies(payload.opportunities);
  renderStrategyRoi(payload.strategy_roi);
  renderPriorityCalls(payload.strategy_roi);
  renderConfig(payload);
  renderLogs(payload.events);
  renderIncome(payload.income);
  renderUpgrades(payload.upgrades);
  renderReport(payload.report);
  hydrateMoodControls(payload.config);
  hydrateStrategyControls(payload.config);
}

function renderWorker(worker) {
  const pill = $("#workerPill");
  pill.classList.remove("running", "stale");
  if (worker.state === "running") {
    pill.classList.add("running");
  }
  if (worker.state === "stale") {
    pill.classList.add("stale");
  }
  const age = worker.age_seconds === null ? "no heartbeat" : `${worker.age_seconds}s ago`;
  $("#workerPillText").textContent = `Worker: ${worker.state} (${age})`;
}

function renderStrategies(opportunities) {
  const list = $("#strategiesList");
  list.replaceChildren();
  if (!opportunities.length) {
    list.appendChild(emptyRow("No strategies configured."));
    return;
  }
  for (const item of opportunities.slice(0, 5)) {
    const row = document.createElement("div");
    row.className = "strategy-row";
    row.innerHTML = `
      <div class="strategy-main">
        <strong></strong>
        <span></span>
        <small class="strategy-meta"></small>
      </div>
      <div class="score-stack">
        <b class="tag"></b>
        <div class="score-bar"><span></span></div>
      </div>
    `;
    row.querySelector("strong").textContent = item.name;
    row.querySelector("span").textContent = `${item.expected} expected - ${item.period_income} recorded this period`;
    row.querySelector(".strategy-meta").textContent = item.rationale;
    const tag = row.querySelector(".tag");
    tag.textContent = `${item.score}/100`;
    if (item.fit === "deadline" || item.risk !== "low") {
      tag.classList.add("warn");
    }
    row.querySelector(".score-bar span").style.width = `${Math.min(item.score, 100)}%`;
    row.title = item.next_action;
    list.appendChild(row);
  }
}

function renderTopOpportunity(item) {
  const grid = $("#componentGrid");
  grid.replaceChildren();
  if (!item) {
    $("#topName").textContent = "No recommendation available";
    $("#topScore").textContent = "score --";
    $("#topRationale").textContent = "Configure at least one strategy to generate a ranked offering.";
    return;
  }

  $("#topName").textContent = `#${item.rank} ${item.name}`;
  $("#topScore").textContent = `${item.score}/100 - ${titleCase(item.score_label)}`;
  $("#topRationale").textContent = `${item.rationale} Next action: ${item.next_action}`;
  for (const [label, value] of Object.entries(item.components)) {
    const chip = document.createElement("div");
    chip.className = "component-chip";
    chip.innerHTML = "<span></span><strong></strong>";
    chip.querySelector("span").textContent = label;
    chip.querySelector("strong").textContent = value;
    grid.appendChild(chip);
  }
}

function renderStrategyRoi(roi) {
  const list = $("#roiList");
  list.replaceChildren();
  if (!roi || !roi.rows || !roi.rows.length) {
    $("#roiPeriod").textContent = "no data";
    list.appendChild(emptyRow("No strategy ROI data yet."));
    return;
  }

  $("#roiPeriod").textContent = `${shortDate(roi.period.start)} to ${shortDate(roi.period.end)}`;
  for (const row of roi.rows) {
    const item = document.createElement("div");
    item.className = `roi-row recommendation-${row.recommendation}`;
    const notes = row.notes && row.notes.length ? row.notes : [];
    item.innerHTML = `
      <div class="roi-head">
        <div>
          <strong></strong>
          <span></span>
        </div>
        <b class="tag"></b>
      </div>
      <div class="roi-metrics">
        <div><span>Current</span><strong></strong></div>
        <div><span>Previous</span><strong></strong></div>
        <div><span>Delta</span><strong></strong></div>
        <div><span>Per Effort</span><strong></strong></div>
      </div>
      <div class="note-list"></div>
    `;
    item.querySelector(".roi-head strong").textContent = `#${row.roi_rank} ${row.name}`;
    item.querySelector(".roi-head span").textContent = `${titleCase(row.trend)} - ${row.target_capture_pct}% of expected value`;
    item.querySelector(".tag").textContent = row.recommendation;
    const metrics = item.querySelectorAll(".roi-metrics strong");
    metrics[0].textContent = row.current_period;
    metrics[1].textContent = row.previous_period;
    metrics[2].textContent = row.delta;
    metrics[3].textContent = row.roi_per_effort;

    const noteList = item.querySelector(".note-list");
    if (!notes.length) {
      const note = document.createElement("span");
      note.textContent = "No conversion notes recorded.";
      noteList.appendChild(note);
    } else {
      for (const noteItem of notes) {
        const note = document.createElement("span");
        note.textContent = `${noteItem.amount} - ${noteItem.note}`;
        noteList.appendChild(note);
      }
    }
    list.appendChild(item);
  }
}

function renderPriorityCalls(roi) {
  const list = $("#recommendationList");
  list.replaceChildren();
  if (!roi || !roi.rows || !roi.rows.length) {
    list.appendChild(emptyRow("No recommendations yet."));
    return;
  }

  const calls = [
    ...roi.push_recommendations.map((item) => ({ ...item, call: "Push" })),
    ...roi.pause_recommendations.map((item) => ({ ...item, call: "Pause" })),
  ];
  const visible = calls.length ? calls.slice(0, 5) : roi.rows.slice(0, 3).map((item) => ({ ...item, call: "Watch" }));
  for (const item of visible) {
    const row = document.createElement("div");
    row.className = `priority-row recommendation-${item.recommendation}`;
    row.innerHTML = "<strong></strong><span></span>";
    row.querySelector("strong").textContent = `${item.call}: ${item.name}`;
    row.querySelector("span").textContent = item.recommendation_reason;
    list.appendChild(row);
  }
}

function renderConfig(payload) {
  const list = $("#configList");
  const status = payload.status;
  const worker = payload.worker;
  list.replaceChildren(
    configRow("Primary Currency", payload.config.base_currency),
    configRow("Active Mood", status.mood),
    configRow("Risk Level", riskLabel(status.judgement)),
    configRow("Worker State", worker.state),
  );
}

function renderLogs(events) {
  const list = $("#logList");
  list.replaceChildren();
  if (!events.length) {
    const line = document.createElement("div");
    line.className = "log-line";
    line.innerHTML = "<time>--:--:--</time><span>system</span><strong>Temple initialized. Awaiting command.</strong>";
    list.appendChild(line);
    return;
  }
  for (const event of events.slice().reverse()) {
    const line = document.createElement("div");
    line.className = "log-line";
    line.innerHTML = "<time></time><span></span><strong></strong>";
    line.querySelector("time").textContent = formatTime(event.created_at);
    line.querySelector("span").textContent = event.category;
    line.querySelector("strong").textContent = event.message;
    list.appendChild(line);
  }
  list.scrollTop = list.scrollHeight;
}

function renderIncome(income) {
  const list = $("#incomeList");
  list.replaceChildren();
  if (!income.length) {
    list.appendChild(emptyRow("No income recorded yet."));
    return;
  }
  for (const item of income) {
    const row = document.createElement("div");
    row.className = "income-row";
    row.innerHTML = "<strong></strong><span></span>";
    row.querySelector("strong").textContent = item.counted;
    const strategy = item.strategy ? ` [${item.strategy}]` : "";
    const note = item.note ? ` - ${item.note}` : "";
    row.querySelector("span").textContent = `${item.source}${strategy} - ${item.occurred_at}${note}`;
    list.appendChild(row);
  }
}

function renderUpgrades(upgrades) {
  const list = $("#upgradeList");
  list.replaceChildren();
  for (const item of upgrades.slice(0, 6)) {
    const row = document.createElement("div");
    row.className = "upgrade-item";
    row.innerHTML = "<span></span>";
    row.querySelector("span").textContent = item;
    list.appendChild(row);
  }
}

function renderReport(report) {
  if (!report) {
    $("#reportTitle").textContent = "No report generated";
    $("#reportMeta").textContent = "Choose a period and generate a report.";
    $("#reportPreview").textContent = "";
    return;
  }
  state.report = report;
  $("#reportTitle").textContent = report.title;
  $("#reportMeta").textContent = `${report.period.start} to ${report.period.end} - ${report.earned} earned of ${report.quota}`;
  $("#reportPreview").textContent = report.markdown;
}

function hydrateMoodControls(config) {
  const moodNames = Object.keys(config.moods || {});
  for (const select of [$("#activeMood"), $("#quotaMood")]) {
    const currentValue = select.value || config.active_mood;
    select.replaceChildren();
    for (const mood of moodNames) {
      const option = document.createElement("option");
      option.value = mood;
      option.textContent = capitalize(mood);
      select.appendChild(option);
    }
    select.value = moodNames.includes(currentValue) ? currentValue : config.active_mood;
  }
}

function hydrateStrategyControls(config) {
  for (const selector of ["#incomeStrategy", "#importStrategy"]) {
    const select = $(selector);
    if (!select) continue;
    const currentValue = select.value;
    select.replaceChildren();
    const unassigned = document.createElement("option");
    unassigned.value = "";
    unassigned.textContent = selector === "#importStrategy" ? "Auto / Unassigned" : "Unassigned";
    select.appendChild(unassigned);
    for (const channel of config.channels || []) {
      const option = document.createElement("option");
      option.value = channel.id || slugify(channel.name);
      option.textContent = channel.name;
      select.appendChild(option);
    }
    select.value = [...select.options].some((option) => option.value === currentValue) ? currentValue : "";
  }
}

function configRow(label, value) {
  const row = document.createElement("div");
  row.className = "config-row";
  row.innerHTML = "<strong></strong><span></span>";
  row.querySelector("strong").textContent = label;
  row.querySelector("span").textContent = String(value).toUpperCase();
  return row;
}

function emptyRow(message) {
  const row = document.createElement("div");
  row.className = "strategy-row";
  row.innerHTML = "<span></span>";
  row.querySelector("span").textContent = message;
  return row;
}

function runningStrategyCount(payload) {
  return payload.opportunities.filter((item) => item.score >= 50).length;
}

function riskLabel(judgement) {
  if (judgement === "wrath risk") return "moderate";
  if (judgement === "needs offerings") return "elevated";
  if (judgement === "quota satisfied") return "low";
  return "managed";
}

function formPayload(form) {
  const data = new FormData(form);
  return Object.fromEntries([...data.entries()].filter(([, value]) => String(value).trim() !== ""));
}

function attachForm(selector, path, successMessage) {
  const form = $(selector);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type='submit']");
    button.disabled = true;
    try {
      const payload = await request(path, {
        method: "POST",
        body: JSON.stringify(formPayload(form)),
      });
      if (payload.state) {
        state.latest = payload.state;
        render(payload.state);
      } else {
        await refresh();
      }
      form.reset();
      showToast(successMessage);
    } catch (error) {
      showToast(error.message);
    } finally {
      button.disabled = false;
    }
  });
}

function attachPulse() {
  $("#pulseButton").addEventListener("click", async () => {
    const button = $("#pulseButton");
    button.disabled = true;
    try {
      const payload = await request("/api/daemon/run-once", { method: "POST", body: "{}" });
      state.latest = payload.state;
      render(payload.state);
      showToast("Worker pulse complete");
    } catch (error) {
      showToast(error.message);
    } finally {
      button.disabled = false;
    }
  });
}

function attachReportControls() {
  $("#reportButton").addEventListener("click", async () => {
    const button = $("#reportButton");
    button.disabled = true;
    try {
      const period = $("#reportPeriod").value;
      const payload = await request(`/api/report?period=${encodeURIComponent(period)}`);
      renderReport(payload.report);
      showToast("Report generated");
    } catch (error) {
      showToast(error.message);
    } finally {
      button.disabled = false;
    }
  });

  $("#downloadReportButton").addEventListener("click", () => {
    if (!state.report) {
      showToast("Generate a report first");
      return;
    }
    const filename = `${slugify(state.report.title)}_${state.report.period.start}_${state.report.period.end}.md`;
    const blob = new Blob([state.report.markdown], { type: "text/markdown;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
  });
}

function attachImportControls() {
  $("#importForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const file = form.elements.file.files[0];
    if (!file) {
      showToast("Choose a CSV file first");
      return;
    }
    const button = form.querySelector("button[type='submit']");
    button.disabled = true;
    try {
      const payload = await request("/api/import/csv", {
        method: "POST",
        body: JSON.stringify({
          csv_text: await file.text(),
          filename: file.name,
          source_type: form.elements.source_type.value,
          default_strategy: form.elements.default_strategy.value,
          dry_run: form.elements.dry_run.checked,
        }),
      });
      state.latest = payload.state;
      render(payload.state);
      renderImportResult(payload.import_result);
      showToast(form.elements.dry_run.checked ? "Import dry run complete" : "CSV import complete");
    } catch (error) {
      showToast(error.message);
    } finally {
      button.disabled = false;
    }
  });
}

function renderImportResult(result) {
  state.importResult = result;
  const target = $("#importResult");
  target.replaceChildren();
  if (!result) return;
  const summary = document.createElement("div");
  summary.className = "import-summary";
  summary.innerHTML = "<strong></strong><span></span>";
  summary.querySelector("strong").textContent = result.dry_run ? "Dry Run Complete" : "Import Complete";
  const primaryCount = result.dry_run ? `${result.ready_count || 0} ready` : `${result.imported_count} imported`;
  summary.querySelector("span").textContent =
    `${primaryCount}, ${result.duplicate_count} duplicate, ${result.skipped_count} skipped`;
  target.appendChild(summary);

  const rows = result.rows.filter((row) => row.status !== "parsed").slice(0, 8);
  for (const row of rows) {
    const item = document.createElement("div");
    item.className = `import-row import-${row.status}`;
    item.innerHTML = "<strong></strong><span></span>";
    item.querySelector("strong").textContent = `Row ${row.row_number || "?"}: ${titleCase(row.status)}`;
    item.querySelector("span").textContent =
      row.reason || (row.existing_id ? `Existing income #${row.existing_id}` : `${row.gbp || ""} ${row.source || ""}`);
    target.appendChild(item);
  }
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.classList.remove("visible"), 2800);
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--:--:--";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function shortDate(value) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

function capitalize(value) {
  return String(value).charAt(0).toUpperCase() + String(value).slice(1);
}

function titleCase(value) {
  return String(value)
    .split(" ")
    .map(capitalize)
    .join(" ");
}

function slugify(value) {
  return String(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || "strategy";
}

attachForm("#incomeForm", "/api/income", "Income recorded");
attachForm("#quotaForm", "/api/quota", "Quota updated");
attachForm("#moodForm", "/api/mood", "Mood updated");
attachForm("#exceptionForm", "/api/exception", "Exception added");
attachPulse();
attachReportControls();
attachImportControls();
refresh();
setInterval(refresh, 10000);
