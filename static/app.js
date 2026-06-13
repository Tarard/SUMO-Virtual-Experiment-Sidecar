const state = {
  sessionId: null,
  hasExperimentStateBoard: false,
};

const scenarioTemplates = new Map();
const visualObservationTaxonomy = new Map();

const el = (id) => document.getElementById(id);

function log(message, payload = null) {
  const line = `[${new Date().toLocaleTimeString()}] ${message}`;
  const detail = payload ? `\n${JSON.stringify(payload, null, 2)}` : "";
  el("logOutput").textContent = `${line}${detail}\n\n${el("logOutput").textContent}`;
}

function setControls(enabled) {
  for (const id of [
    "stepBtn",
    "runUntilBtn",
    "screenshotBtn",
    "templateCheckpointBtn",
    "addTimelineNoteBtn",
    "recordChangeBtn",
    "startScenarioBtn",
    "recordScenarioChangeBtn",
    "scenarioStatusBtn",
    "firstCheckpointBtn",
    "stateBtn",
    "workflowBtn",
    "compareReadinessBtn",
    "exportExperimentStateBoardBtn",
    "enableLiveExperimentStateBoardBtn",
    "runEvidenceLoopBtn",
    "evidenceBtn",
    "exportPacketBtn",
    "exportAgentPromptBtn",
    "exportAgentActionPlanBtn",
    "exportAgentLoopReviewBtn",
    "recordAgentFeedbackBtn",
    "recordAgentActionOutcomeBtn",
    "exportNextActionReviewBtn",
    "exportTimelineBtn",
    "compareMetricsBtn",
    "exportMetricChartBtn",
    "exportReviewSummaryBtn",
    "exportVisualDiffBtn",
    "recordVisualObservationBtn",
    "recordGuidedVisualObservationBtn",
    "closeBtn",
  ]) {
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
  if (body.id !== state.sessionId) {
    state.hasExperimentStateBoard = false;
  }
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

function configPreflightPayload() {
  return {
    baseline_config: el("baselineConfig").value,
    variant_config: el("variantConfig").value,
  };
}

function configPatchPayload() {
  const payload = {
    source_config: el("sourcePatchConfig").value,
    option: el("patchOption").value,
    value: el("patchValue").value,
  };
  if (el("patchedConfigPath").value.trim()) {
    payload.output_config = el("patchedConfigPath").value.trim();
  }
  return payload;
}

function visualObservationPayload() {
  return {
    label: el("visualObservationLabel").value,
    observation_type: el("visualObservationType").value,
    evidence_artifact: el("visualObservationArtifact").value,
    confidence: el("visualObservationConfidence").value,
    comparison_role: el("visualObservationRole").value,
    visual_view: el("visualObservationView").value,
    location: el("visualObservationLocation").value,
    movement: el("visualObservationMovement").value,
    link_or_lane: el("visualObservationLinkLane").value,
    visual_anchor: el("visualObservationAnchor").value,
    note: el("visualObservationNote").value,
  };
}

function agentFeedbackPayload() {
  return {
    label: el("agentFeedbackLabel").value,
    source_agent: el("agentFeedbackSource").value,
    prompt_artifact: el("agentFeedbackPromptArtifact").value,
    response_text: el("agentFeedbackText").value,
    recommended_action: el("agentFeedbackAction").value,
    claim_boundary: el("agentFeedbackBoundary").value,
  };
}

function agentActionOutcomePayload() {
  return {
    label: el("agentActionOutcomeLabel").value,
    action_plan_artifact: el("agentActionOutcomePlanArtifact").value,
    action: el("agentActionOutcomeAction").value,
    outcome_status: el("agentActionOutcomeStatus").value,
    evidence_artifact: el("agentActionOutcomeEvidence").value,
    note: el("agentActionOutcomeNote").value,
  };
}

async function loadVisualObservationTaxonomy() {
  const body = await api("/api/visual-observation/taxonomy");
  visualObservationTaxonomy.clear();
  const selector = el("visualObservationTaxonomy");
  selector.replaceChildren();
  selector.append(new Option("custom", ""));
  for (const item of body.taxonomy || []) {
    visualObservationTaxonomy.set(item.id, item);
    selector.append(new Option(item.label, item.id));
  }
  if (body.taxonomy && body.taxonomy.length) {
    selector.value = body.taxonomy[0].id;
    applyVisualObservationTaxonomy();
  }
  return body;
}

function applyVisualObservationTaxonomy() {
  const item = visualObservationTaxonomy.get(el("visualObservationTaxonomy").value);
  if (!item) {
    el("visualObservationGuidePreview").textContent = "Select an observation type to see evidence checks.";
    return;
  }
  el("visualObservationType").value = item.id;
  el("visualObservationArtifact").value = (item.evidence_targets || [])[0] || "visual-diff.md";
  el("visualObservationNote").placeholder = item.note_prompt || "What did you see in the SUMO GUI or visual diff matrix?";
  el("visualObservationGuidePreview").textContent = [
    `${item.label} (${item.id})`,
    item.description,
    "",
    "Evidence to check:",
    formatList(item.evidence_targets || []),
    "",
    "Suggested checks:",
    formatList(item.evidence_checks || []),
    "",
    "Suggested next actions:",
    formatList(item.next_actions || []),
    "",
    "Claim boundary:",
    item.claim_boundary,
  ].join("\n");
}

function syncConfigPatchFieldsFromScenario() {
  const sourceConfig = el("sourcePatchConfig").value.trim() || el("baselineConfig").value.trim();
  if (sourceConfig) {
    el("sourcePatchConfig").value = sourceConfig;
  }
  el("patchOption").value = el("scenarioParameter").value;
  el("patchValue").value = el("scenarioAfter").value;
}

function scenarioPatchPayload() {
  syncConfigPatchFieldsFromScenario();
  return configPatchPayload();
}

function renderConfigPreflight(body) {
  const lines = [
    `status: ${body.status}`,
    "",
    "paired_warnings:",
    ...(body.paired_warnings || []).map((warning) => `- ${warning}`),
    ...(body.paired_warnings || []).length ? "" : "- none",
    "",
    sectionForConfig(body.baseline),
    "",
    sectionForConfig(body.variant),
  ];
  el("configPreflightOutput").textContent = lines.join("\n");
  autofillOutputPaths(body);
}

function renderConfigPatch(body) {
  el("configPatchOutput").textContent = [
    `status: ${body.status}`,
    `claim_status: ${body.claim_status}`,
    `source_config: ${body.source_config}`,
    `output_config: ${body.output_config}`,
    `option: ${body.option}`,
    `old_value: ${body.old_value}`,
    `new_value: ${body.new_value}`,
    `attribute: ${body.attribute}`,
    `match_count: ${body.match_count}`,
    "",
    "warnings:",
    formatList(body.warnings || []),
    "",
    "This is a config copy only. Run config preflight and paired SUMO evidence before interpreting results.",
  ].join("\n");
  if (!el("variantConfig").value.trim()) {
    el("variantConfig").value = body.output_config;
  }
}

async function preflightPatchedScenarioConfig(patchReport) {
  if (!el("baselineConfig").value.trim()) {
    el("baselineConfig").value = patchReport.source_config;
  }
  el("variantConfig").value = patchReport.output_config;
  const body = await api("/api/config/preflight", {
    method: "POST",
    body: JSON.stringify(configPreflightPayload()),
  });
  renderConfigPreflight(body);
  return body;
}

function autofillOutputPaths(body) {
  setOutputPath("baselineSummary", findOutputPath(body.baseline, "summary-output"));
  setOutputPath("baselineTripinfo", findOutputPath(body.baseline, "tripinfo-output"));
  setOutputPath("variantSummary", findOutputPath(body.variant, "summary-output"));
  setOutputPath("variantTripinfo", findOutputPath(body.variant, "tripinfo-output"));
}

function findOutputPath(report, option) {
  const match = (report.references || []).find((item) => item.kind === "output" && item.option === option);
  return match ? match.resolved_path : "";
}

function setOutputPath(id, value) {
  if (value && !el(id).value.trim()) {
    el(id).value = value;
  }
}

function fillOutputPath(id, value) {
  el(id).value = value || "";
}

function applyMinimalDemo(body) {
  el("sessionName").value = "minimal-paired-demo";
  el("baselineConfig").value = body.baseline_config;
  el("variantConfig").value = body.variant_config;
  fillOutputPath("baselineSummary", body.baseline_summary);
  fillOutputPath("baselineTripinfo", body.baseline_tripinfo);
  fillOutputPath("variantSummary", body.variant_summary);
  fillOutputPath("variantTripinfo", body.variant_tripinfo);
  el("configPreflightOutput").textContent = [
    "Minimal demo paths loaded.",
    "",
    "Next:",
    "1. Run Check Config Pair.",
    "2. Run the headless SUMO commands or create a paired GUI session.",
    "3. Inspect Outputs after summary/tripinfo files exist.",
    "",
    ...(body.headless_commands || []),
  ].join("\n");
}

function renderScenarioTemplates(body) {
  scenarioTemplates.clear();
  const select = el("scenarioTemplate");
  select.replaceChildren();

  const customOption = document.createElement("option");
  customOption.value = "";
  customOption.textContent = "custom";
  select.append(customOption);

  for (const template of body.templates || []) {
    scenarioTemplates.set(template.id, template);
    const option = document.createElement("option");
    option.value = template.id;
    option.textContent = template.label;
    select.append(option);
  }
}

async function loadScenarioTemplates() {
  const body = await api("/api/scenario/templates");
  renderScenarioTemplates(body);
  log("Loaded scenario templates", { count: (body.templates || []).length });
}

function applyScenarioTemplate(template) {
  el("scenarioLabel").value = template.label;
  el("scenarioParameter").value = template.parameter;
  el("scenarioBefore").value = template.before_value;
  el("scenarioAfter").value = template.after_value;
  el("scenarioHypothesis").value = template.hypothesis;
  el("scenarioMetrics").value = (template.expected_metrics || []).join(", ");
  el("scenarioNote").value = template.note || "";
  syncChangeFieldsFromScenario();
  syncConfigPatchFieldsFromScenario();
  el("scenarioOutput").textContent = [
    `template: ${template.label}`,
    "",
    "This template only pre-fills a scenario plan.",
    "It does not edit SUMO files, run simulations, or prove that a change was applied.",
    "",
    "Next: create a paired session, start the scenario, capture before/after evidence, and inspect outputs.",
  ].join("\n");
}

function renderHeadlessDemo(body) {
  applyMinimalDemo(body);
  renderOutputInspection(body.output_inspection);
  const commandLines = (body.commands || []).map((item) => {
    const command = Array.isArray(item.command) ? item.command.join(" ") : item.command;
    return `${item.returncode === 0 ? "PASS" : "FAIL"} ${command}`;
  });
  el("configPreflightOutput").textContent = [
    `Minimal demo headless run: ${body.status}`,
    "",
    "commands:",
    ...commandLines,
    "",
    "Output evidence has been loaded below.",
  ].join("\n");
}

function renderGuidedDemo(body) {
  applyMinimalDemo(body);
  renderOutputInspection(body.output_inspection);
  const commandLines = ((body.headless_run && body.headless_run.commands) || []).map((item) => {
    const command = Array.isArray(item.command) ? item.command.join(" ") : item.command;
    return `${item.returncode === 0 ? "PASS" : "FAIL"} ${command}`;
  });
  el("configPreflightOutput").textContent = [
    `Guided demo: ${body.status}`,
    `claim_status: ${body.claim_status}`,
    "",
    `config_preflight: ${body.config_preflight.status}`,
    `headless_run: ${body.headless_run.status}`,
    `output_inspection: ${body.output_inspection.status}`,
    "",
    "commands:",
    ...commandLines,
    "",
    "next_actions:",
    ...((body.next_actions || []).map((item) => `- ${item}`)),
  ].join("\n");
}

async function renderGuidedGuiLaunch(body) {
  applyMinimalDemo(body.guided_demo);
  renderGuidedDemo(body.guided_demo);
  renderState(body.session);
  renderOutputInspection(body.output_inspection);
  renderEvidence(body.evidence);
  await refreshWorkflow();
  el("configPreflightOutput").textContent += [
    "",
    "paired_gui_session:",
    `- ${body.session.id}`,
    "- output inspection persisted into session evidence",
  ].join("\n");
}

function renderFullWorkflowLaunch(body) {
  renderGuidedDemo(body.guided_demo);
  renderState(body.session);
  renderOutputInspection(body.output_inspection);
  renderEvidence(body.evidence);
  renderVisualDiff(body.visual_diff.visual_diff);
  renderWorkflow(body.workflow);
  el("visualDiffMarkdown").textContent = body.visual_diff.visual_diff_markdown;
  el("metricComparisonPreview").textContent = body.metric_comparison.metric_comparison_markdown;
  renderMetricChart(body.metric_chart);
  el("packetPreview").textContent = body.packet.packet_markdown;
  el("timelinePreview").textContent = body.timeline.timeline_markdown;
  el("reviewSummaryPreview").textContent = body.review_summary.review_summary_markdown;
  el("configPreflightOutput").textContent += [
    "",
    "full_workflow_session:",
    `- ${body.session.id}`,
    "- first checkpoint captured",
    "- before/after checkpoints captured",
    "- output inspection, visual diff, metric chart, timeline, review summary, review timeline, and Codex packet exported",
    `- workflow: ${body.workflow.status}`,
  ].join("\n");
}

function outputInspectionPayload() {
  const payload = {};
  if (el("baselineSummary").value.trim()) payload.baseline_summary = el("baselineSummary").value.trim();
  if (el("baselineTripinfo").value.trim()) payload.baseline_tripinfo = el("baselineTripinfo").value.trim();
  if (el("variantSummary").value.trim()) payload.variant_summary = el("variantSummary").value.trim();
  if (el("variantTripinfo").value.trim()) payload.variant_tripinfo = el("variantTripinfo").value.trim();
  return payload;
}

function scenarioPlanPayload() {
  const metrics = el("scenarioMetrics").value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const note = el("scenarioNote").value.trim();
  return {
    label: el("scenarioLabel").value,
    parameter: el("scenarioParameter").value,
    before_value: el("scenarioBefore").value,
    after_value: el("scenarioAfter").value,
    hypothesis: el("scenarioHypothesis").value,
    expected_metrics: metrics,
    note: note || null,
  };
}

function changeRecordPayload() {
  const note = el("changeNote").value.trim();
  return {
    label: el("changeLabel").value,
    parameter: el("changeParameter").value,
    before_value: el("changeBefore").value,
    after_value: el("changeAfter").value,
    rationale: el("changeRationale").value,
    note: note || null,
  };
}

function scenarioChangeRecordPayload() {
  syncChangeFieldsFromScenario();
  return changeRecordPayload();
}

function syncChangeFieldsFromScenario() {
  el("changeLabel").value = el("scenarioLabel").value || "parameter-change";
  el("changeParameter").value = el("scenarioParameter").value;
  el("changeBefore").value = el("scenarioBefore").value;
  el("changeAfter").value = el("scenarioAfter").value;
  el("changeRationale").value = el("scenarioHypothesis").value;
  el("changeNote").value = el("scenarioNote").value;
}

function renderOutputInspection(body) {
  const lines = [
    `status: ${body.status}`,
    "",
    "paired_warnings:",
    ...(body.paired_warnings || []).map((warning) => `- ${warning}`),
    ...(body.paired_warnings || []).length ? "" : "- none",
    "",
    sectionForOutputRun(body.baseline),
    "",
    sectionForOutputRun(body.variant),
  ];
  el("outputEvidenceOutput").textContent = lines.join("\n");
}

function sectionForOutputRun(run) {
  return [
    `${run.role}: ${run.status}`,
    "warnings:",
    formatList(run.warnings),
    "",
    "summary:",
    summaryBlock(run.summary),
    "",
    "tripinfo:",
    tripinfoBlock(run.tripinfo),
  ].join("\n");
}

function summaryBlock(summary) {
  if (!summary) return "  - not provided";
  return [
    `  path: ${summary.path}`,
    `  valid_xml: ${summary.valid_xml}`,
    `  last_time: ${summary.last_time}`,
    `  loaded: ${summary.loaded}`,
    `  inserted: ${summary.inserted}`,
    `  arrived: ${summary.arrived}`,
    `  running: ${summary.running}`,
    `  waiting: ${summary.waiting}`,
    `  teleports: ${summary.teleports}`,
    `  completion_ratio: ${summary.completion_ratio}`,
  ].join("\n");
}

function tripinfoBlock(tripinfo) {
  if (!tripinfo) return "  - not provided";
  return [
    `  path: ${tripinfo.path}`,
    `  valid_xml: ${tripinfo.valid_xml}`,
    `  trip_count: ${tripinfo.trip_count}`,
    `  mean_duration: ${tripinfo.mean_duration}`,
    `  mean_waiting_time: ${tripinfo.mean_waiting_time}`,
    `  mean_time_loss: ${tripinfo.mean_time_loss}`,
  ].join("\n");
}

function formatList(items) {
  return items.length ? items.map((item) => `- ${item}`).join("\n") : "- none";
}

function sectionForConfig(report) {
  const missingInputs = report.missing_inputs.length
    ? report.missing_inputs.map((item) => `  - ${item}`).join("\n")
    : "  - none";
  const missingOutputParents = report.missing_output_parents.length
    ? report.missing_output_parents.map((item) => `  - ${item}`).join("\n")
    : "  - none";
  const declaredOutputs = report.declared_outputs.length
    ? report.declared_outputs.map((item) => `  - ${item}`).join("\n")
    : "  - none";
  const warnings = report.warnings.length
    ? report.warnings.map((item) => `  - ${item}`).join("\n")
    : "  - none";

  return [
    `${report.role}: ${report.status}`,
    `config: ${report.config_path}`,
    `valid_xml: ${report.valid_xml}`,
    "missing_inputs:",
    missingInputs,
    "missing_output_parents:",
    missingOutputParents,
    "declared_outputs:",
    declaredOutputs,
    "warnings:",
    warnings,
  ].join("\n");
}

el("preflightBtn").addEventListener("click", async () => {
  try {
    const body = await api("/api/preflight");
    log("Preflight", body);
  } catch (error) {
    log(`Preflight failed: ${error.message}`);
  }
});

el("loadDemoBtn").addEventListener("click", async () => {
  try {
    const body = await api("/api/examples/minimal-paired");
    applyMinimalDemo(body);
    log("Loaded minimal demo", body);
  } catch (error) {
    log(`Load demo failed: ${error.message}`);
  }
});

el("loadScenarioTemplateBtn").addEventListener("click", () => {
  const templateId = el("scenarioTemplate").value;
  if (!templateId) {
    log("No scenario template selected");
    return;
  }
  const template = scenarioTemplates.get(templateId);
  if (!template) {
    log("Selected scenario template is not loaded", { templateId });
    return;
  }
  applyScenarioTemplate(template);
  log("Applied scenario template", { templateId });
});

el("runDemoBtn").addEventListener("click", async () => {
  try {
    const body = await api("/api/examples/minimal-paired/run-headless", { method: "POST" });
    renderHeadlessDemo(body);
    log("Ran minimal demo headless", body);
  } catch (error) {
    log(`Run demo failed: ${error.message}`);
  }
});

el("guidedDemoBtn").addEventListener("click", async () => {
  try {
    const body = await api("/api/examples/minimal-paired/run-guided", { method: "POST" });
    renderGuidedDemo(body);
    log("Ran guided demo", body);
  } catch (error) {
    log(`Guided demo failed: ${error.message}`);
  }
});

el("launchDemoGuiBtn").addEventListener("click", async () => {
  try {
    const demo = await api("/api/examples/minimal-paired");
    applyMinimalDemo(demo);
    const body = await api("/api/examples/minimal-paired/launch-gui", { method: "POST" });
    renderState(body);
    log("Launched minimal demo GUI session", body);
  } catch (error) {
    log(`Launch demo GUI failed: ${error.message}`);
  }
});

el("launchGuidedGuiBtn").addEventListener("click", async () => {
  try {
    const body = await api("/api/examples/minimal-paired/launch-guided-gui", { method: "POST" });
    await renderGuidedGuiLaunch(body);
    log("Launched guided demo GUI session", body);
  } catch (error) {
    log(`Launch guided GUI failed: ${error.message}`);
  }
});

el("launchFullWorkflowGuiBtn").addEventListener("click", async () => {
  try {
    const body = await api("/api/examples/minimal-paired/launch-full-workflow-gui", { method: "POST" });
    renderFullWorkflowLaunch(body);
    log("Launched full workflow demo GUI session", body);
  } catch (error) {
    log(`Launch full workflow failed: ${error.message}`);
  }
});

el("configPreflightBtn").addEventListener("click", async () => {
  try {
    const body = await api("/api/config/preflight", {
      method: "POST",
      body: JSON.stringify(configPreflightPayload()),
    });
    renderConfigPreflight(body);
    log("Config preflight", body);
  } catch (error) {
    log(`Config preflight failed: ${error.message}`);
  }
});

el("createConfigPatchBtn").addEventListener("click", async () => {
  try {
    const body = await api("/api/config/patch", {
      method: "POST",
      body: JSON.stringify(configPatchPayload()),
    });
    renderConfigPatch(body);
    log("Created config patch", { output_config: body.output_config, option: body.option });
  } catch (error) {
    log(`Config patch failed: ${error.message}`);
  }
});

async function patchConfigFromScenario() {
  const body = await api("/api/config/patch", {
    method: "POST",
    body: JSON.stringify(scenarioPatchPayload()),
  });
  renderConfigPatch(body);
  const preflight = await preflightPatchedScenarioConfig(body);
  syncChangeFieldsFromScenario();
  el("scenarioOutput").textContent = [
    "config_patch: generated",
    `config_preflight: ${preflight.status}`,
    `source_config: ${body.source_config}`,
    `output_config: ${body.output_config}`,
    `option: ${body.option}`,
    `old_value: ${body.old_value}`,
    `new_value: ${body.new_value}`,
    "",
    "Next: create a paired session, start the scenario, and record the structured change.",
  ].join("\n");
  return { patch: body, preflight };
}

el("patchFromScenarioBtn").addEventListener("click", async () => {
  try {
    const body = await patchConfigFromScenario();
    log("Patched and preflighted config from scenario", {
      output_config: body.patch.output_config,
      option: body.patch.option,
      preflight_status: body.preflight.status,
    });
  } catch (error) {
    log(`Scenario config patch failed: ${error.message}`);
  }
});

el("inspectOutputsBtn").addEventListener("click", async () => {
  try {
    const path = state.sessionId ? `/api/session/${state.sessionId}/outputs/inspect` : "/api/outputs/inspect";
    const body = await api(path, {
      method: "POST",
      body: JSON.stringify(outputInspectionPayload()),
    });
    renderOutputInspection(body);
    if (state.sessionId) {
      await loadEvidence();
      await refreshWorkflow();
    }
    log("Output inspection", body);
  } catch (error) {
    log(`Output inspection failed: ${error.message}`);
  }
});

el("createBtn").addEventListener("click", async () => {
  try {
    const body = await api("/api/session/create", {
      method: "POST",
      body: JSON.stringify(sessionPayload()),
    });
    renderState(body);
    await refreshWorkflow();
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

el("firstCheckpointBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/checkpoint/first`, { method: "POST" });
    renderEvidence(body.evidence);
    await refreshWorkflow();
    log("Captured first checkpoint", body.screenshot);
  } catch (error) {
    log(`First checkpoint failed: ${error.message}`);
  }
});

el("templateCheckpointBtn").addEventListener("click", async () => {
  try {
    const note = el("checkpointNote").value.trim();
    const body = await api(`/api/session/${state.sessionId}/checkpoint/template`, {
      method: "POST",
      body: JSON.stringify({
        template: el("checkpointTemplate").value,
        note: note || null,
      }),
    });
    renderEvidence(body.evidence);
    await refreshWorkflow();
    log("Captured template checkpoint", body.screenshot);
  } catch (error) {
    log(`Template checkpoint failed: ${error.message}`);
  }
});

el("addTimelineNoteBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/timeline/note`, {
      method: "POST",
      body: JSON.stringify({
        label: el("timelineNoteLabel").value,
        note: el("timelineNoteText").value,
      }),
    });
    renderEvidence(body.evidence);
    const timeline = await exportTimelineWithPreset();
    renderEvidence(timeline.evidence);
    el("timelinePreview").textContent = timeline.timeline_markdown;
    await refreshWorkflow();
    log("Added timeline note", body.note);
  } catch (error) {
    log(`Timeline note failed: ${error.message}`);
  }
});

