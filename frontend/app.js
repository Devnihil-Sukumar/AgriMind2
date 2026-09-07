(function () {
  "use strict";

  const API_BASE = "";

  // ================================================================
  // DOM references
  // ================================================================

  const form = document.getElementById("queryForm");
  const cropInput = document.getElementById("cropInput");
  const queryInput = document.getElementById("queryInput");
  const latInput = document.getElementById("latInput");
  const lonInput = document.getElementById("lonInput");
  const submitBtn = document.getElementById("submitBtn");
  const submitBtnLabel = document.getElementById("submitBtnLabel");
  const useDefaultLocationBtn = document.getElementById("useDefaultLocation");

  const apiStatusDot = document.getElementById("apiStatusDot");
  const apiStatusText = document.getElementById("apiStatusText");

  const emptyState = document.getElementById("emptyState");
  const loadingState = document.getElementById("loadingState");
  const errorState = document.getElementById("errorState");
  const errorMessage = document.getElementById("errorMessage");
  const resultsState = document.getElementById("resultsState");
  const loadingSeconds = document.getElementById("loadingSeconds");

  const tabs = document.getElementById("tabs");
  const rawJsonEl = document.getElementById("rawJson");

  let defaults = { latitude: 11.0168, longitude: 76.9558, crop: "rice" };
  let loadingTimer = null;

  // ================================================================
  // Helpers
  // ================================================================

  function esc(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function pct(value) {
    const n = Number(value);
    if (Number.isNaN(n)) return "0%";
    const v = n > 1 ? n : n * 100;
    return Math.round(v) + "%";
  }

  function pctValue(value) {
    const n = Number(value);
    if (Number.isNaN(n)) return 0;
    return n > 1 ? n : n * 100;
  }

  function titleCase(str) {
    return String(str)
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function badgeClass(status) {
    const s = String(status || "").toLowerCase();
    return "status-" + s.replace(/\s+/g, "_");
  }

  function badge(text, extraClass) {
    if (text === null || text === undefined || text === "") return "";
    return `<span class="badge ${badgeClass(text)} ${extraClass || ""}">${esc(text)}</span>`;
  }

  function confidenceBar(value, label) {
    const v = pctValue(value);
    return `
      <div>
        <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--text-muted);margin-bottom:2px;">
          <span>${esc(label || "Confidence")}</span>
          <span>${Math.round(v)}%</span>
        </div>
        <div class="confidence-bar-track">
          <div class="confidence-bar-fill" style="width:${Math.max(0, Math.min(100, v))}%"></div>
        </div>
      </div>`;
  }

  function chipList(items, cls) {
    if (!items || !items.length) return `<span class="text-muted" style="font-size:12.5px;">None reported.</span>`;
    return `<div class="chip-list">${items
      .map((item) => `<span class="chip ${cls || ""}">${esc(item)}</span>`)
      .join("")}</div>`;
  }

  function listPlain(items) {
    if (!items || !items.length) return `<p class="text-muted" style="font-size:13px;">None.</p>`;
    return `<ul class="list-plain">${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>`;
  }

  function kv(label, value) {
    const display = Array.isArray(value)
      ? value.map((v) => (typeof v === "object" ? JSON.stringify(v) : v)).join(", ")
      : value;
    return `<div class="kv"><div class="k">${esc(label)}</div><div class="v">${esc(display)}</div></div>`;
  }

  // Generic renderer for objects/arrays whose exact shape can vary
  // (LLM-generated or loosely-typed sections).
  function genericBlock(value) {
    if (value === null || value === undefined) return `<span class="text-muted">Not available.</span>`;

    if (Array.isArray(value)) {
      if (!value.length) return `<span class="text-muted">None.</span>`;
      return value
        .map((item) => `<div class="card" style="margin-bottom:8px;padding:12px;">${genericBlock(item)}</div>`)
        .join("");
    }

    if (typeof value === "object") {
      const entries = Object.entries(value).filter(([, v]) => v !== null && v !== undefined && v !== "");
      if (!entries.length) return `<span class="text-muted">None.</span>`;
      return `<div class="kv-grid">${entries
        .map(([k, v]) => {
          let display;
          if (Array.isArray(v)) display = v.map((x) => (typeof x === "object" ? JSON.stringify(x) : x)).join(", ");
          else if (typeof v === "object") display = JSON.stringify(v);
          else display = v;
          return kv(titleCase(k), display);
        })
        .join("")}</div>`;
    }

    return esc(value);
  }

  function section(title, innerHtml) {
    return `<div class="section-title">${esc(title)}</div>${innerHtml}`;
  }

  // ================================================================
  // API status + defaults
  // ================================================================

  async function checkHealth() {
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      if (!res.ok) throw new Error("bad status");
      apiStatusDot.classList.add("ok");
      apiStatusText.textContent = "Backend connected";
    } catch (e) {
      apiStatusDot.classList.add("bad");
      apiStatusText.textContent = "Backend unreachable";
    }
  }

  async function loadDefaults() {
    try {
      const res = await fetch(`${API_BASE}/api/defaults`);
      if (!res.ok) throw new Error("bad status");
      defaults = await res.json();
      latInput.placeholder = `default (${defaults.latitude})`;
      lonInput.placeholder = `default (${defaults.longitude})`;
    } catch (e) {
      // Keep hard-coded fallback defaults; form still works.
    }
  }

  useDefaultLocationBtn.addEventListener("click", () => {
    latInput.value = defaults.latitude;
    lonInput.value = defaults.longitude;
  });

  document.querySelectorAll(".example-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      cropInput.value = chip.dataset.crop;
      queryInput.value = chip.dataset.query;
      queryInput.focus();
    });
  });

  // ================================================================
  // Tabs
  // ================================================================

  tabs.addEventListener("click", (e) => {
    const btn = e.target.closest(".tab");
    if (!btn) return;
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  });

  // ================================================================
  // State transitions
  // ================================================================

  function showState(state) {
    emptyState.classList.add("hidden");
    loadingState.classList.add("hidden");
    errorState.classList.add("hidden");
    resultsState.classList.add("hidden");
    if (state === "empty") emptyState.classList.remove("hidden");
    if (state === "loading") loadingState.classList.remove("hidden");
    if (state === "error") errorState.classList.remove("hidden");
    if (state === "results") resultsState.classList.remove("hidden");
  }

  function startLoadingTimer() {
    let seconds = 0;
    loadingSeconds.textContent = "0";
    loadingTimer = setInterval(() => {
      seconds += 1;
      loadingSeconds.textContent = String(seconds);
    }, 1000);
  }

  function stopLoadingTimer() {
    if (loadingTimer) {
      clearInterval(loadingTimer);
      loadingTimer = null;
    }
  }

  // ================================================================
  // Submit
  // ================================================================

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      query: queryInput.value.trim(),
      crop: (cropInput.value || "rice").trim(),
      latitude: latInput.value === "" ? null : Number(latInput.value),
      longitude: lonInput.value === "" ? null : Number(lonInput.value),
    };

    if (!payload.query) {
      queryInput.focus();
      return;
    }

    submitBtn.disabled = true;
    submitBtnLabel.textContent = "Running…";
    showState("loading");
    startLoadingTimer();

    try {
      const res = await fetch(`${API_BASE}/api/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || `Request failed with status ${res.status}`);
      }

      renderResult(data);
      showState("results");
    } catch (err) {
      errorMessage.textContent = err.message || String(err);
      showState("error");
    } finally {
      stopLoadingTimer();
      submitBtn.disabled = false;
      submitBtnLabel.textContent = "Run Analysis";
    }
  });

  // ================================================================
  // Render: top level
  // ================================================================

  function renderResult(data) {
    const execution = data.execution || {};
    const context = data.context || {};
    const specialists = execution.specialists || {};
    const reasoning = execution.reasoning || {};
    const executive = execution.executive || {};
    const recommendation = execution.recommendation || {};
    const explanation = execution.explanation || {};
    const governance = execution.governance || {};
    const statistics = execution.statistics || {};

    document.getElementById("tab-overview").innerHTML = renderOverview(
      data, context, executive, recommendation, statistics
    );
    document.getElementById("tab-specialists").innerHTML = renderSpecialists(specialists);
    document.getElementById("tab-reasoning").innerHTML = renderReasoning(reasoning, governance, data);
    document.getElementById("tab-explainability").innerHTML = renderExplainability(explanation);
    rawJsonEl.textContent = JSON.stringify(data, null, 2);

    // Reset to first tab on every new result.
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    document.querySelector('.tab[data-tab="overview"]').classList.add("active");
    document.getElementById("tab-overview").classList.add("active");
  }

  // ================================================================
  // Render: Overview
  // ================================================================

  function renderOverview(data, context, executive, recommendation, statistics) {
    const recText = recommendation.recommendation || executive.decision || "No recommendation was generated.";
    const priority = recommendation.priority || executive.priority || "unknown";
    const confidence = recommendation.confidence ?? executive.confidence ?? data.confidence ?? 0;
    const generationMode = recommendation.generation_mode;

    const impact = executive.impact || {};
    const priorities = executive.priorities || [];
    const actions = recommendation.actions || [];
    const monitoring = recommendation.monitoring_plan || [];

    const hero = `
      <div class="hero-card">
        <div class="hero-eyebrow">Recommendation</div>
        <div class="hero-text">${esc(recText)}</div>
        <div class="hero-meta">
          ${badge(priority, "on-dark")}
          ${executive.urgency ? badge(executive.urgency, "on-dark") : ""}
          ${executive.risk_level ? badge(executive.risk_level, "on-dark") : ""}
          ${generationMode ? `<span class="badge on-dark">${esc(generationMode)}</span>` : ""}
        </div>
        <div style="margin-top:16px;max-width:260px;">
          ${confidenceBarLight(confidence, "Recommendation confidence")}
        </div>
      </div>`;

    const executiveCard = `
      <div class="card">
        <h3>Executive Decision</h3>
        <p class="text-block">${esc(executive.decision || "—")}</p>
        <div class="kv-grid">
          ${kv("Priority", executive.priority || "—")}
          ${kv("Urgency", executive.urgency || "—")}
          ${kv("Risk Level", executive.risk_level || "—")}
          ${kv("Action Order", executive.action_order || "—")}
        </div>
        ${priorities.length ? `
          <div class="section-title">Priorities</div>
          <div class="table-wrap"><table class="table-simple">
            <thead><tr><th>Issue</th><th>Severity</th><th>Urgency</th><th>Owner</th><th>Action</th></tr></thead>
            <tbody>
              ${priorities.map((p) => `
                <tr>
                  <td>${esc(p.issue)}</td>
                  <td>${badge(p.severity)}</td>
                  <td>${esc(p.urgency)}</td>
                  <td>${esc(p.owner)}</td>
                  <td>${esc(p.action)}</td>
                </tr>`).join("")}
            </tbody>
          </table></div>` : ""}
      </div>`;

    const impactCard = Object.keys(impact).length ? `
      <div class="card">
        <h3>Estimated Impact</h3>
        <div class="kv-grid">
          ${Object.entries(impact).map(([k, v]) => kv(titleCase(k), v)).join("")}
        </div>
      </div>` : "";

    const actionsCard = `
      <div class="card">
        <h3>Recommended Actions</h3>
        ${listPlain(actions)}
      </div>`;

    const monitoringCard = `
      <div class="card">
        <h3>Monitoring Plan</h3>
        ${listPlain(monitoring)}
      </div>`;

    const contextCard = `
      <div class="card">
        <h3>Farm Context</h3>
        <div class="kv-grid">
          ${kv("Crop", context.crop || "—")}
          ${kv("Location", `${context.location?.district || "Unknown"}, ${context.location?.state || "Unknown"}`)}
          ${kv("Weather Status", context.weather_status || "—")}
          ${kv("Soil Health Score", context.soil_health ?? "—")}
          ${kv("Vegetation Health", context.vegetation_health || "—")}
          ${kv("Market Trend", context.market_trend || "—")}
          ${kv("Historical Records", context.historical_records ?? "—")}
        </div>
        <div class="section-title">Risks</div>
        ${chipList(context.risks, "risk")}
        <div class="section-title">Opportunities</div>
        ${chipList(context.opportunities, "opportunity")}
      </div>`;

    const statsCard = `
      <div class="card">
        <h3>Pipeline Statistics</h3>
        <div class="kv-grid">
          ${kv("Agents Planned", statistics.agents_planned ?? "—")}
          ${kv("Agents Completed", statistics.agents_completed ?? "—")}
          ${kv("Agents Failed", statistics.agents_failed ?? "—")}
          ${kv("Agents Unavailable", statistics.agents_unavailable ?? "—")}
          ${kv("Total Time (s)", data.total_time ?? "—")}
        </div>
      </div>`;

    return hero + `<div class="card-grid">${executiveCard}${impactCard}${contextCard}${actionsCard}${monitoringCard}${statsCard}</div>`;
  }

  function confidenceBarLight(value, label) {
    const v = pctValue(value);
    return `
      <div>
        <div style="display:flex;justify-content:space-between;font-size:12px;color:rgba(255,255,255,0.85);margin-bottom:4px;">
          <span>${esc(label || "Confidence")}</span>
          <span>${Math.round(v)}%</span>
        </div>
        <div class="confidence-bar-track" style="background:rgba(255,255,255,0.25);">
          <div class="confidence-bar-fill" style="width:${Math.max(0, Math.min(100, v))}%;background:#fff;"></div>
        </div>
      </div>`;
  }

  // ================================================================
  // Render: Specialists
  // ================================================================

  function renderSpecialists(specialists) {
    const names = Object.keys(specialists);
    if (!names.length) return `<p class="text-muted">No specialist agents ran for this query.</p>`;

    return `<div class="card-grid">${names
      .map((name) => {
        const out = specialists[name] || {};
        const gov = out.governance || {};
        const decision = gov.decision || {};

        return `
          <div class="card">
            <div class="agent-card-header">
              <span class="agent-name">${esc(name)}</span>
              ${badge(out.status)}
            </div>
            ${confidenceBar(out.confidence, "Specialist confidence")}
            <p class="text-block" style="margin-top:12px;">${esc(out.summary || out.analysis || out.error || "No analysis available.")}</p>
            <div class="section-title">Risks</div>
            ${chipList(out.risks, "risk")}
            <div class="section-title">Opportunities</div>
            ${chipList(out.opportunities, "opportunity")}
            <div class="kv-grid" style="margin-top:14px;">
              ${kv("Execution Time (s)", out.execution_time ?? "—")}
              ${kv("Trust Posterior", gov.posterior_mean !== undefined ? Math.round(gov.posterior_mean * 100) + "%" : "—")}
            </div>
            ${decision.action ? `
              <div class="section-title">Governance</div>
              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                ${badge(decision.action)}
                <span class="text-muted" style="font-size:12.5px;">${esc(decision.rationale || "")}</span>
              </div>` : ""}
          </div>`;
      })
      .join("")}</div>`;
  }

  // ================================================================
  // Render: Reasoning & Governance
  // ================================================================

  function renderReasoning(reasoning, governance, data) {
    const agentTrust = governance.agent_trust || {};
    const cropLearning = governance.crop_learning || {};
    const conflicts = reasoning.conflicts || [];

    const reasoningCard = `
      <div class="card">
        <h3>Collaborative Reasoning</h3>
        ${confidenceBar(reasoning.confidence, "Reasoning confidence")}
        <div class="section-title">Summary</div>
        <p class="text-block">${esc(reasoning.summary || "—")}</p>
        <div class="section-title">Consensus</div>
        <p class="text-block">${esc(reasoning.consensus || "—")}</p>
        <div class="section-title">Merged Risks</div>
        ${chipList(reasoning.merged_risks, "risk")}
        <div class="section-title">Merged Opportunities</div>
        ${chipList(reasoning.merged_opportunities, "opportunity")}
        ${conflicts.length ? `<div class="section-title">Conflicts</div>${genericBlock(conflicts)}` : ""}
      </div>`;

    const trustRows = Object.entries(agentTrust);
    const trustCard = `
      <div class="card">
        <h3>TRUSTAI Governance — Agent Trust</h3>
        ${trustRows.length ? `
          <div class="table-wrap"><table class="table-simple">
            <thead><tr><th>Agent</th><th>Category</th><th>Trust Mean</th><th>Trust Std</th></tr></thead>
            <tbody>
              ${trustRows.map(([name, t]) => `
                <tr>
                  <td>${esc(name)}</td>
                  <td>${esc(t.category)}</td>
                  <td>${pct(t.trust_mean)}</td>
                  <td>${esc((t.trust_std ?? 0).toFixed ? t.trust_std.toFixed(4) : t.trust_std)}</td>
                </tr>`).join("")}
            </tbody>
          </table></div>` : `<p class="text-muted">No trust snapshot available.</p>`}
      </div>`;

    const learningCard = `
      <div class="card">
        <h3>Continuous Learning — Crop Trust</h3>
        <div class="kv-grid">
          ${kv("Crop", cropLearning.crop || "—")}
          ${kv("Trust Mean", cropLearning.trust_mean !== undefined ? pct(cropLearning.trust_mean) : "—")}
          ${kv("Decision", cropLearning.decision || "—")}
        </div>
        <div class="kv-grid" style="margin-top:14px;">
          ${kv("Recommendation Requires Review", governance.recommendation_requires_review ? "Yes" : "No")}
          ${kv("Recommendation Rejected", governance.recommendation_rejected ? "Yes" : "No")}
        </div>
      </div>`;

    return `<div class="card-grid">${reasoningCard}${trustCard}${learningCard}</div>`;
  }

  // ================================================================
  // Render: Explainability
  // ================================================================

  function renderExplainability(explanation) {
    if (!explanation || !Object.keys(explanation).length) {
      return `<p class="text-muted">No explainability report was generated.</p>`;
    }

    const trace = (explanation.decision_trace && explanation.decision_trace.steps) || [];
    const evidence = explanation.evidence || {};
    const rankedEvidence = evidence.ranked_evidence || evidence.top_evidence || [];
    const limitations = explanation.limitations || [];
    const monitoring = explanation.monitoring_plan || [];
    const alternatives = explanation.rejected_alternatives || [];

    const narrativeCard = `
      <div class="card">
        <h3>Explanation</h3>
        ${confidenceBar(explanation.overall_confidence, "Overall confidence")}
        <p class="text-block" style="margin-top:12px;">${esc(explanation.explanation || "—")}</p>
        ${explanation.farmer_message ? `
          <div class="section-title">Farmer-Friendly Summary</div>
          <p class="text-block">${esc(explanation.farmer_message)}</p>` : ""}
      </div>`;

    const traceCard = `
      <div class="card">
        <h3>Decision Trace</h3>
        ${trace.length ? trace.map((step) => `
          <div class="trace-step">
            <div class="trace-index">${esc(step.step)}</div>
            <div>
              <div style="font-weight:700;font-size:13px;">${esc(step.stage)} ${step.source ? "· " + esc(step.source) : ""}</div>
              <div class="text-block" style="margin-top:2px;">${esc(step.finding || "")}</div>
              ${step.confidence !== undefined ? `<div class="text-muted" style="font-size:12px;margin-top:2px;">Confidence: ${pct(step.confidence)}</div>` : ""}
            </div>
          </div>`).join("") : `<p class="text-muted">No decision trace available.</p>`}
      </div>`;

    const evidenceCard = `
      <div class="card">
        <h3>Ranked Evidence</h3>
        ${rankedEvidence.length ? `
          <div class="table-wrap"><table class="table-simple">
            <thead><tr><th>Source</th><th>Type</th><th>Finding</th><th>Score</th><th>Importance</th></tr></thead>
            <tbody>
              ${rankedEvidence.map((e) => `
                <tr>
                  <td>${esc(e.source)}</td>
                  <td>${esc(e.type)}</td>
                  <td>${esc(e.finding)}</td>
                  <td>${pct(e.evidence_score)}</td>
                  <td>${badge(e.importance)}</td>
                </tr>`).join("")}
            </tbody>
          </table></div>` : `<p class="text-muted">No ranked evidence available.</p>`}
      </div>`;

    const limitationsCard = `
      <div class="card">
        <h3>Limitations</h3>
        ${limitations.length ? limitations.map((l) => `
          <div style="margin-bottom:12px;">
            <div style="font-weight:700;font-size:13px;">${esc(l.category)}</div>
            <div class="text-block">${esc(l.limitation)}</div>
            <div class="text-muted" style="font-size:12.5px;margin-top:2px;">${esc(l.impact)}</div>
          </div>`).join("") : `<p class="text-muted">None reported.</p>`}
      </div>`;

    const monitoringCard = `
      <div class="card">
        <h3>Monitoring Plan</h3>
        ${monitoring.length ? `
          <div class="table-wrap"><table class="table-simple">
            <thead><tr><th>Source</th><th>Parameter</th><th>Frequency</th><th>Reason</th></tr></thead>
            <tbody>
              ${monitoring.map((m) => `
                <tr>
                  <td>${esc(m.source)}</td>
                  <td>${esc(m.parameter)}</td>
                  <td>${esc(m.frequency)}</td>
                  <td>${esc(m.reason)}</td>
                </tr>`).join("")}
            </tbody>
          </table></div>` : `<p class="text-muted">No monitoring plan available.</p>`}
      </div>`;

    const alternativesCard = alternatives.length ? `
      <div class="card">
        <h3>Rejected Alternatives</h3>
        ${genericBlock(alternatives)}
      </div>` : "";

    return narrativeCard + `<div class="card-grid">${traceCard}${evidenceCard}${limitationsCard}${monitoringCard}${alternativesCard}</div>`;
  }

  // ================================================================
  // Init
  // ================================================================

  checkHealth();
  loadDefaults();
})();
