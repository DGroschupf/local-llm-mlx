const state = {
  busy: false,
  refreshMs: 1000,
  timerId: null,
  active: false,
  lastStatus: null,
  claudeModel: null,
  continueModel: null,
};

document.addEventListener("DOMContentLoaded", () => {
  document.querySelector("[data-action='stop']").addEventListener("click", stopModel);
  document.querySelector("[data-action='shutdown']").addEventListener("click", shutdownServer);
  document.querySelector("[data-action='send']").addEventListener("click", sendPrompt);
  document.querySelector("[data-action='clear']").addEventListener("click", clearPrompt);
  document.querySelector("[data-action='copy-claude']").addEventListener("click", copyClaudeCommand);
  document.querySelector("[data-action='copy-continue']").addEventListener("click", copyContinueCommand);

  document.getElementById("claudeModelSelect").addEventListener("change", (event) => {
    state.claudeModel = event.target.value;
    if (state.lastStatus) renderSnippets(state.lastStatus);
  });
  document.getElementById("continueModelSelect").addEventListener("change", (event) => {
    state.continueModel = event.target.value;
    if (state.lastStatus) renderSnippets(state.lastStatus);
  });

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
  const cache = await api("/api/cache");
  renderCache(cache);
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
  
  const stopBtn = document.querySelector("[data-action='stop']");
  const originalHtml = stopBtn.innerHTML;
  stopBtn.innerHTML = '<span class="icon">⏹</span> Stopping...';
  
  state.busy = true;
  setButtonsDisabled(true);
  try {
    await api("/api/stop", { method: "POST" });
    stopBtn.innerHTML = '<span class="icon">✓</span> Stopped!';
    stopBtn.classList.add("copied");
    await refresh();
  } finally {
    setTimeout(() => {
      stopBtn.innerHTML = originalHtml;
      stopBtn.classList.remove("copied");
    }, 1400);
    state.busy = false;
    setButtonsDisabled(false);
  }
}

async function shutdownServer() {
  if (state.busy) {
    return;
  }
  state.busy = true;
  setButtonsDisabled(true);
  clearInterval(state.timerId);
  try {
    await api("/api/shutdown", { method: "POST" });
    document.body.innerHTML = "<div style='display:flex;align-items:center;justify-content:center;height:100vh;color:#fff;font-family:ui-sans-serif,system-ui,sans-serif;'><h2>Server and UI have been shut down. You can close this tab.</h2></div>";
  } catch (err) {
    alert("Failed to shutdown server: " + err.message);
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
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    
    if (!response.ok) {
      throw new Error(await response.text());
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    answer.textContent = "";

    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep the last partial line in the buffer
      
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const dataStr = line.slice(6).trim();
          if (dataStr === "[DONE]") continue;
          try {
            const data = JSON.parse(dataStr);
            const delta = data.choices?.[0]?.delta || {};
            const content = delta.content || "";
            const reasoning = delta.reasoning_content || "";
            answer.textContent += reasoning + content;
          } catch (e) {
            console.error("Failed to parse SSE data:", dataStr, e);
          }
        }
      }
    }
    
    if (!answer.textContent) {
      answer.textContent = "(empty response)";
    }
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
  const activeModel = serverState.model_name;
  const activeBackend = serverState.backend || "mlx";
  state.active = active;
  
  if (!state.busy) {
    const stopModelBtn = document.querySelector("[data-action='stop']");
    if (stopModelBtn) {
      stopModelBtn.disabled = !active;
    }
  }

  const pill = document.getElementById("activePill");
  pill.textContent = active ? `${serverState.model_name} · ${backendLabel(activeBackend)}` : "Idle";
  pill.className = `pill ${active ? "green" : ""}`;

  document.querySelectorAll("[data-start-model]").forEach((button) => {
    if (!button.dataset.label) {
      button.dataset.label = button.textContent;
    }
    const isActive = active
      && button.dataset.startModel === activeModel
      && (button.dataset.backend || "mlx") === activeBackend;
    button.classList.toggle("active-model", isActive);
    button.setAttribute("aria-pressed", String(isActive));
    button.textContent = isActive ? `${button.dataset.label} · Running` : button.dataset.label;
  });

  renderDownloadBadges(status.models || {});

  const pulse = document.querySelector(".pulse");
  if (pulse) {
    pulse.className = `pulse ${active ? "active" : ""}`;
  }

  document.getElementById("serverText").textContent = active
    ? `${serverState.model} on ${serverState.host}:${serverState.port} | PID ${serverState.pid}`
    : "No model server loaded.";

  const pressure = document.getElementById("pressure");
  const pVal = memory.pressure || "-";
  pressure.textContent = pVal !== "-" ? pVal.charAt(0).toUpperCase() + pVal.slice(1) : "-";
  pressure.className = memory.pressure || "";

  document.getElementById("rss").textContent = formatGb(memory.process_rss_gb);
  document.getElementById("available").textContent = formatGb(memory.available_gb);
  document.getElementById("swap").textContent = formatGb(memory.swap_used_gb);

  document.getElementById("fit").replaceChildren(...fitCards(status.fit.models));
  document.getElementById("commands").textContent = commandText(status.commands);

  state.lastStatus = status;
  renderSnippets(status);
}