el("recordChangeBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/change/record`, {
      method: "POST",
      body: JSON.stringify(changeRecordPayload()),
    });
    renderEvidence(body.evidence);
    const timeline = await exportTimelineWithPreset();
    renderEvidence(timeline.evidence);
    el("timelinePreview").textContent = timeline.timeline_markdown;
    await refreshWorkflow();
    log("Recorded structured change", body.change);
  } catch (error) {
    log(`Change record failed: ${error.message}`);
  }
});

async function recordScenarioChange() {
  const body = await api(`/api/session/${state.sessionId}/change/record`, {
    method: "POST",
    body: JSON.stringify(scenarioChangeRecordPayload()),
  });
  renderEvidence(body.evidence);
  const timeline = await exportTimelineWithPreset();
  renderEvidence(timeline.evidence);
  el("timelinePreview").textContent = timeline.timeline_markdown;
  await refreshWorkflow();
  await refreshScenario();
  el("scenarioOutput").textContent += [
    "",
    "change_record: recorded",
    `change_label: ${body.change.label}`,
    `parameter: ${body.change.parameter}`,
  ].join("\n");
  return body;
}

el("recordScenarioChangeBtn").addEventListener("click", async () => {
  try {
    const body = await recordScenarioChange();
    log("Recorded scenario change", body.change);
  } catch (error) {
    log(`Scenario change record failed: ${error.message}`);
  }
});

