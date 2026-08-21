const state = {
  busy: false,
  refreshMs: 1000,
  timerId: null,
  active: false,
};

document.addEventListener("DOMContentLoaded", () => {
  document.querySelector("[data-action='stop']").addEventListener("click", stopModel);
  document.querySelector("[data-action='shutdown']").addEventListener("click", shutdownServer);
  document.querySelector("[data-action='send']").addEventListener("click", sendPrompt);
  document.querySelector("[data-action='clear']").addEventListener("click", clearPrompt);
  document.querySelector("[data-action='copy-claude']").addEventListener("click", copyClaudeCommand);
  document.querySelector("[data-action='copy-continue']").addEventListener("click", copyContinueCommand);

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
            const content = data.choices?.[0]?.delta?.content || "";
            answer.textContent += content;
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
  state.active = active;
  
  if (!state.busy) {
    const stopModelBtn = document.querySelector("[data-action='stop']");
    if (stopModelBtn) {
      stopModelBtn.disabled = !active;
    }
  }

  const pill = document.getElementById("activePill");
  pill.textContent = active ? serverState.model_name : "Idle";
  pill.className = `pill ${active ? "green" : ""}`;

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
  document.getElementById("claudeCommand").textContent = claudeCommand(status);
  document.getElementById("continueCommand").textContent = continueCommand(status);
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

function continueCommand(status) {
  const active = status.state || {};
  const activeModel = active.model_name || "qwen";
  let modelStr = "keXjos/Qwen3.8-9B-mlx-4Bit";
  if (active.model) {
    modelStr = active.model;
  } else if (activeModel === "devstral") {
    modelStr = "mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit";
  }
  
  return `{
  "models": [
    {
      "title": "Local ${activeModel}",
      "provider": "openai",
      "model": "${modelStr}",
      "apiBase": "http://127.0.0.1:8080/v1"
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
