# AgriMind — Complete Project Documentation

AgriMind is a multi-agent, LLM-based decision-support system for precision
agriculture. A farmer asks a natural-language question about a crop at a
location; the system fans out to five specialist AI agents (weather, soil,
satellite, market, historical), fuses their findings through a
collaborative-reasoning stage, produces a governed executive decision and
recommendation, and returns a fully-explained result — decision trace,
ranked evidence, limitations, monitoring plan, and a Bayesian trust
snapshot for every agent involved.

This document traces the system **end to end, input to output**: every
file in the live request path, its exact input/output shape, which
external service or LLM provider it calls, and how the pieces connect.
It also documents which parts of the codebase are legacy/unused, since
several earlier project iterations are still present on disk alongside
the current one.

---

## 1. High-Level Architecture

```
                         POST /api/recommend
                    { query, crop, latitude, longitude }
                                 │
                                 ▼
                    app/api/agrimind_api.py
                                 │
                                 ▼
          app/orchestrator/dynamic_orchestrator.py  (run)
                                 │
   ┌─────────────────────────────┼─────────────────────────────┐
   │ 1. Crop Knowledge            │ crop_knowledge_agent → crop_profile_manager
   │ 2. Data Collection           │ data_collector → 5 collectors → 5 external sources
   │ 3. Context Understanding     │ context_agent (pure Python, no LLM)
   │ 4. Dynamic Planning          │ planner (Groq, deterministic fallback)
   │ 5. Specialist Execution      │ executor → 5 specialist agents (Ollama/Groq) + TRUSTAI
   │ 6. Collaborative Reasoning   │ collaborative_engine (Gemini, deterministic fallback)
   │ 7. Executive Decision        │ executive_agent (pure rule engine, no LLM)
   │ 8. Recommendation            │ recommendation_agent (Groq, deterministic fallback)
   │ 9. Explainability            │ explanation_engine (Groq narrative + deterministic artifacts)
   │ 10. Governance               │ trustai + continuous_learning_engine (Bayesian, Beta-Bernoulli)
   └─────────────────────────────┼─────────────────────────────┘
                                 ▼
                    Full JSON response (§9 below)
                                 │
                                 ▼
                   frontend/ dashboard renders it
```

Every stage below is a real Python module read directly for this
document — none of this is inferred from names alone.

---

## 2. Entry Point and Request Contract

**`main.py`** — the FastAPI application. It mounts two independent things
under one process:

- `agrimind_router` (`app/api/agrimind_api.py`) — the AI recommendation
  pipeline described in this document.
- `farmer_router, farm_router, crop_router, recommendation_router,
  weather_router` — a **separate, unrelated CRUD subsystem** backed by
  `app/database/*` (SQLAlchemy models, a Postgres-backed `get_db()`
  session). This does plain database CRUD with no agents or LLMs
  involved, and is not part of the pipeline this document traces.
- `frontend/` served as static files at `/dashboard`.

**`app/api/agrimind_api.py`** — the pipeline's actual entry point:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | `{"status": "ok"}` liveness check |
| `/api/defaults` | GET | `{latitude, longitude, crop}` from `app.config.ai_settings`, for the frontend to prefill |
| `/api/recommend` | POST | Runs the full pipeline |

**Request body** (`RecommendationRequest`, Pydantic):

```json
{
  "query": "string, min length 3, required",
  "crop": "string, default \"rice\"",
  "latitude": "float or null, -90..90",
  "longitude": "float or null, -180..180"
}
```