el("startScenarioBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/scenario/plan`, {
      method: "POST",
      body: JSON.stringify(scenarioPlanPayload()),
    });
    syncChangeFieldsFromScenario();
    renderEvidence(body.evidence);
    renderScenarioStatus(body.scenario_status);
    log("Started guided scenario", { scenario_plan_markdown_path: body.scenario_plan_markdown_path });
  } catch (error) {
    log(`Scenario start failed: ${error.message}`);
  }
});

el("scenarioStatusBtn").addEventListener("click", async () => {
  try {
    await refreshScenario();
  } catch (error) {
    log(`Scenario refresh failed: ${error.message}`);
  }
});

async function refreshState() {
  const body = await api(`/api/session/${state.sessionId}/state`);
  renderState(body);
  log("Refreshed state", body);
}

async function refreshWorkflow() {
  const body = await api(`/api/session/${state.sessionId}/workflow/status`);
  renderWorkflow(body);
  log("Refreshed workflow", { status: body.status, claim_status: body.claim_status });
}

async function refreshScenario() {
  const body = await api(`/api/session/${state.sessionId}/scenario/status`);
  renderScenarioStatus(body);
  log("Refreshed scenario", { status: body.status, current_step: body.current_step });
}

async function loadEvidence() {
  const body = await api(`/api/session/${state.sessionId}/evidence`);
  renderEvidence(body);
  log("Loaded evidence", { session_dir: body.session_dir });
}

