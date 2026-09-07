# AgriMind — Paper-Readiness Status

Single source of truth for "where the evidence stands right now." Read
this before writing any section that cites a number, so the paper never
states something the data doesn't currently support.

---

## 1. What changed since the last full evaluation

| Fix | Before | After | Evidence |
|---|---|---|---|
| Routing ground truth was availability-blind | 40% exact-match | 60% (same data, corrected scoring) | `reports/planner_routing_improvement.md` §1 |
| Planner prompt (question-type routing rules) | 60% | 100% on benchmark, **100% (8/8) on held-out** crops/phrasings | same doc, §2-3 |
| Agent F1 conflated risk/opportunity | macro F1 0.33 (fabricated-looking zeros) | 0.78 | `metrics.py` `agent_f1_scores()` docstring |
| Specialists ran sequentially | 582s mean latency | 445.6s (measured, N=10 full benchmark) | live e2e proof: 614.7s summed specialist time inside a 423.6s wall-clock run |
| Ablation baselines ran sequentially while full_system was parallel | confounded (condition 3 slower than condition 4) | fixed: all conditions now use the same concurrency | `baselines.py` module docstring |
| Soil was 100% synthetic | `data/soil_data.csv` only | **live ISRIC SoilGrids**, CSV fallback on coverage gap | `app/services/soilgrids_service.py`, verified pH 7.4 at real coordinates |
| Market was 100% synthetic | `data/market_prices.csv` only | **live Agmarknet/data.gov.in**, CSV fallback + circuit breaker | `app/services/agmarknet_service.py` (currently on fallback — see §4) |
| Dataset was N=10, 7 phrasings, 6/7 perturbation types | narrow | **N=50**, 40 phrasings, 7/7 perturbation types, includes a documented capability-gap probe (soil pH) | `evaluation_latest/dataset/build_dataset.py` |
| Evaluator could silently bank quota-degraded runs | undetected | `evaluator.is_degraded()` checks recommendation mode, specialist status, AND reasoning-stage fallback text | `tests/test_evaluator_quality_gate.py` (12 tests) |

Every one of these is a verified, tested change — not a claim. 33 tests
pass across `test_specialist_parallelism.py`, `test_live_data_sources.py`,
`test_evaluator_quality_gate.py`.

---

## 2. Current data collection state (as of this writing)

**N=11 of 50 clean `full_system` scenarios banked.** All 11 verified via
`evaluator.is_degraded()` — real LLM specialist calls, real Gemini
reasoning, no failed/rejected specialists.

The other 39 have not run yet or were correctly excluded as degraded
(quota-starved) and will re-run automatically on the next resume.

**Blocking constraint:** two independent daily quotas gate this, and
both are exhausted as of this writing:

| Provider | Used for | Daily limit | Status |
|---|---|---|---|
| Groq (`openai/gpt-oss-120b`) | Planner, specialists (Satellite/Market/Historical), Recommendation, Explanation | 200,000 tokens/day | Exhausted (199,656/200,000) |
| Gemini (`gemini-3.6-flash`) | Collaborative Reasoning | 20 requests/day (free tier) | Exhausted |

Gemini's 20/day is the tighter ceiling in practice — expect roughly
15-20 clean scenarios per day once both reset, so completing the
remaining 39 realistically needs **2-3 more days of resumes**, run via:

```bash
venv/Scripts/python.exe -u evaluation_latest/evaluator.py --conditions full_system
```

**DO NOT run `compute_and_report.py` while either quota is exhausted.**
It makes ~30+ additional Groq calls for the LLM-judge metrics (Agent F1,
Recommendation Quality, Hallucination Rate); attempting it against a
dead quota was tried during this session and failed on the first call.
Confirm headroom first:

```bash
venv/Scripts/python.exe -c "from app.utils.groq_client import groq_client; groq_client.generate(prompt='OK', max_tokens=2000)"
```

---

## 3. What the currently-published report reflects (stale, will be replaced)

`reports/final_report.md`, Tables 1-3, and Figures 1-2 currently reflect
the **N=10 pre-expansion dataset** (before this session's dataset
expansion to N=50) — they are the last numbers computed on quota that
was actually available. Table 4 (ablation) is from the same N=10 run
and additionally predates the dataset expansion by design (ablation
conditions were not re-run against the 50-scenario set this session).

**Do not cite these N=10 numbers in the paper as final** — they exist
only as the last-known-good snapshot until N=50 completes. Once 50/50
full_system scenarios are clean, run `compute_and_report.py` to
regenerate Tables 1-3 and Figures 1-2 for real. Table 4 needs conditions
1-3 (`single_agent`, `multi_no_reasoning`, `multi_with_reasoning`)
re-run against the same 50-scenario set separately:

