const state = {
  sessionId: null,
  hasExperimentStateBoard: false,
  agentActionPlanFocusTarget: null,
  activeSessionChecklist: defaultActiveSessionChecklist(),
};

const scenarioTemplates = new Map();
const visualObservationTaxonomy = new Map();

const el = (id) => document.getElementById(id);
const outputPathInputIds = ["baselineSummary", "baselineTripinfo", "variantSummary", "variantTripinfo"];

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
    "refreshCockpitBtn",
    "workflowBtn",
    "compareReadinessBtn",
    "exportExperimentStateBoardBtn",
    "enableLiveExperimentStateBoardBtn",
    "checkEvidenceLoopBtn",
    "guideSourceEvidenceBtn",
    "focusSourceEvidenceBtn",
    "focusVisualComparisonBtn",
    "focusAgentActionPlanBtn",
    "applySuggestedOutputPathsBtn",
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
  if (enabled) {
    updateActiveSessionChecklist("session", "Session", "active", state.sessionId || "Session is active.");
    if (!state.agentActionPlanFocusTarget) {
      el("focusAgentActionPlanBtn").disabled = true;
    }
  } else {
    resetActiveSessionChecklist();
    state.agentActionPlanFocusTarget = null;
    renderAgentActionPlanFocus({});
  }
}