function renderWorkflow(body) {
  const checklist = (body.checklist || [])
    .map((item) => `${item.status.toUpperCase()} ${item.label}\n  evidence: ${item.evidence}`)
    .join("\n");
  const actions = (body.next_actions || []).map((item) => `- ${item}`).join("\n");
  el("workflowOutput").textContent = [
    `status: ${body.status}`,
    `claim_status: ${body.claim_status}`,
    "",
    "checklist:",
    checklist || "- none",
    "",
    "next_actions:",
    actions || "- none",
  ].join("\n");
}

function renderComparisonReadiness(body) {
  const checklist = (body.checklist || [])
    .map((item) => `${item.status.toUpperCase()} ${item.label}\n  evidence: ${item.evidence}`)
    .join("\n");
  const actions = (body.next_actions || []).map((item) => `- ${item}`).join("\n");
  el("compareReadinessOutput").textContent = [
    `status: ${body.status}`,
    `claim_status: ${body.claim_status}`,
    "",
    "checklist:",
    checklist || "- none",
    "",
    "next_actions:",
    actions || "- none",
    "",
    `claim_boundary: ${body.claim_boundary}`,
  ].join("\n");
}

function renderScenarioStatus(body) {
  const checklist = (body.checklist || [])
    .map((item) => `${item.status.toUpperCase()} ${item.label}\n  evidence: ${item.evidence}`)
    .join("\n");
  const actions = (body.next_actions || []).map((item) => `- ${item}`).join("\n");
  el("scenarioOutput").textContent = [
    `status: ${body.status}`,
    `current_step: ${body.current_step}`,
    "",
    "checklist:",
    checklist || "- none",
    "",
    "next_actions:",
    actions || "- none",
  ].join("\n");
}

