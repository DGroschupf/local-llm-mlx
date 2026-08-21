const state = {
  busy: false,
  refreshMs: 1000,
  timerId: null,
};

document.addEventListener("DOMContentLoaded", () => {
  document.querySelector("[data-action='stop']").addEventListener("click", stopModel);
  document.querySelector("[data-action='send']").addEventListener("click", sendPrompt);
  document.querySelector("[data-action='clear']").addEventListener("click", clearPrompt);
  document.querySelector("[data-action='copy-claude']").addEventListener("click", copyClaudeCommand);

  document.querySelectorAll("[data-start-model]").forEach((button) => {
    button.addEventListener("click", () => {
      startModel(button.dataset.startModel, button.dataset.backend || "mlx");
    });
  });

  configureRefresh().then(refresh);
});

async function configureRefresh() {
  const config = await api("/api/config");
  state.refreshMs = Math.max(1, Number(config.refresh_seconds || 1)) * 1000;
  document.getElementById("refreshText").textContent = `updates every ${state.refreshMs / 1000}s`;

  if (state.timerId) {
    clearInterval(state.timerId);
  }
  state.timerId = setInterval(refresh, state.refreshMs);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

async function refresh() {
  const status = await api("/api/status");
  renderStatus(status);
}

async function startModel(name, backend) {
  if (state.busy) {
    return;
  }
  state.busy = true;
  setButtonsDisabled(true);
  try {
    await api(`/api/start/${name}:${backend}`, { method: "POST" });
    await refresh();
  } finally {
    state.busy = false;
    setButtonsDisabled(false);
  }
}

async function stopModel() {
  if (state.busy) {
    return;
  }
  state.busy = true;
  setButtonsDisabled(true);
  try {
    await api("/api/stop", { method: "POST" });
    await refresh();
  } finally {
    state.busy = false;
    setButtonsDisabled(false);
  }
}

async function sendPrompt() {
  const prompt = document.getElementById("prompt").value.trim();
  if (!prompt || state.busy) {
    return;
  }

  state.busy = true;
  setButtonsDisabled(true);
  const answer = document.getElementById("answer");
  answer.textContent = "Thinking...";

  try {
    const data = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    answer.textContent = data.content || "(empty response)";
    await refresh();
  } catch (error) {
    answer.textContent = error.message;
  } finally {
    state.busy = false;
    setButtonsDisabled(false);
  }
}

function clearPrompt() {
  document.getElementById("prompt").value = "";
}

function renderStatus(status) {
  const serverState = status.state || {};
  const memory = status.memory || {};
  const active = Boolean(status.active);

  const pill = document.getElementById("activePill");
  pill.textContent = active ? serverState.model_name : "Idle";
  pill.className = `pill ${active ? "green" : ""}`;

  document.getElementById("serverText").textContent = active
    ? `${serverState.model} on ${serverState.host}:${serverState.port} | PID ${serverState.pid}`
    : "No model server loaded.";

  const pressure = document.getElementById("pressure");
  pressure.textContent = memory.pressure || "-";
  pressure.className = memory.pressure || "";

  document.getElementById("rss").textContent = formatGb(memory.process_rss_gb);
  document.getElementById("available").textContent = formatGb(memory.available_gb);
  document.getElementById("swap").textContent = formatGb(memory.swap_used_gb);

  document.getElementById("fit").replaceChildren(...fitCards(status.fit.models));
  document.getElementById("commands").textContent = commandText(status.commands);
  document.getElementById("claudeCommand").textContent = claudeCommand(status);
}

function fitCards(models) {
  return Object.entries(models).map(([name, info]) => {
    const card = document.createElement("div");
    card.className = "fit-card";

    const title = document.createElement("div");
    title.className = "fit-title";

    const model = document.createElement("strong");
    model.textContent = name;

    const level = document.createElement("span");
    level.className = info.level;
    level.textContent = info.level;

    const message = document.createElement("div");
    message.className = "muted";
    message.textContent = info.message;

    title.append(model, level);
    card.append(title, message);
    return card;
  });
}

function commandText(commands) {
  return Object.entries(commands)
    .map(([name, values]) => {
      const lines = [`${name}`, `  ${values.chat}`, `  ${values.serve}`];
      if (values.serve_agent) {
        lines.push(`  ${values.serve_agent}`);
      }
      return lines.join("\n");
    })
    .join("\n\n");
}

function claudeCommand(status) {
  const active = status.state || {};
  const activeModel = active.model_name;
  if (activeModel && status.commands[activeModel]?.claude) {
    return status.commands[activeModel].claude;
  }
  return status.commands.devstral?.claude || "";
}

async function copyClaudeCommand(event) {
  const command = document.getElementById("claudeCommand").textContent.trim();
  if (!command) {
    return;
  }
  await navigator.clipboard.writeText(command);
  event.target.classList.add("copied");
  event.target.textContent = "Copied";
  setTimeout(() => {
    event.target.classList.remove("copied");
    event.target.textContent = "Copy";
  }, 1400);
}

function formatGb(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${Number(value).toFixed(2)} GB`;
}

function setButtonsDisabled(disabled) {
  document.querySelectorAll("button").forEach((button) => {
    button.disabled = disabled;
  });
}
