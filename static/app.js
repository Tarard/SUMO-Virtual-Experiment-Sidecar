const state = {
  sessionId: null,
};

const el = (id) => document.getElementById(id);

function log(message, payload = null) {
  const line = `[${new Date().toLocaleTimeString()}] ${message}`;
  const detail = payload ? `\n${JSON.stringify(payload, null, 2)}` : "";
  el("logOutput").textContent = `${line}${detail}\n\n${el("logOutput").textContent}`;
}

function setControls(enabled) {
  for (const id of ["stepBtn", "runUntilBtn", "screenshotBtn", "stateBtn", "evidenceBtn", "closeBtn"]) {
    el(id).disabled = !enabled;
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || response.statusText);
  }
  return body;
}

function renderState(body) {
  state.sessionId = body.id;
  el("sessionId").textContent = body.id || "none";
  el("sessionDir").textContent = body.session_dir || "not created";
  el("baselineState").textContent = JSON.stringify(body.baseline || {}, null, 2);
  el("variantState").textContent = JSON.stringify(body.variant || {}, null, 2);
  setControls(Boolean(body.id));
}

function sessionPayload() {
  const payload = {
    name: el("sessionName").value,
    baseline_config: el("baselineConfig").value,
    variant_config: el("variantConfig").value,
    start: el("autoStart").checked,
    quit_on_end: el("quitOnEnd").checked,
  };
  if (el("outputRoot").value.trim()) payload.output_root = el("outputRoot").value.trim();
  if (el("sumoGuiBinary").value.trim()) payload.sumo_gui_binary = el("sumoGuiBinary").value.trim();
  return payload;
}

el("preflightBtn").addEventListener("click", async () => {
  try {
    const body = await api("/api/preflight");
    log("Preflight", body);
  } catch (error) {
    log(`Preflight failed: ${error.message}`);
  }
});

el("createBtn").addEventListener("click", async () => {
  try {
    const body = await api("/api/session/create", {
      method: "POST",
      body: JSON.stringify(sessionPayload()),
    });
    renderState(body);
    log("Created paired session", body);
  } catch (error) {
    log(`Create failed: ${error.message}`);
  }
});

el("stepBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/step`, {
      method: "POST",
      body: JSON.stringify({ count: Number(el("stepCount").value) }),
    });
    renderState(body);
    log("Stepped both simulations", body);
  } catch (error) {
    log(`Step failed: ${error.message}`);
  }
});

el("runUntilBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/run-until`, {
      method: "POST",
      body: JSON.stringify({ target_time: Number(el("targetTime").value) }),
    });
    renderState(body);
    log("Ran both simulations", body);
  } catch (error) {
    log(`Run-until failed: ${error.message}`);
  }
});

el("screenshotBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/screenshot`, {
      method: "POST",
      body: JSON.stringify({ label: el("screenshotLabel").value }),
    });
    log("Captured paired screenshots", body);
    await loadEvidence();
  } catch (error) {
    log(`Screenshot failed: ${error.message}`);
  }
});

async function refreshState() {
  const body = await api(`/api/session/${state.sessionId}/state`);
  renderState(body);
  log("Refreshed state", body);
}

async function loadEvidence() {
  const body = await api(`/api/session/${state.sessionId}/evidence`);
  el("sessionDir").textContent = body.session_dir;
  const artifacts = (body.artifacts || [])
    .map((item) => `${item.relative_path}  (${item.size_bytes} bytes)`)
    .join("\n");
  el("artifactList").textContent = artifacts || "No artifacts found.";
  el("evidencePreview").textContent = body.comparison_markdown;
  log("Loaded evidence", { session_dir: body.session_dir });
}

el("stateBtn").addEventListener("click", async () => {
  try {
    await refreshState();
  } catch (error) {
    log(`State refresh failed: ${error.message}`);
  }
});

el("evidenceBtn").addEventListener("click", async () => {
  try {
    await loadEvidence();
  } catch (error) {
    log(`Evidence load failed: ${error.message}`);
  }
});

el("closeBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/close`, { method: "POST" });
    log("Closed session", body);
    setControls(false);
  } catch (error) {
    log(`Close failed: ${error.message}`);
  }
});

setControls(false);