function renderEvidence(body) {
  el("sessionDir").textContent = body.session_dir;
  const artifacts = (body.artifacts || [])
    .map((item) => `${item.relative_path}  (${item.size_bytes} bytes)`)
    .join("\n");
  el("artifactList").textContent = artifacts || "No artifacts found.";
  renderScreenshotPreview(body.artifacts || []);
  el("evidencePreview").textContent = body.comparison_markdown;
}

function artifactUrl(relativePath) {
  return `/api/session/${state.sessionId}/artifact/${relativePath.split("/").map(encodeURIComponent).join("/")}`;
}

function renderScreenshotPreview(artifacts) {
  const screenshots = artifacts.filter((item) => item.relative_path.toLowerCase().endsWith(".png"));
  const container = el("screenshotPreview");
  container.replaceChildren();
  if (!screenshots.length) {
    container.textContent = "No screenshots loaded.";
    return;
  }
  for (const item of screenshots) {
    const link = document.createElement("a");
    link.href = artifactUrl(item.relative_path);
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.className = "screenshot-card";

    const image = document.createElement("img");
    image.src = link.href;
    image.alt = item.relative_path;
    image.loading = "lazy";

    const label = document.createElement("span");
    label.textContent = item.relative_path;

    link.append(image, label);
    container.append(link);
  }
}

el("stateBtn").addEventListener("click", async () => {
  try {
    await refreshState();
  } catch (error) {
    log(`State refresh failed: ${error.message}`);
  }
});

el("workflowBtn").addEventListener("click", async () => {
  try {
    await refreshWorkflow();
  } catch (error) {
    log(`Workflow refresh failed: ${error.message}`);
  }
});

el("compareReadinessBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/comparison/readiness`);
    renderComparisonReadiness(body);
    log("Checked comparison readiness", { status: body.status, claim_status: body.claim_status });
  } catch (error) {
    log(`Comparison readiness failed: ${error.message}`);
  }
});

el("exportExperimentStateBoardBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/experiment-state-board/export`, { method: "POST" });
    renderExperimentStateBoard(body);
    await refreshWorkflow();
    log("Exported experiment state board", {
      experiment_state_board_markdown_path: body.experiment_state_board_markdown_path,
    });
  } catch (error) {
    log(`Experiment state board export failed: ${error.message}`);
  }
});

el("enableLiveExperimentStateBoardBtn").addEventListener("click", async () => {
  try {
    await enableLiveExperimentStateBoard();
  } catch (error) {
    log(`Live experiment state board failed: ${error.message}`);
  }
});

async function enableLiveExperimentStateBoard() {
  const body = await api(`/api/session/${state.sessionId}/experiment-state-board/export`, { method: "POST" });
  renderExperimentStateBoard(body);
  await refreshWorkflow();
  log("Live experiment state board enabled", {
    experiment_state_board_markdown_path: body.experiment_state_board_markdown_path,
  });
  return body;
}

async function refreshExperimentStateBoardIfAvailable(reason) {
  if (!state.sessionId || !state.hasExperimentStateBoard) {
    return null;
  }
  try {
    const body = await api(`/api/session/${state.sessionId}/experiment-state-board/export`, { method: "POST" });
    renderExperimentStateBoard(body);
    log("Refreshed experiment state board", {
      reason,
      experiment_state_board_markdown_path: body.experiment_state_board_markdown_path,
    });
    return body;
  } catch (error) {
    log(`Experiment state board refresh skipped: ${error.message}`);
    return null;
  }
}

function renderExperimentStateBoard(body) {
  state.hasExperimentStateBoard = true;
  renderEvidence(body.evidence);
  renderExperimentStateBoardCards(body.experiment_state_board);
  el("experimentStateBoardPreview").textContent =
    body.experiment_state_board_markdown || "No experiment state board exported.";
}

function renderExperimentStateBoardCards(board) {
  const container = el("experimentStateBoardCards");
  container.replaceChildren();
  if (!board) {
    container.textContent = "No experiment state board exported.";
    return;
  }

  const summary = document.createElement("section");
  summary.className = `state-board-summary status-${statusClass(board.status)}`;

  const heading = document.createElement("h4");
  heading.textContent = board.status || "unknown";

  const focus = document.createElement("p");
  focus.textContent = board.primary_focus || "No primary focus recorded.";

  const meta = document.createElement("div");
  meta.className = "state-board-meta";
  meta.append(
    makeStateBoardTag("Readiness", board.readiness_status),
    makeStateBoardTag("Workflow", board.workflow_status),
    makeStateBoardTag("Claim", board.claim_status),
  );

  summary.append(heading, focus, meta);
  container.append(summary);

  const laneGrid = document.createElement("div");
  laneGrid.className = "state-board-lanes";
  for (const lane of board.lanes || []) {
    laneGrid.append(renderExperimentStateBoardLane(lane));
  }
  container.append(laneGrid);
}

function renderExperimentStateBoardLane(lane) {
  const card = document.createElement("article");
  card.className = `state-board-lane status-${statusClass(lane.status)}`;

  const titleRow = document.createElement("div");
  titleRow.className = "state-board-lane-title";

  const title = document.createElement("h4");
  title.textContent = lane.label || lane.id || "Lane";

  const status = document.createElement("span");
  status.textContent = lane.status || "unknown";

  titleRow.append(title, status);

  const summary = document.createElement("p");
  summary.textContent = lane.summary || "No summary recorded.";

  const artifactList = document.createElement("div");
  artifactList.className = "state-board-artifacts";
  const artifacts = lane.artifacts || [];
  if (!artifacts.length) {
    const empty = document.createElement("span");
    empty.textContent = "No artifacts yet";
    artifactList.append(empty);
  } else {
    for (const artifact of artifacts) {
      artifactList.append(makeArtifactLink(artifact));
    }
  }

  card.append(titleRow, summary);
  card.append(renderExperimentStateBoardLanePreview(lane.preview));
  card.append(artifactList);
  return card;
}

function renderExperimentStateBoardLanePreview(preview) {
  const panel = document.createElement("div");
  panel.className = "state-board-preview";
  if (!preview || !preview.kind) {
    panel.textContent = "No structured preview yet.";
    return panel;
  }
  if (preview.kind === "visual_diff") {
    return renderVisualDiffLanePreview(preview);
  }
  if (preview.kind === "metric_highlights") {
    return renderMetricLanePreview(preview);
  }
  if (preview.kind === "agent_loop") {
    return renderAgentLoopLanePreview(preview);
  }
  if (preview.kind === "claim_gate") {
    return renderClaimGateLanePreview(preview);
  }
  panel.textContent = `${preview.kind}: preview not supported.`;
  return panel;
}