function defaultActiveSessionChecklist() {
  return {
    session: {
      label: "Session",
      status: "missing",
      detail: "Create or load a paired session.",
    },
    workflow: {
      label: "Workflow",
      status: "not checked",
      detail: "Refresh workflow status.",
    },
    compare: {
      label: "Compare",
      status: "not checked",
      detail: "Check comparison readiness.",
    },
    "evidence-loop": {
      label: "Evidence loop",
      status: "not checked",
      detail: "Check evidence loop readiness.",
    },
    "source-guide": {
      label: "Source guide",
      status: "not checked",
      detail: "Guide missing source evidence if needed.",
    },
  };
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
      await refreshEvidenceLoopStatus("output-inspection");
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

async function refreshComparisonReadiness() {
  const body = await api(`/api/session/${state.sessionId}/comparison/readiness`);
  renderComparisonReadiness(body);
  log("Checked comparison readiness", { status: body.status, claim_status: body.claim_status });
  return body;
}

async function refreshEvidenceLoopStatus(refreshTrigger = "manual-check") {
  const body = await api(`/api/session/${state.sessionId}/evidence-loop/status`);
  renderEvidenceLoopStatus(body, refreshTrigger);
  log("Checked evidence loop", {
    refresh_trigger: refreshTrigger,
    status: body.status,
    source_status: body.source_status,
    review_status: body.review_status,
  });
  await syncSourceEvidenceGuideFromEvidenceLoop(refreshTrigger);
  return body;
}

async function syncSourceEvidenceGuideFromEvidenceLoop(refreshTrigger) {
  try {
    await refreshSourceEvidenceGuide(`evidence-loop-${refreshTrigger}`);
  } catch (error) {
    log(`Source evidence guide sync failed: ${error.message}`);
  }
}

async function refreshSourceEvidenceGuide(refreshTrigger = "manual-guide") {
  const body = await api(`/api/session/${state.sessionId}/source-evidence/guide`);
  renderSourceEvidenceGuide(body, refreshTrigger);
  log("Guided source evidence", {
    refresh_trigger: refreshTrigger,
    status: body.status,
    evidence_loop_status: body.evidence_loop_status,
  });
  return body;
}

async function applySuggestedOutputPaths() {
  const body = await refreshSourceEvidenceGuide();
  const inspectStep = (body.steps || []).find((step) => step.id === "inspect_outputs");
  const { applied, skipped } = applySuggestedOutputPathsFromStep(inspectStep);
  log("Suggested output paths applied", {
    applied,
    skipped,
    manual_gate: "Suggested paths fill text inputs only. Inspect Outputs still requires a separate user action.",
  });
  renderSuggestedOutputPathStatus(applied, skipped);
  refreshOutputInspectionReadiness();
  return { applied, skipped };
}

function applySuggestedOutputPathsFromStep(step) {
  const suggestedInputs = step ? step.suggested_inputs || {} : {};
  const applied = [];
  const skipped = [];
  for (const [sourceKey, inputId] of [
    ["baseline_summary", "baselineSummary"],
    ["baseline_tripinfo", "baselineTripinfo"],
    ["variant_summary", "variantSummary"],
    ["variant_tripinfo", "variantTripinfo"],
  ]) {
    const result = setSuggestedOutputPath(sourceKey, inputId, suggestedInputs[sourceKey]);
    if (result === "applied") {
      applied.push(sourceKey);
    } else {
      skipped.push(`${sourceKey}:${result}`);
    }
  }
  renderSuggestedOutputPathStatus(applied, skipped);
  refreshOutputInspectionReadiness();
  return { applied, skipped };
}

function setSuggestedOutputPath(sourceKey, inputId, suggestion) {
  if (!suggestion || !suggestion.path) {
    return "missing";
  }
  if (el(inputId).value.trim()) {
    return "kept-existing";
  }
  el(inputId).value = suggestion.path;
  return "applied";
}

function renderSuggestedOutputPathStatus(applied, skipped) {
  el("suggestedOutputPathStatus").textContent = [
    "Suggested output path copy status",
    "",
    "applied:",
    formatList(applied),
    "",
    "skipped:",
    formatList(skipped),
    "",
    "manual_gate:",
    "- This filled text fields only.",
    "- Inspect Outputs still requires a separate user action.",
    "- Confirm the suggested files belong to the intended completed paired run.",
  ].join("\n");
}

function openSidebarDrawer(id) {
  const drawer = el(id);
  if (!drawer) {
    return null;
  }
  if (drawer.tagName.toLowerCase() === "details") {
    drawer.open = true;
  }
  drawer.scrollIntoView({ behavior: "smooth", block: "center" });
  return drawer;
}

function focusElement(id) {
  const node = el(id);
  if (!node) {
    return;
  }
  node.scrollIntoView({ behavior: "smooth", block: "center" });
  if (typeof node.focus === "function") {
    node.focus({ preventScroll: true });
  }
}

async function focusSourceEvidence() {
  const body = await refreshSourceEvidenceGuide("focus-source-evidence");
  const step = (body.steps || [])[0];
  const result = focusSourceEvidenceStep(step);
  log("Focused source evidence", {
    step_id: step ? step.id : "none",
    ui_action: step ? step.ui_action : "none",
    manual_gate: step ? step.manual_gate : "No source evidence guide step reported.",
    result,
  });
  return result;
}

function focusSourceEvidenceStep(step) {
  if (!step) {
    focusElement("sourceGuideNextStep");
    return { target: "sourceGuideNextStep", action: "no-step" };
  }
  if (step.id === "inspect_outputs") {
    openSidebarDrawer("outputEvidenceDrawer");
    const copied = applySuggestedOutputPathsFromStep(step);
    const required = step.required_inputs || [];
    const target = required.includes("baseline_summary") ? "baselineSummary" : "variantSummary";
    focusElement(target);
    return { target: "outputEvidenceDrawer", action: "inspect-output-fields", copied };
  }
  if (step.id === "capture_before_after_checkpoints") {
    openSidebarDrawer("runControlsDrawer");
    const templateInput = (step.required_inputs || []).find((item) => item.startsWith("template="));
    const template = templateInput ? templateInput.split("=", 2)[1] : "before-change";
    el("checkpointTemplate").value = template;
    focusElement("checkpointTemplate");
    return { target: "checkpointTemplate", action: "checkpoint-template", template };
  }
  if (step.id === "run_evidence_loop") {
    focusElement("runEvidenceLoopBtn");
    return { target: "runEvidenceLoopBtn", action: "run-evidence-loop" };
  }
  if (step.id === "inspect_review_package") {
    const drawer = el("evidenceArtifactsDrawer");
    if (drawer && drawer.tagName.toLowerCase() === "details") {
      drawer.open = true;
    }
    focusElement("evidenceArtifactsDrawer");
    return { target: "evidenceArtifactsDrawer", action: "review-evidence" };
  }
  focusElement("sourceGuideNextStep");
  return { target: "sourceGuideNextStep", action: step.ui_action || "unknown" };
}

function focusVisualComparison() {
  const cue = el("visualFocusCue");
  const target = cue.dataset.target || "visualReviewDrawer";
  const focus = cue.dataset.focus || "visualDiffPreview";
  if (target === "runControlsDrawer") {
    openSidebarDrawer("runControlsDrawer");
    const template = cue.dataset.template || "before-change";
    el("checkpointTemplate").value = template;
    focusElement("checkpointTemplate");
    return { target, focus: "checkpointTemplate", action: "checkpoint-template", template };
  }
  if (target === "advancedReviewActions") {
    openSidebarDrawer("advancedReviewActions");
    openSidebarDrawer("visualReviewDrawer");
    focusElement("exportVisualDiffBtn");
    return { target, focus: "exportVisualDiffBtn", action: "export-visual-diff-button" };
  }
  openSidebarDrawer("visualReviewDrawer");
  if (focus === "visualDiffPreview") {
    focusElement("visualDiffPreview");
  } else {
    focusElement(focus);
  }
  return { target: "visualReviewDrawer", focus, action: "inspect-visual-review" };
}

function renderAgentActionPlanFocus(plan) {
  const target =
    plan.ui_focus_target || (plan.recommended_action ? plan.recommended_action.ui_focus_target : null) || null;
  state.agentActionPlanFocusTarget = target;
  const cue = el("agentActionPlanFocus");
  const button = el("focusAgentActionPlanBtn");
  if (!cue || !button) return;
  const status = plan.status || (target ? "manual-action-needed" : "unknown");
  cue.className = `agent-action-plan-focus status-${status}`;
  cue.querySelector("strong").textContent = target ? target.label : "No action plan exported.";
  cue.querySelector("em").textContent = target
    ? target.manual_gate
    : "Export an agent action plan after recording Codex or Claude feedback.";
  button.disabled = !state.sessionId || !target;
}

function focusAgentActionPlan() {
  const target = state.agentActionPlanFocusTarget;
  if (!target) {
    focusElement("agentActionPlanPreview");
    return { target: "agentActionPlanPreview", action: "no-action-plan-target" };
  }
  if (target.drawer) {
    openSidebarDrawer(target.drawer);
  }
  if (target.secondary_drawer) {
    openSidebarDrawer(target.secondary_drawer);
  }
  focusElement(target.focus);
  return { target, focus: target.focus, action: "focus-planned-action" };
}

function refreshOutputInspectionReadiness() {
  const required = {
    baseline_summary: Boolean(el("baselineSummary").value.trim()),
    variant_summary: Boolean(el("variantSummary").value.trim()),
  };
  const optional = {
    baseline_tripinfo: Boolean(el("baselineTripinfo").value.trim()),
    variant_tripinfo: Boolean(el("variantTripinfo").value.trim()),
  };
  const status = required.baseline_summary && required.variant_summary
    ? "ready-to-inspect"
    : "needs-required-summary-paths";
  renderOutputInspectionReadiness(status, required, optional);
  return { status, required, optional };
}

function renderOutputInspectionReadiness(status, required, optional) {
  el("outputInspectionReadiness").textContent = [
    `status: ${status}`,
    "",
    "required:",
    `- baseline_summary: ${required.baseline_summary ? "filled" : "missing"}`,
    `- variant_summary: ${required.variant_summary ? "filled" : "missing"}`,
    "",
    "optional:",
    `- baseline_tripinfo: ${optional.baseline_tripinfo ? "filled" : "missing"}`,
    `- variant_tripinfo: ${optional.variant_tripinfo ? "filled" : "missing"}`,
    "",
    "manual_gate:",
    "- No files are opened or validated by this hint.",
    "- Inspect Outputs still requires a separate user action.",
  ].join("\n");
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

function workflowCueStatusClass(status) {
  return `status-${String(status || "unknown")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "unknown"}`;
}

function updateWorkflowCue(id, label, status, detail) {
  const cue = el(id);
  cue.className = `workflow-cue ${workflowCueStatusClass(status)}`;
  cue.replaceChildren();
  const labelNode = document.createElement("span");
  labelNode.textContent = label;
  const statusNode = document.createElement("strong");
  statusNode.textContent = status || "unknown";
  const detailNode = document.createElement("em");
  detailNode.textContent = detail || "No next action reported.";
  cue.append(labelNode, statusNode, detailNode);
}

function resetActiveSessionChecklist() {
  state.activeSessionChecklist = defaultActiveSessionChecklist();
  renderActiveSessionChecklist();
}

function updateActiveSessionChecklist(id, label, status, detail) {
  state.activeSessionChecklist[id] = {
    label,
    status: status || "unknown",
    detail: detail || "No next action reported.",
  };
  renderActiveSessionChecklist();
}

function activeChecklistStatusClass(status) {
  return `status-${String(status || "unknown")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "unknown"}`;
}

function activeChecklistIsReady(status) {
  return [
    "active",
    "pass",
    "ready",
    "review-ready",
    "ready-to-compare",
    "ready-for-agent-review",
    "ready-to-run-loop",
    "review-index-ready",
    "complete",
  ].includes(String(status || "").toLowerCase());
}

function renderActiveSessionChecklist() {
  const order = ["session", "workflow", "compare", "evidence-loop", "source-guide"];
  const container = el("activeSessionChecklist");
  container.replaceChildren();
  for (const id of order) {
    const item = state.activeSessionChecklist[id] || defaultActiveSessionChecklist()[id];
    const card = document.createElement("div");
    card.className = `active-checklist-card ${activeChecklistStatusClass(item.status)}`;
    const label = document.createElement("span");
    label.textContent = item.label;
    const status = document.createElement("strong");
    status.textContent = item.status || "unknown";
    const detail = document.createElement("em");
    detail.textContent = item.detail || "No next action reported.";
    card.append(label, status, detail);
    container.append(card);
  }
  const firstPending = order
    .map((id) => state.activeSessionChecklist[id])
    .find((item) => item && !activeChecklistIsReady(item.status));
  el("activeChecklistHeadline").textContent = state.sessionId
    ? firstPending?.detail || "Review checklist is current."
    : "No session active";
}

function renderWorkflow(body) {
  const checklist = (body.checklist || [])
    .map((item) => `${item.status.toUpperCase()} ${item.label}\n  evidence: ${item.evidence}`)
    .join("\n");
  const actions = (body.next_actions || []).map((item) => `- ${item}`).join("\n");
  updateWorkflowCue("workflowCueWorkflow", "Workflow", body.status, (body.next_actions || [])[0] || body.claim_status);
  updateActiveSessionChecklist("workflow", "Workflow", body.status, (body.next_actions || [])[0] || body.claim_status);
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
  updateWorkflowCue("workflowCueCompare", "Compare", body.status, (body.next_actions || [])[0] || body.claim_status);
  updateActiveSessionChecklist("compare", "Compare", body.status, (body.next_actions || [])[0] || body.claim_status);
  renderVisualComparisonFocus(body);
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

function visualComparisonFocusFromReadiness(body) {
  const checks = Object.fromEntries((body.checklist || []).map((item) => [item.id, item]));
  const beforeAfter = checks.before_after_checkpoints;
  const visualDiff = checks.visual_diff;
  if (!body.checklist || !body.checklist.length) {
    return {
      status: "not checked",
      detail: "Check comparison readiness to see whether checkpoints or visual diff are missing.",
      target: "visualReviewDrawer",
      focus: "visualDiffPreview",
    };
  }
  if (!beforeAfter || beforeAfter.status !== "pass") {
    return {
      status: "needs-checkpoints",
      detail: "Capture before-change and after-change checkpoints before exporting visual diff.",
      target: "runControlsDrawer",
      focus: "checkpointTemplate",
      template: "before-change",
    };
  }
  if (!visualDiff || visualDiff.status !== "pass") {
    return {
      status: "needs-visual-diff",
      detail: "Before/after checkpoints exist. Export Visual Diff to build the comparison matrix.",
      target: "advancedReviewActions",
      focus: "exportVisualDiffBtn",
    };
  }
  return {
    status: body.status || "ready",
    detail: "Visual diff is available. Open Visual Review to inspect the before/after matrix.",
    target: "visualReviewDrawer",
    focus: "visualDiffPreview",
  };
}

function renderVisualComparisonFocus(body) {
  const cue = visualComparisonFocusFromReadiness(body);
  const container = el("visualFocusCue");
  container.className = `visual-focus-cue ${workflowCueStatusClass(cue.status)}`;
  container.dataset.target = cue.target;
  container.dataset.focus = cue.focus;
  container.dataset.template = cue.template || "";
  el("visualFocusStatus").textContent = cue.status;
  el("visualFocusDetail").textContent = cue.detail;
}

function renderEvidenceLoopStatus(body, refreshTrigger = "manual-check") {
  renderEvidenceLoopNextAction(body, refreshTrigger);
  const sourceEvidence = (body.source_evidence || [])
    .map((item) => `${item.status.toUpperCase()} ${item.label}\n  evidence: ${item.evidence}`)
    .join("\n");
  const reviewExports = (body.review_exports || [])
    .map((item) => `${item.status.toUpperCase()} ${item.label}\n  evidence: ${item.evidence}`)
    .join("\n");
  const actions = (body.next_actions || []).map((item) => `- ${item}`).join("\n");
  el("evidenceLoopOutput").textContent = [
    `status: ${body.status}`,
    `refresh_trigger: ${refreshTrigger}`,
    `source_status: ${body.source_status}`,
    `review_status: ${body.review_status}`,
    "",
    "source_evidence:",
    sourceEvidence || "- none",
    "",
    "review_exports:",
    reviewExports || "- none",
    "",
    "next_actions:",
    actions || "- none",
    "",
    `claim_boundary: ${body.claim_boundary}`,
  ].join("\n");
}

function renderEvidenceLoopNextAction(body, refreshTrigger) {
  const firstNextAction = (body.next_actions || [])[0] || "No next action reported.";
  updateWorkflowCue("workflowCueEvidence", "Evidence loop", body.status, firstNextAction);
  updateActiveSessionChecklist("evidence-loop", "Evidence loop", body.status, firstNextAction);
  el("evidenceLoopNextAction").textContent = [
    `status: ${body.status}`,
    `refresh_trigger: ${refreshTrigger}`,
    `next_action: ${firstNextAction}`,
    "manual_gate: workflow cue only; inspect the detailed status before making claims.",
  ].join("\n");
}

function renderSourceGuideNextStep(body, refreshTrigger) {
  const firstGuideStep = (body.steps || [])[0];
  if (!firstGuideStep) {
    updateWorkflowCue("workflowCueSourceGuide", "Source guide", body.status, "No guide step reported.");
    updateActiveSessionChecklist("source-guide", "Source guide", body.status, "No guide step reported.");
    el("sourceGuideNextStep").textContent = [
      `status: ${body.status}`,
      `refresh_trigger: ${refreshTrigger}`,
      "guide_step: none",
      "manual_gate: workflow cue only; execute the guide step manually.",
    ].join("\n");
    return;
  }
  updateWorkflowCue("workflowCueSourceGuide", "Source guide", body.status, firstGuideStep.ui_action);
  updateActiveSessionChecklist("source-guide", "Source guide", body.status, firstGuideStep.ui_action);
  el("sourceGuideNextStep").textContent = [
    `status: ${body.status}`,
    `refresh_trigger: ${refreshTrigger}`,
    `guide_step: ${firstGuideStep.title}`,
    `ui_action: ${firstGuideStep.ui_action}`,
    `required_inputs: ${(firstGuideStep.required_inputs || []).join(", ") || "none"}`,
    `manual_gate: ${firstGuideStep.manual_gate}`,
    "boundary: workflow cue only; execute the guide step manually.",
  ].join("\n");
}

function renderSourceEvidenceGuide(body, refreshTrigger = "manual-guide") {
  renderSourceGuideNextStep(body, refreshTrigger);
  const steps = (body.steps || [])
    .map((step) => [
      `${step.status.toUpperCase()} ${step.title}`,
      `  id: ${step.id}`,
      `  source_evidence_id: ${step.source_evidence_id}`,
      `  ui_action: ${step.ui_action}`,
      `  endpoint: ${step.endpoint}`,
      `  required_inputs: ${(step.required_inputs || []).join(", ") || "none"}`,
      `  optional_inputs: ${(step.optional_inputs || []).join(", ") || "none"}`,
      "  suggested_inputs:",
      formatSuggestedInputs(step.suggested_inputs),
      `  manual_gate: ${step.manual_gate}`,
      "  guidance:",
      ...((step.guidance || []).map((item) => `    - ${item}`)),
    ].join("\n"))
    .join("\n\n");
  el("sourceEvidenceGuideOutput").textContent = [
    `status: ${body.status}`,
    `refresh_trigger: ${refreshTrigger}`,
    `evidence_loop_status: ${body.evidence_loop_status}`,
    `source_status: ${body.source_status}`,
    `review_status: ${body.review_status}`,
    "",
    "steps:",
    steps || "- none",
    "",
    `claim_boundary: ${body.claim_boundary}`,
  ].join("\n");
}

function formatSuggestedInputs(suggestedInputs) {
  const entries = Object.entries(suggestedInputs || {});
  if (!entries.length) {
    return "    - none";
  }
  return entries
    .map(([name, item]) => [
      `    - ${name}: ${item.path}`,
      `      candidate source: ${item.source}`,
      `      exists: ${item.exists}`,
      `      parent_exists: ${item.parent_exists}`,
      `      boundary: ${item.claim_boundary}`,
    ].join("\n"))
    .join("\n");
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

el("refreshCockpitBtn").addEventListener("click", async () => {
  try {
    await refreshCockpit();
  } catch (error) {
    log(`Cockpit refresh failed: ${error.message}`);
  }
});

el("compareReadinessBtn").addEventListener("click", async () => {
  try {
    await refreshComparisonReadiness();
  } catch (error) {
    log(`Comparison readiness failed: ${error.message}`);
  }
});

el("checkEvidenceLoopBtn").addEventListener("click", async () => {
  try {
    await refreshEvidenceLoopStatus("manual-check");
  } catch (error) {
    log(`Evidence loop readiness failed: ${error.message}`);
  }
});

el("guideSourceEvidenceBtn").addEventListener("click", async () => {
  try {
    await refreshSourceEvidenceGuide();
  } catch (error) {
    log(`Source evidence guide failed: ${error.message}`);
  }
});

el("focusSourceEvidenceBtn").addEventListener("click", async () => {
  try {
    await focusSourceEvidence();
  } catch (error) {
    log(`Source evidence focus failed: ${error.message}`);
  }
});

el("focusVisualComparisonBtn").addEventListener("click", () => {
  try {
    const result = focusVisualComparison();
    log("Focused visual comparison", result);
  } catch (error) {
    log(`Visual comparison focus failed: ${error.message}`);
  }
});

el("applySuggestedOutputPathsBtn").addEventListener("click", async () => {
  try {
    await applySuggestedOutputPaths();
  } catch (error) {
    log(`Suggested output path copy failed: ${error.message}`);
  }
});

async function refreshCockpit() {
  const results = [];
  results.push(await runCockpitRefreshStep("workflow status", async () => refreshWorkflow()));
  results.push(await runCockpitRefreshStep("comparison readiness", async () => refreshComparisonReadiness()));
  results.push(await runCockpitRefreshStep("evidence loop status", async () => refreshEvidenceLoopStatus("cockpit-refresh")));
  log("Refreshed cockpit", { results });
  return results;
}

async function runCockpitRefreshStep(label, action) {
  try {
    const output = await action();
    return { label, status: "pass", output: output || {} };
  } catch (error) {
    log(`Cockpit refresh step failed: ${label}: ${error.message}`);
    return { label, status: "fail", error: error.message };
  }
}

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
  renderAgentActionPlanFocus(body.agent_action_plan || {});
  el("agentActionPlanPreview").textContent = body.agent_action_plan_markdown || "No agent action plan exported.";
}

el("focusAgentActionPlanBtn").addEventListener("click", () => {
  const result = focusAgentActionPlan();
  log("Focused agent action plan", result);
});

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
  results.push(
    await runEvidenceLoopStep("evidence loop status", async () =>
      refreshEvidenceLoopStatus("guided-evidence-loop-start"),
    ),
  );
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
  await refreshEvidenceLoopStatus("guided-evidence-loop-finished");
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
  container.append(renderVisualDiffSummary(visualDiff));
  container.append(renderVisualDiffSpotlight(visualDiff));
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

function renderVisualDiffSummary(visualDiff) {
  const summary = document.createElement("div");
  summary.className = "visual-diff-summary";
  const pairs = visualDiff.pairs || [];
  summary.append(
    makeVisualDiffSummaryCard("status", visualDiff.status || "unknown", "visual diff index status"),
    makeVisualDiffSummaryCard("pairs", String(pairs.length), "paired before/after groups"),
  );
  if (pairs.length) {
    summary.append(renderVisualDiffPairSummary(pairs[0]));
  }
  const warnings = visualDiff.warnings || [];
  summary.append(
    makeVisualDiffSummaryCard(
      "boundary",
      warnings.length ? `${warnings.length} warning(s)` : "diagnostic only",
      "GUI screenshots still need output and completion evidence before claims.",
    ),
  );
  return summary;
}

function renderVisualDiffPairSummary(pair) {
  const dominantRow = dominantVisualDiffRow(pair);
  const ratio = dominantRow ? formatPixelRatio(dominantRow) || "pixel ratio unavailable" : "no row";
  const pixelStatus = pair.pixel_diff ? pair.pixel_diff.status || "unknown" : "index-only";
  return makeVisualDiffSummaryCard(
    "dominant_row",
    dominantRow ? dominantRow.label || dominantRow.role || "unknown" : "not available",
    `pixel_diff_status: ${pixelStatus}; ${ratio}`,
  );
}

function dominantVisualDiffRow(pair) {
  const rows = visualDiffRows(pair).filter((row) => typeof row.changed_pixel_ratio === "number");
  if (!rows.length) {
    return null;
  }
  return rows.reduce((best, row) => (row.changed_pixel_ratio > best.changed_pixel_ratio ? row : best), rows[0]);
}

function makeVisualDiffSummaryCard(label, value, detail) {
  const card = document.createElement("div");
  card.className = "visual-diff-summary-card";
  const labelNode = document.createElement("span");
  labelNode.textContent = label;
  const valueNode = document.createElement("strong");
  valueNode.textContent = value;
  const detailNode = document.createElement("em");
  detailNode.textContent = detail;
  card.append(labelNode, valueNode, detailNode);
  return card;
}

function renderVisualDiffSpotlight(visualDiff) {
  const dominant = dominantVisualDiffPair(visualDiff);
  if (!dominant) {
    return document.createDocumentFragment();
  }
  const { pair, row } = dominant;
  const section = document.createElement("section");
  section.className = "visual-diff-spotlight";

  const header = document.createElement("div");
  const title = document.createElement("h4");
  title.textContent = "Highest-change visual row";
  const meta = document.createElement("p");
  const ratio = formatPixelRatio(row) || "pixel ratio unavailable";
  const pixelStatus = pair.pixel_diff ? pair.pixel_diff.status || "unknown" : "index-only";
  meta.textContent = `Pair ${pair.index}; ${row.label || row.role || "unknown"}; ${ratio}; pixel_diff_status: ${pixelStatus}`;
  const action = document.createElement("button");
  action.type = "button";
  action.className = "visual-diff-spotlight-action";
  action.textContent = "Use as observation anchor";
  action.addEventListener("click", () => applyVisualDiffSpotlightObservation(pair, row));
  header.append(title, meta, action);

  const gallery = document.createElement("div");
  gallery.className = "visual-diff-spotlight-gallery";
  gallery.append(
    makeVisualDiffSpotlightCell("Before", row.before),
    makeVisualDiffSpotlightCell("After", row.after),
    makeVisualDiffSpotlightCell("Diff", row.pixel_diff),
  );

  const boundary = document.createElement("p");
  boundary.className = "visual-diff-spotlight-boundary";
  boundary.textContent = "Use this as the first visual inspection target; confirm claims with SUMO completion and output evidence.";

  section.append(header, gallery, boundary);
  return section;
}

function applyVisualDiffSpotlightObservation(pair, row) {
  const payload = visualDiffSpotlightObservationPayload(pair, row);
  el("visualObservationType").value = payload.observation_type;
  el("visualObservationArtifact").value = payload.evidence_artifact;
  el("visualObservationConfidence").value = payload.confidence;
  el("visualObservationLabel").value = payload.label;
  el("visualObservationRole").value = payload.comparison_role;
  el("visualObservationView").value = payload.visual_view;
  el("visualObservationAnchor").value = payload.visual_anchor;
  el("visualObservationNote").value = payload.note;
  if (el("visualObservationTaxonomy").querySelector(`option[value="${payload.observation_type}"]`)) {
    el("visualObservationTaxonomy").value = payload.observation_type;
  }
  openSidebarDrawer("visualReviewDrawer");
  focusElement("visualObservationNote");
  log("Prepared visual observation from spotlight", payload);
  return payload;
}

function visualDiffSpotlightObservationPayload(pair, row) {
  const rowRole = row.role === "baseline" || row.role === "variant" ? row.role : "both";
  const rowLabel = row.label || row.role || "unknown row";
  const ratio = formatPixelRatio(row) || "pixel ratio unavailable";
  const anchorParts = [
    "visual-diff spotlight",
    `pair ${pair.index}`,
    rowLabel,
    `before=${row.before || "not available"}`,
    `after=${row.after || "not available"}`,
    `diff=${row.pixel_diff || "not available"}`,
  ];
  return {
    label: "spotlight-visual-observation",
    observation_type: "density-change",
    evidence_artifact: "visual-diff.md",
    confidence: "diagnostic",
    comparison_role: rowRole,
    visual_view: "diff",
    visual_anchor: anchorParts.join("; "),
    note: `Highest-change visual-diff row: pair ${pair.index}, ${rowLabel}, ${ratio}. Inspect the before/after/diff artifacts and verify against SUMO completion and output evidence before making a claim.`,
  };
}

function dominantVisualDiffPair(visualDiff) {
  let dominant = null;
  for (const pair of visualDiff.pairs || []) {
    const row = dominantVisualDiffRow(pair);
    if (!row || typeof row.changed_pixel_ratio !== "number") {
      continue;
    }
    if (!dominant || row.changed_pixel_ratio > dominant.row.changed_pixel_ratio) {
      dominant = { pair, row };
    }
  }
  return dominant;
}

function makeVisualDiffSpotlightCell(labelText, relativePath) {
  const cell = document.createElement("div");
  cell.className = "visual-diff-spotlight-cell";
  const label = document.createElement("span");
  label.textContent = labelText;
  cell.append(label);
  if (!relativePath) {
    const missing = document.createElement("p");
    missing.textContent = "Not available";
    cell.append(missing);
    return cell;
  }
  cell.append(makeDiffImage(labelText, relativePath));
  return cell;
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
    state.sessionId = null;
    state.hasExperimentStateBoard = false;
    el("sessionId").textContent = "none";
    el("sessionDir").textContent = "not created";
    setControls(false);
  } catch (error) {
    log(`Close failed: ${error.message}`);
  }
});

for (const inputId of outputPathInputIds) {
  el(inputId).addEventListener("input", refreshOutputInspectionReadiness);
}

setControls(false);
refreshOutputInspectionReadiness();
loadScenarioTemplates().catch((error) => {
  log(`Scenario template load failed: ${error.message}`);
});
