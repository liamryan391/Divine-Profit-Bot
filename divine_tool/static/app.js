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
  $("#templeNext").textContent = status.remaining_minor === 0 ? "Upgrade window unlocked" : "Next: v1.0 after Phase 1";
  $("#progressFill").style.width = `${Math.min(status.progress_pct, 100)}%`;
  $("#timeRemaining").textContent = `Time remaining: ${status.days_left} day${status.days_left === 1 ? "" : "s"}`;
  $("#judgementBadge").textContent = titleCase(status.judgement);

  renderWorker(payload.worker);
  renderStrategies(payload.opportunities);
  renderConfig(payload);
  renderLogs(payload.events);
  renderIncome(payload.income);
  renderUpgrades(payload.upgrades);
  hydrateMoodControls(payload.config);
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
      <strong></strong>
      <span></span>
      <b class="tag"></b>
    `;
    row.querySelector("strong").textContent = item.name;
    row.querySelector("span").textContent = item.expected;
    const tag = row.querySelector(".tag");
    tag.textContent = item.fit;
    if (item.fit === "deadline" || item.risk !== "low") {
      tag.classList.add("warn");
    }
    row.title = item.next_action;
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
  return payload.opportunities.filter((item) => item.fit !== "partial").length;
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

attachForm("#incomeForm", "/api/income", "Income recorded");
attachForm("#quotaForm", "/api/quota", "Quota updated");
attachForm("#moodForm", "/api/mood", "Mood updated");
attachForm("#exceptionForm", "/api/exception", "Exception added");
attachPulse();
refresh();
setInterval(refresh, 10000);