function renderVisualDiffLanePreview(preview) {
  const panel = document.createElement("div");
  panel.className = "state-board-preview";
  panel.append(makeStateBoardPreviewRow("Pairs", preview.pair_count ?? 0));
  const firstPair = preview.first_pair;
  if (!firstPair) {
    panel.append(makeStateBoardPreviewRow("First pair", "not available"));
    return panel;
  }
  panel.append(
    makeStateBoardPreviewRow("Templates", `${firstPair.before_template || "before"} -> ${firstPair.after_template || "after"}`),
    makeStateBoardPreviewRow("Pixel diff", firstPair.pixel_status || "unknown"),
  );
  const thumbGrid = renderStateBoardVisualThumbGrid(firstPair.matrix || []);
  if (thumbGrid) {
    panel.append(thumbGrid);
  }
  for (const row of firstPair.matrix || []) {
    const ratio = formatPixelRatio(row) || "ratio n/a";
    panel.append(makeStateBoardPreviewRow(row.label || row.role || "Run", ratio));
  }
  return panel;
}

function renderMetricLanePreview(preview) {
  const panel = document.createElement("div");
  panel.className = "state-board-preview";
  const metrics = preview.metrics || [];
  if (!metrics.length) {
    panel.textContent = "No metric highlights yet.";
    return panel;
  }
  const chartPreview = renderStateBoardMetricChartPreview(preview.chart_artifact);
  if (chartPreview) {
    panel.append(chartPreview);
  }
  for (const row of metrics) {
    const label = row.label || row.metric;
    const value = `${formatMetricValue(row.baseline)} -> ${formatMetricValue(row.variant)} (${formatMetricDelta(row.delta)})`;
    panel.append(makeStateBoardPreviewRow(label, value));
  }
  return panel;
}

function renderStateBoardVisualThumbGrid(rows) {
  const usableRows = rows.filter((row) => row.before || row.after || row.pixel_diff);
  if (!usableRows.length) {
    return null;
  }
  const grid = document.createElement("div");
  grid.className = "state-board-thumb-grid";
  for (const row of usableRows) {
    for (const [label, path] of [["Before", row.before], ["After", row.after], ["Diff", row.pixel_diff]]) {
      const tile = document.createElement("a");
      tile.className = "state-board-thumb";
      if (path) {
        tile.href = artifactUrl(path);
        tile.target = "_blank";
        tile.rel = "noopener noreferrer";
      } else {
        tile.classList.add("is-missing");
      }

      if (path) {
        const image = document.createElement("img");
        image.src = tile.href;
        image.alt = `${row.label || row.role || "Run"} ${label}`;
        image.loading = "lazy";
        tile.append(image);
      } else {
        const placeholder = document.createElement("strong");
        placeholder.textContent = "n/a";
        tile.append(placeholder);
      }

      const caption = document.createElement("span");
      caption.textContent = `${row.label || row.role || "Run"} ${label}`;

      tile.append(caption);
      grid.append(tile);
    }
  }
  return grid;
}

function renderStateBoardMetricChartPreview(chartArtifact) {
  if (!chartArtifact) {
    return null;
  }
  const link = document.createElement("a");
  link.className = "state-board-chart";
  link.href = artifactUrl(chartArtifact);
  link.target = "_blank";
  link.rel = "noopener noreferrer";

  const image = document.createElement("img");
  image.src = link.href;
  image.alt = "Metric delta chart";
  image.loading = "lazy";

  const caption = document.createElement("span");
  caption.textContent = chartArtifact;

  link.append(image, caption);
  return link;
}

function renderAgentLoopLanePreview(preview) {
  const panel = document.createElement("div");
  panel.className = "state-board-preview";
  panel.append(makeStateBoardPreviewRow("Loop", preview.status || "missing"));
  for (const step of preview.steps || []) {
    panel.append(makeStateBoardPreviewRow(step.label || step.id, step.status || "unknown"));
  }
  if (preview.next_step) {
    panel.append(makeStateBoardPreviewRow("Next", preview.next_step));
  }
  return panel;
}

function renderClaimGateLanePreview(preview) {
  const panel = document.createElement("div");
  panel.className = "state-board-preview";
  panel.append(
    makeStateBoardPreviewRow("Readiness", preview.readiness_status || "unknown"),
    makeStateBoardPreviewRow("Workflow", preview.workflow_status || "unknown"),
    makeStateBoardPreviewRow("Claim", preview.claim_status || preview.workflow_claim_status || "unknown"),
  );
  return panel;
}

function makeStateBoardPreviewRow(label, value) {
  const row = document.createElement("div");
  row.className = "state-board-preview-row";

  const labelNode = document.createElement("span");
  labelNode.textContent = label || "Item";

  const valueNode = document.createElement("strong");
  valueNode.textContent = value === null || value === undefined || value === "" ? "n/a" : String(value);

  row.append(labelNode, valueNode);
  return row;
}

function formatMetricValue(value) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return String(value);
}

function formatMetricDelta(value) {
  if (value === null || value === undefined) {
    return "delta n/a";
  }
  const prefix = typeof value === "number" && value > 0 ? "+" : "";
  return `delta ${prefix}${value}`;
}

function makeStateBoardTag(label, value) {
  const tag = document.createElement("span");
  tag.textContent = `${label}: ${value || "unknown"}`;
  return tag;
}

function makeArtifactLink(relativePath) {
  const link = document.createElement("a");
  link.href = artifactUrl(relativePath);
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = relativePath;
  return link;
}

function statusClass(value) {
  return String(value || "unknown").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "unknown";
}

el("evidenceBtn").addEventListener("click", async () => {
  try {
    await loadEvidence();
  } catch (error) {
    log(`Evidence load failed: ${error.message}`);
  }
});

el("exportPacketBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/packet/export`, { method: "POST" });
    renderEvidence(body.evidence);
    el("packetPreview").textContent = body.packet_markdown;
    await refreshWorkflow();
    log("Exported Codex packet", { packet_path: body.packet_path });
  } catch (error) {
    log(`Packet export failed: ${error.message}`);
  }
});

el("exportAgentPromptBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/agent-review-prompt/export`, { method: "POST" });
    renderAgentReviewPrompt(body);
    await refreshWorkflow();
    log("Exported agent review prompt", { agent_prompt_markdown_path: body.agent_prompt_markdown_path });
  } catch (error) {
    log(`Agent prompt export failed: ${error.message}`);
  }
});

function renderAgentReviewPrompt(body) {
  renderEvidence(body.evidence);
  el("agentPromptPreview").textContent = body.agent_prompt_markdown || "No agent prompt exported.";
}

el("recordAgentFeedbackBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/agent-feedback/record`, {
      method: "POST",
      body: JSON.stringify(agentFeedbackPayload()),
    });
    renderAgentFeedback(body);
    await refreshWorkflow();
    log("Recorded agent feedback", {
      label: body.agent_feedback.label,
      agent_feedback_markdown_path: body.agent_feedback_markdown_path,
    });
  } catch (error) {
    log(`Agent feedback record failed: ${error.message}`);
  }
});

function renderAgentFeedback(body) {
  renderEvidence(body.evidence);
  el("agentFeedbackPreview").textContent = body.agent_feedback_markdown || "No agent feedback recorded.";
}

el("exportAgentActionPlanBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/agent-action-plan/export`, { method: "POST" });
    renderAgentActionPlan(body);
    await refreshWorkflow();
    log("Exported agent action plan", { agent_action_plan_markdown_path: body.agent_action_plan_markdown_path });
  } catch (error) {
    log(`Agent action plan export failed: ${error.message}`);
  }
});

function renderAgentActionPlan(body) {
  renderEvidence(body.evidence);
  el("agentActionPlanPreview").textContent = body.agent_action_plan_markdown || "No agent action plan exported.";
}

el("recordAgentActionOutcomeBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/agent-action-outcome/record`, {
      method: "POST",
      body: JSON.stringify(agentActionOutcomePayload()),
    });
    renderAgentActionOutcome(body);
    await refreshWorkflow();
    await refreshExperimentStateBoardIfAvailable("agent action outcome");
    log("Recorded agent action outcome", {
      label: body.agent_action_outcome.label,
      agent_action_outcome_markdown_path: body.agent_action_outcome_markdown_path,
    });
  } catch (error) {
    log(`Agent action outcome record failed: ${error.message}`);
  }
});

function renderAgentActionOutcome(body) {
  renderEvidence(body.evidence);
  el("agentActionOutcomePreview").textContent =
    body.agent_action_outcome_markdown || "No agent action outcome recorded.";
}

el("exportAgentLoopReviewBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/agent-loop-review/export`, { method: "POST" });
    renderAgentLoopReview(body);
    await refreshWorkflow();
    await refreshExperimentStateBoardIfAvailable("agent loop review");
    log("Exported agent loop review", { agent_loop_review_markdown_path: body.agent_loop_review_markdown_path });
  } catch (error) {
    log(`Agent loop review export failed: ${error.message}`);
  }
});

function renderAgentLoopReview(body) {
  renderEvidence(body.evidence);
  el("agentLoopReviewPreview").textContent =
    body.agent_loop_review_markdown || "No agent loop review exported.";
}

el("exportNextActionReviewBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/next-action-review/export`, { method: "POST" });
    renderNextActionReview(body);
    await refreshWorkflow();
    log("Exported next action review", { next_action_review_markdown_path: body.next_action_review_markdown_path });
  } catch (error) {
    log(`Next action review export failed: ${error.message}`);
  }
});

function renderNextActionReview(body) {
  renderEvidence(body.evidence);
  el("nextActionReviewPreview").textContent = body.next_action_review_markdown || "No next action review exported.";
}

el("runEvidenceLoopBtn").addEventListener("click", runGuidedEvidenceLoop);

async function runGuidedEvidenceLoop() {
  const results = [];
  results.push(await runEvidenceLoopStep("workflow status", async () => refreshWorkflow()));
  results.push(await runEvidenceLoopStep("metric comparison", async () => {
    const body = await api(`/api/session/${state.sessionId}/metrics/compare`, { method: "POST" });
    renderEvidence(body.evidence);
    el("metricComparisonPreview").textContent = body.metric_comparison_markdown;
    return { metric_comparison_markdown_path: body.metric_comparison_markdown_path };
  }));
  results.push(await runEvidenceLoopStep("metric chart", async () => {
    const body = await api(`/api/session/${state.sessionId}/metrics/chart`, { method: "POST" });
    renderEvidence(body.evidence);
    renderMetricChart(body);
    return { metric_chart_markdown_path: body.metric_chart_markdown_path };
  }));
  results.push(await runEvidenceLoopStep("visual diff", async () => {
    const body = await api(`/api/session/${state.sessionId}/visual-diff/export`, { method: "POST" });
    renderEvidence(body.evidence);
    renderVisualDiff(body.visual_diff);
    el("visualDiffMarkdown").textContent = body.visual_diff_markdown;
    return { visual_diff_markdown_path: body.visual_diff_markdown_path };
  }));
  results.push(await runEvidenceLoopStep("review timeline", async () => {
    const body = await exportTimelineWithPreset("review");
    renderEvidence(body.evidence);
    el("timelinePreview").textContent = body.timeline_markdown;
    return { timeline_markdown_path: body.timeline_markdown_path };
  }));
  results.push(await runEvidenceLoopStep("review summary", async () => {
    const body = await api(`/api/session/${state.sessionId}/review/summary`, { method: "POST" });
    renderEvidence(body.evidence);
    el("reviewSummaryPreview").textContent = body.review_summary_markdown;
    return { review_summary_markdown_path: body.review_summary_markdown_path };
  }));
  results.push(await runEvidenceLoopStep("agent prompt", async () => {
    const body = await api(`/api/session/${state.sessionId}/agent-review-prompt/export`, { method: "POST" });
    renderAgentReviewPrompt(body);
    return { agent_prompt_markdown_path: body.agent_prompt_markdown_path };
  }));
  results.push(await runEvidenceLoopStep("live state board", async () => enableLiveExperimentStateBoard()));
  await refreshWorkflow();
  log("Guided evidence loop finished", { results });
}

async function runEvidenceLoopStep(label, action) {
  try {
    const output = await action();
    return { label, status: "pass", output: output || {} };
  } catch (error) {
    log(`Evidence loop step failed: ${label}`, { error: error.message });
    return { label, status: "failed", error: error.message };
  }
}

el("exportTimelineBtn").addEventListener("click", async () => {
  try {
    const body = await exportTimelineWithPreset();
    renderEvidence(body.evidence);
    el("timelinePreview").textContent = body.timeline_markdown;
    await refreshWorkflow();
    log("Exported run timeline", { timeline_markdown_path: body.timeline_markdown_path });
  } catch (error) {
    log(`Timeline export failed: ${error.message}`);
  }
});

el("compareMetricsBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/metrics/compare`, { method: "POST" });
    renderEvidence(body.evidence);
    el("metricComparisonPreview").textContent = body.metric_comparison_markdown;
    await refreshWorkflow();
    await refreshExperimentStateBoardIfAvailable("metric comparison");
    log("Exported metric comparison", { metric_comparison_markdown_path: body.metric_comparison_markdown_path });
  } catch (error) {
    log(`Metric comparison failed: ${error.message}`);
  }
});

el("exportMetricChartBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/metrics/chart`, { method: "POST" });
    renderEvidence(body.evidence);
    renderMetricChart(body);
    await refreshWorkflow();
    await refreshExperimentStateBoardIfAvailable("metric chart");
    log("Exported metric chart", { metric_chart_markdown_path: body.metric_chart_markdown_path });
  } catch (error) {
    log(`Metric chart export failed: ${error.message}`);
  }
});

el("exportReviewSummaryBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/review/summary`, { method: "POST" });
    renderEvidence(body.evidence);
    el("reviewSummaryPreview").textContent = body.review_summary_markdown;
    await refreshWorkflow();
    log("Exported review summary", { review_summary_markdown_path: body.review_summary_markdown_path });
  } catch (error) {
    log(`Review summary export failed: ${error.message}`);
  }
});

async function exportTimelineWithPreset(forcedPreset = null) {
  const preset = encodeURIComponent(forcedPreset || el("timelinePreset").value || "full");
  return api(`/api/session/${state.sessionId}/timeline/export?preset=${preset}`, { method: "POST" });
}

function renderMetricChart(body) {
  const container = el("metricChartPreview");
  container.replaceChildren();
  if (body.metric_chart_svg) {
    container.innerHTML = body.metric_chart_svg;
  } else {
    container.textContent = "No metric chart exported.";
  }
  el("metricChartMarkdown").textContent = body.metric_chart_markdown || "No metric chart exported.";
}