```bash
venv/Scripts/python.exe -u evaluation_latest/evaluator.py
# (all four conditions; will skip full_system pairs already banked)
```

---

## 4. Live data source status (production pipeline, separate from the benchmark)

The benchmark evaluates the reasoning pipeline against fixed synthetic
fixtures by design (reproducibility requires a controlled,
non-changing input — see `metrics.py`'s methodology note). The
production pipeline's live-data status is a separate, additional claim:

| Source | Status | Note |
|---|---|---|
| Weather (Open-Meteo) | live | unchanged, was already live |
| Satellite (Sentinel-2/GEE) | live | unchanged, was already live |
| **Soil (SoilGrids)** | **live**, verified | pH 7.4 measured at (10.85, 77.05); correctly falls back over coverage gaps (e.g. Coimbatore city centre) |
| **Market (Agmarknet)** | integrated, tested, **currently on fallback** | `api.data.gov.in` has had extended outages throughout this session (502s, then timeouts); circuit breaker confirmed working (0.00s skip vs ~135s of dead retries); will activate automatically once the upstream API recovers |
| Historical | local (per-farm records) | intentionally not a live-data candidate — not a public dataset |

**For the paper:** claim 4 of 5 sources are live-capable and tested;
be precise that market is currently serving from its synthetic fallback
due to an ongoing third-party outage, not a bug on AgriMind's side.

---

## 5. Known, disclosed limitations (do not let these surprise a reviewer)

- **Decision Accuracy ground truth is derived from the same closed
  6-item vocabulary the system's own executive engine uses.** Reported
  two ways as of this session: overall, and excluding 5 scenarios that
  deliberately probe a documented gap (no soil-pH decision branch
  exists). This makes the capability gap visible instead of hiding it
  inside a lower headline number — but it does not resolve the
  underlying circularity concern for a Q1 reviewer. See the standing
  review notes on this (`evaluation/metrics.md` §11 covers the
  equivalent point for the earlier evaluation).
- **No independent human/expert validation exists anywhere in either
  evaluation.** This remains the single largest gap for a top-tier
  venue and is not fixable by further engineering.
- **Three of eight benchmark metrics (Agent F1, Recommendation Quality,
  Hallucination Rate) use an LLM (Groq) as judge**, disclosed
  explicitly in every table.
- **The benchmark's false-positive space is structurally empty**: every
  scenario carries exactly one ground-truth signal for its relevant
  agent(s), so Precision is trivially 1.0 whenever an agent scores a
  true positive — Recall is the number that actually varies. Documented
  in `final_report.md`'s Limitations section.
- **Single geography** (all scenarios centred on Tamil Nadu
  coordinates), **single hardware profile** for all Ollama-routed
  latency figures.

---

## 6. Suggested paper section -> evidence map

| Paper section | Cite this |
|---|---|
| System architecture | `PROJECT_DOCUMENTATION.md` (full traced pipeline, §1-14) |
| Related work / positioning | `evaluation/metrics.md` §10 (18 papers reviewed) |
| Methodology / benchmark construction | `evaluation_latest/dataset/build_dataset.py` module docstring |
| Reliability under real failure | `evaluation/metrics.md` §3, §12 (real Groq rate-limit incidents mid-evaluation, 100% pipeline-level success throughout) |
| Governance / TRUSTAI validation | `evaluation/metrics.md` §5, §9 (ablation shows disabling the reject-gate never improved outcomes) |
| Main results table | `evaluation_latest/reports/table1_overall.md` (regenerate at N=50 before citing) |
| Per-agent breakdown | `table2_agents.md`, `table1b_routing.md` |
| Ablation study | `table4_ablation.md` (regenerate against N=50 before citing) |
| Routing methodology fix (a citable finding in its own right — "we found and corrected our own evaluation's blind spot") | `planner_routing_improvement.md` |
| Limitations | §5 above, plus `final_report.md`'s own Limitations section |

---

## 7. Immediate next actions, in order

1. Wait for Groq + Gemini daily quotas to reset (both exhausted as of
   this writing).
2. Resume `evaluator.py --conditions full_system` daily until 50/50
   clean (check with `evaluator.is_degraded()`, not just file count —
   see §2's warning).
3. Once N=50 full_system is complete, run `compute_and_report.py` to
   regenerate Tables 1-3 and Figures 1-2.
4. Run the full 4-condition sweep (`evaluator.py`, no `--conditions`
   flag) to refresh Table 4's ablation against the same N=50 scenarios.
5. Re-verify all 33 tests still pass, do a final honest read-through of
   `final_report.md`'s Limitations section, then begin drafting.