Missing `latitude`/`longitude` fall back to `ai_settings.DEFAULT_LATITUDE`
/ `DEFAULT_LONGITUDE` (11.0168, 76.9558). `crop` is lower-cased and
stripped. The handler calls
`dynamic_orchestrator.run(user_query, crop, latitude, longitude)` via
`run_in_threadpool` (so the synchronous, multi-minute pipeline doesn't
block FastAPI's event loop) and returns its result dict verbatim, or
raises `HTTPException(500, "Pipeline execution failed: {e}")` on any
uncaught exception.

---

## 3. Stage 1 — Crop Knowledge

**Files:** `app/agents/crop_knowledge_agent.py`,
`app/knowledge/crop_profile_manager.py`, `crop_profile_builder.py`,
`crop_profile_repository.py`, `crop_profile_validator.py`

`CropKnowledgeAgent.execute(crop)` returns
`{agent, status:"completed", confidence:1.0, crop_profile}`.

The profile itself is built by `crop_profile_manager.get_profile(crop)`:

1. `crop_profile_repository.exists(crop)` — SQLite check.
2. **If cached**, `.load(crop)` — tries a per-crop JSON file
   (`app/knowledge/crop_profiles/{crop}.json`) first, then the SQLite
   table `crop_profiles` (`app/database/crop_profiles.db`), re-validates
   and re-saves on every load in case the schema has since evolved.
3. **If not cached**, `crop_profile_builder.build(crop)` calls
   **Groq** with a fixed schema prompt (`CROP_PROFILE_PROMPT`), parses
   the JSON response, and forces `profile["crop"] = crop.lower().strip()`
   before returning — the profile's own `"crop"` field is *not* trusted
   from the LLM's echo, specifically because it silently broke caching
   in practice (see §11, bug log). `crop_profile_validator.validate()`
   then deep-merges the result into a canonical default schema, migrates
   any legacy field names, and `crop_profile_repository.save()` writes it
   to both the SQLite table and the JSON cache.

A crop profile carries agronomic thresholds (optimal temperature/
humidity/rainfall/soil-pH ranges, satellite NDVI/NDWI/SAVI health
thresholds, preferred soil texture/nitrogen/drainage, market keywords,
common diseases/pests, fertilizer recommendations) that every downstream
stage compares live sensor data against.

---

## 4. Stage 2 — Data Collection

**File:** `app/collectors/data_collector.py`, calling five independent
collectors, each wrapped in its own try/except so one source failing
never crashes the run.

| Source | Collector → implementation | Real data source | Output highlights |
|---|---|---|---|
| **Weather** | `weather_collector.py` → `app/tools/weather_tool.py` → `app/services/weather_service.py` | **Open-Meteo API** (live HTTP call: `current=[temperature_2m, relative_humidity_2m, rain, wind_speed_10m, surface_pressure]`) | `raw_data:{temperature,humidity,rainfall,wind_speed,pressure}`, `assessment:{status,identified_risks,opportunities}` scored against the crop profile's optimal bands |
| **Soil** | `soil_collector.py` → `app/tools/soil_tool.py` → `app/services/soilgrids_service.py` | **ISRIC SoilGrids v2.0** (live, keyless REST API), falling back to the local synthetic CSV (`data/soil_data.csv`) on a coverage gap or outage | `{ph,nitrogen,organic_carbon,sand/clay/silt_percent,cec,bulk_density,field_capacity,wilting_point,distance_km,live_source}`, `assessment:{soil_health_score,ph_status,...}` |
| **Satellite** | `satellite_collector.py` → `app/tools/satellite_tool.py` → `app/services/earth_engine_service.py` | **Google Earth Engine / Sentinel-2** (real satellite imagery, cloud-masked, least-cloudy image within a configurable lookback window) | `imagery:{acquisition_date,cloud_cover}`, `vegetation:{ndvi,evi,savi,health}`, `water:{ndwi,stress}`, `soil:{exposure}` |
| **Market** | `market_collector.py` → `app/tools/market_tool.py` → `app/services/agmarknet_service.py`, `app/algorithms/market_ranker.py` | **Agmarknet via data.gov.in** (live daily mandi prices, needs `DATA_GOV_IN_API_KEY`), falling back to the local synthetic CSV (`data/market_prices.csv`, auto-reloaded on file change) | Ranks markets by `0.50×price + 0.30×trend + 0.20×distance`; `market, nearest_market, top_markets[...]` |
| **Historical** | `historical_collector.py` | **SQLite** table `farm_history` (`settings.SQLITE_DB_PATH`) | Last 5 records for the crop; an empty history is `status:"success", record_count:0` — treated as a meaningful signal, not an error |

Final shape:
`{metadata:{collection_time,crop,crop_profile,location}, weather, soil,
market, satellite, historical}`.

**Live vs. synthetic provenance.** Weather, satellite, soil and market
all read real external services; only `historical` is intentionally
local (per-farm records are not a public dataset). Soil and market each
carry a `live_source` boolean and a `metadata.source` string, and both
degrade to their synthetic dataset rather than failing when the upstream
service has no data for the location or is unreachable — SoilGrids
masks built-up land, so a null there is a legitimate answer rather than
an error. Set `SOIL_LIVE_SOURCE=0` / `MARKET_LIVE_SOURCE=0` to force the
synthetic path when reproducing an older run. Because the two paths emit
an identical schema, downstream agents cannot accidentally depend on
which one served a given request, and the evaluation can separate
measured from synthetic runs by reading one flag.

---

## 5. Stage 3 — Context Understanding

**File:** `app/agents/context_agent.py` — pure Python, no LLM call.

Merges the five collector outputs into one flat context dict:
resolves district/state (soil's own location data preferred, falling
back through soil's raw data, then any existing location field),
deterministically aggregates `risks`/`opportunities` (e.g. vegetation
health "Critical" → risk; soil health ≥90 → opportunity), and computes an
unweighted average `confidence` across weather/soil/market/satellite
(satellite only counted if it actually returned data).

Output: `{crop, crop_profile, location:{district,state}, weather, soil,
satellite, market, historical, historical_records,
historical_similarity, weather_status, soil_health, vegetation_health,
market_trend, risks, opportunities, confidence}` — this single dict is
what every remaining stage consumes.

---

## 6. Stage 4 — Dynamic Planning

**File:** `app/orchestrator/planner.py`

1. Builds a **compact** context (crop/location/weather/soil/satellite/
   market summaries + historical availability only) rather than the full
   context — deliberately, to keep the Groq request small enough to fit
   the account's per-minute token budget.
2. Calls Groq with the compact context and the user's query, asking for
   an `execution_plan` (which specialist agents are relevant to this
   specific question).
3. **Validates and normalizes** the response: strips markdown fences,
   extracts the outer JSON object, accepts a few different key names the
   model might use (`execution_plan`/`agents`/`specialist_agents`),
   normalizes agent-name aliases, and **guarantees `RecommendationAgent`
   is always present and always scheduled last**.
4. **On any LLM/parse/validation failure** (after one retry), falls back
   to a deterministic keyword router (`build_fallback_plan`) that matches
   query terms (irrigation, crop health, yield, profit intents, plus
   per-domain keyword lists) to select agents — the pipeline never fails
   outright just because the planner's LLM call failed.

Output: `{goal, execution_plan:[{agent, priority, purpose}], confidence}`.

This is why different questions about the same crop/location can invoke
different subsets of the five specialists — a yield-optimization query
typically routes to Weather/Soil/Satellite; a market-timing query routes
to Market/Historical; a suitability/risk query tends to invoke all five.

---

## 7. Stage 5 — Specialist Agent Execution

**Files:** `app/orchestrator/executor.py`, `app/agents/base_agent.py`,
and the five specialist subclasses (`weather_agent.py`, `soil_agent.py`,
`satellite_agent.py`, `market_agent.py`, `historical_agent.py`).

### 7.1 Shared execution contract (`base_agent.py`)

Every specialist follows the same sequence:

1. **Availability gate.** `is_source_available(context)` checks the
   corresponding collector's `status`; if it isn't `"success"`, the LLM
   is skipped entirely and a deterministic `{status:"unavailable",
   confidence:0}` output is returned. This prevents the model from
   confidently analyzing a missing/failed data source.
2. **Provider resolution.** Each agent has a `provider` class attribute
   that takes priority over `app/utils/provider_config.py`'s
   component-based default (see table below).
3. **Generate + parse**, with a **retry-once-on-empty** safeguard: if the
   first response comes back with empty `analysis`/`risks`/
   `opportunities` — a documented, observed failure mode of the local
   `qwen3:4b` model, which can echo the JSON schema template back
   verbatim instead of analyzing the data — the agent retries once with
   a corrective prompt at a higher temperature (0.6). Still empty after
   two attempts → the specialist reports itself `"unavailable"` at
   confidence 0, rather than passing through a confident-looking empty
   finding.
4. Returns a `SpecialistOutput`: `{agent, status, analysis, summary,
   risks, opportunities, confidence, metadata}`.

### 7.2 Provider assignment (actual, verified from source)

| Agent | Component | Provider (hardcoded) | Why |
|---|---|---|---|
| WeatherAgent | weather | **Ollama** (`qwen3:4b`, local) | Reliable on Ollama; kept local |
| SoilAgent | soil | **Ollama** (local) | Reliable on Ollama; kept local |
| SatelliteAgent | satellite | **Groq** (`openai/gpt-oss-120b`, cloud) | Switched from Ollama after it consistently echoed the empty schema template instead of analyzing NDVI/NDWI/SAVI data (§11) |
| MarketAgent | market | **Groq** | Always cloud-routed |
| HistoricalAgent | historical | **Groq** | Switched from Ollama after its prompt (crop profile + full context + historical records) exceeded `qwen3:4b`'s 4,096-token context window (§11) |
| RecommendationAgent | recommendation | Groq (via `provider_config` default, no hardcoded override) | — |

Note: `app/utils/provider_config.py`'s `DEFAULT_PROVIDERS` dict still
lists Satellite/Historical as Ollama-default — the hardcoded class
attributes on the agents themselves override this and win, which is
worth knowing if you're tracing provider behavior from that config file
alone.

### 7.3 Executor flow (`executor.py`)

For each specialist in the plan: **TRUSTAI pre-execution review**
(`trustai.review(agent_name)`) runs first — a `"reject"` decision skips
the LLM call entirely (`status:"rejected"`). After execution, **TRUSTAI
post-execution recording** (`trustai.record_outcome(agent_name, result)`)
updates that agent's Bayesian trust posterior and attaches a
`GovernanceRecord` to `result["governance"]`.

After all specialists run, `executor.execute()` continues the pipeline:
successful specialist outputs → collaborative reasoning → executive
decision → recommendation → continuous learning → explanation — each
gated by the same TRUSTAI pre/post review pattern for the
Executive/Recommendation stages.

---

## 8. Stage 6 — Collaborative Reasoning

**File:** `app/reasoning/collaborative_engine.py`, using
`evidence_graph.py`, `conflict_detector.py`, `consensus.py`,
`confidence_fusion.py`.

Pipeline: **Evidence Graph → Conflict Detection → Consensus → Confidence
Fusion → Gemini synthesis** (with a deterministic fallback).

- **Evidence graph**: wraps each successful specialist output as an
  `EvidenceNode(agent, analysis, risks, opportunities, confidence,
  metadata)`.
- **Conflict detection**: a narrow, currently single-rule heuristic — if
  one agent's risks contain the literal string `"High crop water
  stress"` while another's analysis contains `"Heavy rainfall
  expected"`, it flags a conflict. This is not general contradiction
  detection; it's a specific, string-matched pattern.
- **Consensus**: deterministic — unions and de-duplicates all risks and
  opportunities across every agent; `agreement_score` is currently a
  fixed `1.0` (not computed from actual agreement).
- **Confidence fusion**: a fixed-weight average
  (`{Weather:0.25, Soil:0.25, Satellite:0.35, Market:0.15}`;
  HistoricalAgent falls through to the 0.25 default weight since it has
  no explicit entry).
- **Gemini call**: sends the evidence graph and compact context to
  Gemini (`gemini-3.6-flash`), asking for `{summary, consensus,
  merged_risks, merged_opportunities, conflicts, confidence}`. On any
  failure, falls back to repackaging the deterministic consensus/
  conflicts/confidence computed above, explicitly labeled
  `"Deterministic consensus generated because Gemini reasoning was
  unavailable."`

Returns a `CollaborativeReasoning` dataclass:
`{summary, consensus, merged_risks, merged_opportunities, conflicts,
confidence, evidence, metadata:{agents, agent_count,
llm_provider:"gemini"}}`.

---

## 9. Stage 7 — Executive Decision

**Files:** `app/executive/executive_agent.py`, `executive_engine.py`,
`priority_engine.py`, `impact_estimator.py`, `summary_generator.py`,
`executive_models.py`.

**This stage makes no LLM call at all** — it is a deterministic rule
engine over the collaborative-reasoning output. (`executor.py`'s own
statistics field labels this stage `"Groq"`, which is a stale/aspirational
label, not what actually executes — worth knowing if you're
cross-referencing that field.)

- **`priority_engine.py`**: keyword-scans `reasoning.merged_risks` for
  known phrases (water stress, vegetation, rainfall, nitrogen, organic
  carbon, soil texture, market), accumulates a severity score, and maps
  it to a priority level (P1–P4), risk level (Critical/High/Moderate/
  Low), and urgency via fixed thresholds. Produces a list of
  `ExecutivePriority` entries with pre-written `owner`/`action` text per
  issue type.
- **`impact_estimator.py`**: four independent 100-point scores
  (agronomic, economic, environmental, operational), each decremented by
  fixed penalties for specific risk keywords, market trend, and satellite
  water-stress/soil-exposure flags, then labeled Excellent/Good/
  Moderate/Poor by score band. Also derives `yield_risk` and
  `profitability`.
- **`summary_generator.py`**: pure string templating over the context,
  priorities, and impact — no model call.
- **`executive_engine.py`**: orchestrates the three above, then
  `infer_decision()` picks the headline decision via a plain if/elif
  chain over risk substrings (`"water stress"` → *"Immediate
  Irrigation"*; `"vegetation"` → *"Field Inspection"*; `"nitrogen"` →
  *"Apply Nitrogen Fertilizer"*; `"organic carbon"` → *"Apply Organic
  Manure"*; else market trend `"Increasing"` → *"Prepare for Harvest and
  Selling"*; otherwise *"Continue Monitoring"*). The decision's
  `confidence` is copied directly from the reasoning stage's confidence.

Output: `{decision, priority, urgency, risk_level, action_order,
priorities:[...], impact:{agronomic,economic,environmental,operational,
yield_risk,profitability,expected_benefit}, summary:{executive,business,
technical,justification}, supporting_evidence, confidence}`.

---

## 10. Stage 8 — Recommendation

**File:** `app/agents/recommendation_agent.py`

This stage **does** call an LLM (Groq, via the `provider_config` default
for `component="recommendation"`). It builds a compact prompt — crop
profile plus summarized farm context (via `app/utils/context_summary.py`)
plus a truncated digest of the reasoning and executive-decision fields —
specifically sized to fit within Groq's per-minute token budget (a full,
untruncated context previously blew through that allowance).

Schema requested: `{recommendation, priority, justification, actions:[],
expected_outcome, monitoring_plan:[], confidence}`.

**On LLM failure**, falls back to a deterministic restatement of the
executive decision — actions derived directly from the executive
priorities/merged risks rather than freshly reasoned — at a
deliberately **reduced confidence of 0.35** and
`generation_mode:"deterministic_fallback"`, so downstream governance can
see the difference between a reasoned answer and a restated one.

Final dict also carries `agent, status, executive_decision,
executive_priority, generation_mode`.

---

## 11. Stage 9 — Explainability

**File:** `app/explainability/explanation_engine.py`, orchestrating
`decision_trace_builder.py`, `evidence_aggregator.py`,
`confidence_explainer.py`, `alternative_generator.py`,
`limitation_generator.py`, `monitoring_generator.py`.

Builds a full explainability report combining deterministic artifacts
(computed in Python, always present regardless of LLM availability) with
an LLM-generated farmer-facing narrative:

- **`decision_trace_builder`**: a chronological, causal trace —
  specialist findings → ranked evidence → collaborative reasoning →
  executive decision → recommendation — each step annotated with what
  influenced the next.
- **`evidence_aggregator`**: ranks every piece of specialist evidence by
  a weighted score of confidence, source reliability, decision relevance,
  and evidence type, producing a `ranked_evidence` list plus a
  `source_summary`.
- **`confidence_explainer`**: breaks the overall confidence down by
  source.
- **`alternative_generator`**: produces context-aware rejected
  alternatives (what else could have been recommended, and why it
  wasn't).
- **`limitation_generator`**: runtime-aware limitations — flags things
  like synthetic (not live) data provenance, high satellite cloud cover,
  or missing sources explicitly, rather than silently ignoring them.
- **`monitoring_generator`**: a structured post-recommendation
  monitoring plan (`{source, parameter, frequency, reason}` per item).

The LLM call (Groq) generates only the narrative fields (`executive_
summary, explanation, reasoning_summary, decision_trace_summary,
confidence_explanation, farmer_message`) — the structured artifacts above
are always deterministic and get attached regardless of whether that LLM
call succeeds. On failure, a deterministic fallback narrative is
generated instead, and `generation_mode` reflects which path was used.

Output is an `Explanation` dataclass with all of the above fields plus
`overall_confidence`.

---

## 12. Stage 10 — Governance (TRUSTAI + Continuous Learning)

**Files:** `app/governance/trustai.py`, `trust_engine.py`,
`risk_engine.py`, `decision_engine.py`, `evidence.py`, `models.py`,
`trust_state.py`, `audit_logger.py`; `app/learning/
continuous_learning_engine.py`.

TRUSTAI is a **Beta-Bernoulli Bayesian trust model**: each agent has a
posterior `Beta(α, β)` over its reliability, starting from a
weakly-informative prior (α=2, β=2 per category). Every outcome (success/
failure, weighted by evidence quality) updates that posterior via the
standard conjugate update (`α ← α + successes`, `β ← β + failures`).

- **Pre-execution review** (`trustai.review(agent_name)`): computes the
  current posterior mean, a category-level risk assessment, and an
  expected-utility comparison across `auto_execute` / `human_review` /
  `reject`, returning whichever action maximizes expected utility. A
  `"reject"` here skips that agent's execution entirely.
- **Post-execution recording** (`trustai.record_outcome`): converts the
  actual result into evidence (success/failure, weighted), updates the
  posterior, and re-runs the same risk/decision computation for the
  audit log.
- **Trust snapshot** (`trustai.snapshot()`): returns
  `{agent_name: {category, trust_mean, trust_std}}` for every known
  agent — this is what populates the dashboard's TRUSTAI table.

State persists to `app/governance/state/trust_state.json` across runs,
so trust posteriors genuinely evolve over the life of the service, not
just within one request.

**Continuous learning** (`app/learning/continuous_learning_engine.py`) is
a second, crop-keyed instance of the *same* governance machinery
(imports the same `TrustEngine`/`risk_engine`/`decision_engine` classes),
persisting separately to `app/governance/state/crop_learning_state.json`
under a fixed `RISK_CATEGORY = "recommendation"`. It runs unconditionally
after every recommendation and is explicitly documented in its own
source as a proxy for "pipeline maturity per crop" (was the answer
LLM-reasoned or a fallback, high or low confidence) — **not** real
agronomic-outcome learning; there is no farmer-feedback channel feeding
it. Its output populates `execution.governance.crop_learning` in the
final response.

The final `governance` block in the API response:
`{agent_trust: {...snapshot...}, crop_learning: {crop, trust_mean,
decision, all_crops}, recommendation_requires_review: bool,
recommendation_rejected: bool}`.

---

## 13. Output — The Full API Response

`POST /api/recommend` returns (top-level keys):

```
{
  "query": "the original user query",
  "crop_profile": { ...canonical crop profile... },
  "raw_data": { ...full collector output (weather/soil/satellite/market/historical)... },
  "context": { ...unified farm context from stage 3... },
  "plan": { "goal", "execution_plan", "confidence" },
  "reasoning": { ...CollaborativeReasoning, duplicated at top level for convenience... },
  "executive": { ...executive decision, duplicated... },
  "recommendation": { ...recommendation, duplicated... },
  "execution": {
    "goal", "execution_plan",
    "specialists": { "WeatherAgent": {...}, "SoilAgent": {...}, ... },
    "reasoning": { ... },
    "executive": { ... },
    "recommendation": { ... },
    "explanation": { ...full Explanation dataclass... },
    "governance": { "agent_trust", "crop_learning", "recommendation_requires_review", "recommendation_rejected" },
    "confidence": 0.0-1.0,
    "statistics": {
      "agents_planned", "agents_completed", "agents_failed", "agents_unavailable",
      "unavailable_agents", "planner_confidence", "reasoning_confidence",
      "executive_confidence", "explanation_confidence", "decision_trace_steps",
      "evidence_sources", "limitations", "monitoring_items",
      "planner_model", "reasoning_model", "executive_model",
      "recommendation_model", "explanation_model"
    }
  },
  "status": "success",
  "total_time": 123.4
}
```

`execution.confidence` is the single authoritative overall-confidence
number (not the top-level object, which has no `confidence` key of its
own — a detail that tripped up this project's own evaluation-analysis
scripts more than once; see `evaluation/metrics.md` §2.6).

---

## 14. Frontend Dashboard

**Files:** `frontend/index.html`, `styles.css`, `app.js` — a
dependency-free vanilla JS single-page app, served by the FastAPI process
itself at `/dashboard` (no separate build step or dev server).

The form collects crop, question, and optional latitude/longitude
(defaults fetched from `/api/defaults`), POSTs to `/api/recommend`, and
renders the response across five tabs:

- **Overview** — the headline recommendation, executive decision,
  estimated impact, farm context summary, recommended actions, and
  monitoring plan.
- **Specialists** — one card per agent: status, confidence, findings,
  and that agent's individual TRUSTAI governance decision.
- **Reasoning & Governance** — collaborative reasoning summary and
  consensus, the full TRUSTAI agent-trust table, and the crop-level
  continuous-learning state.
- **Explainability** — the causal decision trace, ranked evidence,
  limitations, and monitoring plan.
- **Raw JSON** — the complete, unmodified API response, for debugging.

It reads exactly the fields documented in §13 above — `execution.
{reasoning, executive, recommendation, explanation, governance}` and
their nested fields — confirmed by direct inspection of the render
functions.

---

## 15. Legacy and Unused Code

Several earlier project iterations remain on disk. This section exists
so nobody mistakes them for part of the live pipeline. Verified by
grepping every import path across `app/` — none of the following are
reachable from `main.py`, `agrimind_api.py`, or `dynamic_orchestrator.py`:

| Module | Superseded by | Evidence |
|---|---|---|
| `app/ai/orchestrator.py`, `pipeline.py`, `run_pipeline.py` | `app/orchestrator/dynamic_orchestrator.py` | Only imported by its own test scripts; imports the *other* legacy modules below directly |
| `app/memory/chroma_store.py`, `memory_manager.py`, `seed_memory.py` | `historical_collector.py` (plain SQLite `farm_history` table) | Only imported by `app/agents/memory_agent.py` (itself legacy) and its own test file |
| `app/fusion/bayesian_fusion.py` | `app/reasoning/confidence_fusion.py` | Only imported by the legacy `app/ai/orchestrator.py` and its own test |
| `app/agents/memory_agent.py`, `reasoning_agent.py` | `collaborative_engine.py` + `context_agent.py`/`historical_collector.py` | Only imported by legacy `app/ai/orchestrator.py` |
| `app/orchestrator/registry.py` | Executor's own inline agent registry | Zero references anywhere in `app/` — appears to be unused scaffolding, never wired in |
| `app/knowledge/crop_profiles.py` (static crop-parameter dict) | The dynamic Groq-generated + cached crop-profile system (§3) | Zero references anywhere in `app/` |
| `app/**/test_*.py` files | — | Ad-hoc standalone debug scripts, not part of any runtime path or formal test suite (the real automated tests live in the root-level `tests/` directory) |

**Not legacy, despite the name possibly suggesting otherwise:**
`app/tools/*.py` and `app/algorithms/market_ranker.py` are the live
low-level implementation underneath the collectors (§4) —
`weather_collector.py`, `soil_collector.py`, `satellite_collector.py`,
and `market_collector.py` all import directly from `app/tools/`.
`app/database/*` is live too, just for the entirely separate CRUD
subsystem (§2), not the AI pipeline.

---

## 16. Configuration Reference

Key environment variables (`.env`, loaded via `app/config/settings.py`
and `app/config/ai_settings.py`):

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_TPM` | Groq cloud provider — used by Planner, MarketAgent, SatelliteAgent, HistoricalAgent, RecommendationAgent, ExplanationEngine. `GROQ_TPM` paces requests against a daily/per-minute token budget. |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Gemini — used only by Collaborative Reasoning |
| `OLLAMA_URL`, `OLLAMA_MODEL` | Local Ollama server (`qwen3:4b`) — used by WeatherAgent, SoilAgent |
| `SOILGRIDS_URL`, `SOIL_LIVE_SOURCE` | ISRIC SoilGrids (no API key required). `SOIL_LIVE_SOURCE=0` forces the synthetic soil dataset. Optional: `SOILGRIDS_TIMEOUT`, `SOILGRIDS_MIN_INTERVAL` (ISRIC allows ~5 req/min), `SOILGRIDS_CACHE`, `SOILGRIDS_DEPTH` |
| `DATA_GOV_IN_API_KEY`, `MARKET_LIVE_SOURCE` | Agmarknet live mandi prices via data.gov.in (free key). `MARKET_LIVE_SOURCE=0` forces the synthetic market dataset. Optional: `AGMARKNET_RESOURCE_ID`, `AGMARKNET_STATE`, `AGMARKNET_TREND_THRESHOLD`, `AGMARKNET_HISTORY` |
| `DEFAULT_LATITUDE`, `DEFAULT_LONGITUDE` | Fallback location when the API request omits coordinates |
| `GOVERNANCE_PRIOR_ALPHA`, `GOVERNANCE_PRIOR_BETA` | TRUSTAI's weakly-informative Beta prior (default 2, 2) |
| `SQLITE_DB_PATH` | Historical-records database (separate from the crop-profile cache and the CRUD subsystem's own database) |
| `POSTGRES_*` | Only used by the separate CRUD subsystem (§2), not the AI pipeline |

Full setup and run instructions are in **[RUNBOOK.md](RUNBOOK.md)**.
Research evaluation methodology and results are in
**[evaluation/metrics.md](evaluation/metrics.md)**.
