const state = {
  latest: null,
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
  renderConfig(payload);
  renderLogs(payload.events);
  renderIncome(payload.income);
  renderUpgrades(payload.upgrades);
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
    row.querySelector("span").textContent = `${item.source} - ${item.occurred_at}`;
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
  const select = $("#incomeStrategy");
  const currentValue = select.value;
  select.replaceChildren();
  const unassigned = document.createElement("option");
  unassigned.value = "";
  unassigned.textContent = "Unassigned";
  select.appendChild(unassigned);
  for (const channel of config.channels || []) {
    const option = document.createElement("option");
    option.value = channel.id || slugify(channel.name);
    option.textContent = channel.name;
    select.appendChild(option);
  }
  select.value = [...select.options].some((option) => option.value === currentValue) ? currentValue : "";
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
refresh();
setInterval(refresh, 10000);