function renderSnippets(status) {
  const activeModel = (status.state || {}).model_name;

  const claudeCapable = Object.keys(status.commands).filter((name) => status.commands[name]?.claude);
  populateModelSelect("claudeModelSelect", claudeCapable, status.models, "claudeModel", activeModel);

  const allModels = Object.keys(status.commands);
  populateModelSelect("continueModelSelect", allModels, status.models, "continueModel", activeModel);

  document.getElementById("claudeCommand").textContent = claudeCommand(status, state.claudeModel);
  document.getElementById("continueCommand").textContent = continueCommand(status, state.continueModel);
}

function populateModelSelect(selectId, names, models, stateKey, activeModel) {
  const select = document.getElementById(selectId);
  const existing = Array.from(select.options).map((option) => option.value);
  const sameOptions = existing.length === names.length && existing.every((value) => names.includes(value));

  if (!sameOptions) {
    select.replaceChildren(...names.map((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = models[name]?.role ? `${name} — ${models[name].role}` : name;
      return option;
    }));
  }

  if (!names.includes(state[stateKey])) {
    state[stateKey] = names.includes(activeModel) ? activeModel : names[0];
  }
  select.value = state[stateKey] || "";
}

function backendLabel(backend) {
  return backend === "agent" ? "Agent API" : "Chat";
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

function renderDownloadBadges(models) {
  document.querySelectorAll(".model-group").forEach((group) => {
    const button = group.querySelector("[data-start-model]");
    if (!button) return;
    const info = models[button.dataset.startModel];

    let badge = group.querySelector(".download-badge");
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "download-badge";
      group.querySelector("h3")?.append(badge);
    }
    if (info && info.downloaded) {
      badge.textContent = `${info.size_on_disk_gb.toFixed(2)} GB on disk`;
      badge.classList.add("downloaded");
    } else {
      badge.textContent = "not downloaded";
      badge.classList.remove("downloaded");
    }
  });
}

function renderCache(entries) {
  const list = document.getElementById("cacheList");
  if (!list) return;

  if (!entries.length) {
    list.replaceChildren(Object.assign(document.createElement("p"), {
      className: "muted",
      textContent: "Nothing cached yet.",
    }));
    return;
  }

  list.replaceChildren(...entries.map((entry) => {
    const card = document.createElement("div");
    card.className = "fit-card";

    const title = document.createElement("div");
    title.className = "fit-title";

    const name = document.createElement("strong");
    name.textContent = entry.model_name ? `${entry.model_name}` : entry.repo_id;

    const size = document.createElement("span");
    size.className = "muted";
    size.textContent = `${entry.size_gb.toFixed(2)} GB`;

    title.append(name, size);

    const path = document.createElement("div");
    path.className = "muted text-small";
    path.textContent = entry.repo_id;

    const actions = document.createElement("div");
    actions.className = "actions row-actions";

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "danger";
    deleteBtn.textContent = entry.active ? "Active · Stop to delete" : "Delete";
    deleteBtn.disabled = entry.active || state.busy;
    deleteBtn.addEventListener("click", () => deleteCacheEntry(entry.repo_id, deleteBtn));
    actions.append(deleteBtn);

    card.append(title, path, actions);
    return card;
  }));
}

async function deleteCacheEntry(repoId, button) {
  if (state.busy) return;
  if (!confirm(`Delete ${repoId} from disk? This cannot be undone.`)) return;

  state.busy = true;
  const originalText = button.textContent;
  button.textContent = "Deleting...";
  button.disabled = true;
  try {
    await api(`/api/cache/${encodeURIComponent(repoId)}`, { method: "DELETE" });
    await refresh();
  } catch (err) {
    alert("Failed to delete: " + err.message);
    button.textContent = originalText;
    button.disabled = false;
  } finally {
    state.busy = false;
  }
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

function claudeCommand(status, modelName) {
  return status.commands[modelName]?.claude || "";
}

function continueCommand(status, modelName) {
  const profile = status.models[modelName];
  if (!profile) return "";

  const title = `${profile.role || modelName} Local`;

  return `{
  "models": [
    {
      "title": ${JSON.stringify(title)},
      "provider": "openai",
      "model": ${JSON.stringify(profile.model)},
      "apiBase": "http://127.0.0.1:8080/v1",
      "apiKey": "sk-optiq-local",
      "contextLength": ${profile.chat_kv_size},
      "completionOptions": {
        "maxTokens": ${profile.max_tokens}
      },
      "roles": ["chat", "edit", "apply"],
      "capabilities": ["tool_use"]
    }
  ]
}`;
}

async function copyClaudeCommand(event) {
  const command = document.getElementById("claudeCommand").textContent.trim();
  if (!command) return;
  await navigator.clipboard.writeText(command);
  event.target.classList.add("copied");
  event.target.textContent = "Copied!";
  setTimeout(() => {
    event.target.classList.remove("copied");
    event.target.textContent = "Copy snippet";
  }, 1400);
}

async function copyContinueCommand(event) {
  const command = document.getElementById("continueCommand").textContent.trim();
  if (!command) return;
  await navigator.clipboard.writeText(command);
  event.target.classList.add("copied");
  event.target.textContent = "Copied!";
  setTimeout(() => {
    event.target.classList.remove("copied");
    event.target.textContent = "Copy snippet";
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
  if (!disabled) {
    const stopModelBtn = document.querySelector("[data-action='stop']");
    if (stopModelBtn) {
      stopModelBtn.disabled = !state.active;
    }
  }
}