el("exportVisualDiffBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/visual-diff/export`, { method: "POST" });
    renderEvidence(body.evidence);
    renderVisualDiff(body.visual_diff);
    el("visualDiffMarkdown").textContent = body.visual_diff_markdown;
    await refreshWorkflow();
    await refreshExperimentStateBoardIfAvailable("visual diff");
    log("Exported visual diff", { visual_diff_markdown_path: body.visual_diff_markdown_path });
  } catch (error) {
    log(`Visual diff export failed: ${error.message}`);
  }
});

el("recordVisualObservationBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/visual-observation/record`, {
      method: "POST",
      body: JSON.stringify(visualObservationPayload()),
    });
    renderVisualObservation(body);
    const timeline = await exportTimelineWithPreset();
    renderEvidence(timeline.evidence);
    el("timelinePreview").textContent = timeline.timeline_markdown;
    await refreshWorkflow();
    log("Recorded visual observation", body.observation);
  } catch (error) {
    log(`Visual observation failed: ${error.message}`);
  }
});

el("recordGuidedVisualObservationBtn").addEventListener("click", async () => {
  try {
    const body = await api(`/api/session/${state.sessionId}/visual-observation/guided-record`, {
      method: "POST",
      body: JSON.stringify(visualObservationPayload()),
    });
    renderGuidedVisualObservation(body);
    await refreshWorkflow();
    await refreshExperimentStateBoardIfAvailable("guided visual observation");
    log("Recorded guided visual observation", {
      label: body.observation.label,
      timeline_markdown_path: body.timeline_markdown_path,
      next_action_review_markdown_path: body.next_action_review_markdown_path,
    });
  } catch (error) {
    log(`Guided visual observation failed: ${error.message}`);
  }
});

el("loadVisualObservationTaxonomyBtn").addEventListener("click", async () => {
  try {
    const body = await loadVisualObservationTaxonomy();
    log("Loaded visual observation taxonomy", { count: (body.taxonomy || []).length });
  } catch (error) {
    log(`Visual observation taxonomy load failed: ${error.message}`);
  }
});

el("visualObservationTaxonomy").addEventListener("change", applyVisualObservationTaxonomy);

function renderVisualObservation(body) {
  renderEvidence(body.evidence);
  const observation = body.observation;
  el("visualObservationPreview").textContent = [
    `label: ${observation.label}`,
    `type: ${observation.observation_type}`,
    `confidence: ${observation.confidence}`,
    `simulation_time: ${observation.simulation_time}`,
    `evidence_artifact: ${observation.evidence_artifact || "not specified"}`,
    `role: ${observation.comparison_role || "not specified"}`,
    `view: ${observation.visual_view || "not specified"}`,
    `location: ${observation.location || "not specified"}`,
    `movement: ${observation.movement || "not specified"}`,
    `link_or_lane: ${observation.link_or_lane || "not specified"}`,
    `visual_anchor: ${observation.visual_anchor || "not specified"}`,
    "",
    observation.note,
  ].join("\n");
}

function renderGuidedVisualObservation(body) {
  renderVisualObservation(body);
  renderEvidence(body.evidence);
  el("timelinePreview").textContent = body.timeline_markdown || "No visual timeline exported.";
  el("nextActionReviewPreview").textContent = body.next_action_review_markdown || "No next action review exported.";
  el("agentPromptPreview").textContent = body.agent_prompt_markdown || "No agent prompt exported.";
}

function renderVisualDiff(visualDiff) {
  const container = el("visualDiffPreview");
  container.replaceChildren();
  const pairs = visualDiff.pairs || [];
  if (!pairs.length) {
    container.textContent = (visualDiff.warnings || []).join("\n") || "No before/after visual pairs found.";
    return;
  }
  for (const pair of pairs) {
    const article = document.createElement("article");
    article.className = "visual-diff-pair";

    const title = document.createElement("h4");
    title.textContent = `Pair ${pair.index} (${pair.pixel_diff ? pair.pixel_diff.status : "index-only"})`;
    article.append(title);

    article.append(renderVisualDiffMatrix(pair));

    container.append(article);
  }
}

function renderVisualDiffMatrix(pair) {
  const matrix = document.createElement("div");
  matrix.className = "visual-diff-matrix";

  for (const labelText of ["Run", "Before", "After", "Pixel diff"]) {
    const header = document.createElement("div");
    header.className = "visual-diff-cell visual-diff-header";
    header.textContent = labelText;
    matrix.append(header);
  }

  for (const row of visualDiffRows(pair)) {
    const role = document.createElement("div");
    role.className = "visual-diff-cell visual-diff-role";
    role.textContent = row.label || row.role;
    const ratio = formatPixelRatio(row);
    if (ratio) {
      const meta = document.createElement("span");
      meta.textContent = ratio;
      role.append(meta);
    }
    matrix.append(role);
    matrix.append(makeDiffCell("Before", row.before));
    matrix.append(makeDiffCell("After", row.after));
    matrix.append(makeDiffCell("Diff", row.pixel_diff));
  }

  return matrix;
}

function visualDiffRows(pair) {
  if (Array.isArray(pair.matrix) && pair.matrix.length) {
    return pair.matrix;
  }
  const pixelDiff = pair.pixel_diff || {};
  return [
    {
      role: "baseline",
      label: "Baseline",
      before: pair.baseline_before,
      after: pair.baseline_after,
      pixel_diff: pair.baseline_pixel_diff,
      changed_pixels: pixelDiff.baseline_changed_pixels,
      total_pixels: pixelDiff.baseline_total_pixels,
      changed_pixel_ratio: pixelRatio(pixelDiff.baseline_changed_pixels, pixelDiff.baseline_total_pixels),
    },
    {
      role: "variant",
      label: "Variant",
      before: pair.variant_before,
      after: pair.variant_after,
      pixel_diff: pair.variant_pixel_diff,
      changed_pixels: pixelDiff.variant_changed_pixels,
      total_pixels: pixelDiff.variant_total_pixels,
      changed_pixel_ratio: pixelRatio(pixelDiff.variant_changed_pixels, pixelDiff.variant_total_pixels),
    },
  ];
}

function pixelRatio(changedPixels, totalPixels) {
  if (typeof changedPixels !== "number" || typeof totalPixels !== "number" || totalPixels <= 0) {
    return null;
  }
  return changedPixels / totalPixels;
}

function formatPixelRatio(row) {
  if (typeof row.changed_pixel_ratio !== "number") {
    return "";
  }
  const changed = typeof row.changed_pixels === "number" ? row.changed_pixels : "n/a";
  const total = typeof row.total_pixels === "number" ? row.total_pixels : "n/a";
  return `${(row.changed_pixel_ratio * 100).toFixed(2)}% changed (${changed}/${total})`;
}

function makeDiffCell(labelText, relativePath) {
  const cell = document.createElement("div");
  cell.className = "visual-diff-cell";
  if (!relativePath) {
    cell.textContent = "Not available";
    return cell;
  }
  cell.append(makeDiffImage(labelText, relativePath));
  return cell;
}

function makeDiffImage(labelText, relativePath) {
  const link = document.createElement("a");
  link.href = artifactUrl(relativePath);
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.className = "screenshot-card";

  const image = document.createElement("img");
  image.src = link.href;
  image.alt = labelText;
  image.loading = "lazy";

  const label = document.createElement("span");
  label.textContent = `${labelText}: ${relativePath}`;

  link.append(image, label);
  return link;
}

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
loadScenarioTemplates().catch((error) => {
  log(`Scenario template load failed: ${error.message}`);
});
