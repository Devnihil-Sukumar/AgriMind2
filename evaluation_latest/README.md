# AgriMind Research-Grade Evaluation

A reproducible benchmark evaluating the live `POST /api/recommend`
pipeline against a labeled, controlled benchmark dataset.

## Run it (single command)

```bash
venv/Scripts/python.exe evaluation_latest/run_evaluation.py
```

This builds the benchmark dataset (if not already built), runs every
`(scenario, condition)` pair through the **real, unmodified** AgriMind
pipeline (resumable -- safe to stop and re-run; only successful pairs
are skipped on resume), computes all 8 metrics, and writes tables,
figures, and the final report.

**This takes hours**, not minutes — each pair invokes real Ollama/Groq/
Gemini calls exactly as a live request would. Expect roughly 4-6 hours
for the full 10-scenario x 4-condition benchmark on typical local
Ollama hardware. Safe to interrupt (Ctrl-C or an external stop signal)
and resume later with the same command.

To only recompute tables/figures/report from whatever's already in
`results/raw/` (no new pipeline runs):

```bash
venv/Scripts/python.exe evaluation_latest/compute_and_report.py
```

## What gets evaluated

Four conditions, run on **identical synthetic input** per scenario, so
differences are attributable to architecture, not data variance:

1. **Single-agent baseline** — one specialist only, no fusion, no TRUSTAI
2. **Multi-agent, no collaborative reasoning** — real planner + all
   planned specialists, but a deterministic risk/opportunity union
   instead of the real Gemini-based collaborative reasoning stage
3. **Multi-agent + collaborative reasoning** — adds the real
   collaborative-reasoning stage back; still no TRUSTAI
4. **Full AgriMind + TRUSTAI** — the actual, unmodified
   `dynamic_orchestrator.run()`, exactly as a live API request would
   execute it

## Methodology (read before citing any number)

Ground truth is **not** human-expert-authored. Each of the 10 benchmark
scenarios clones a real context AgriMind itself collected in an earlier
evaluation (`evaluation/data/raw/*.json` — genuine weather/soil/
satellite/market data), resets every field to a neutral mid-range value,
then applies exactly **one** documented perturbation that crosses a
threshold already present in that crop's own profile (e.g. forcing soil
pH to 3.2 against rice's optimal 5.5-6.5 range). The expected decision
is expressed using AgriMind's own closed 6-item executive-decision
vocabulary — see `dataset/build_dataset.py`'s module docstring for the
full derivation and why this constraint exists.

Three of the eight metrics (**Individual Agent F1**, **Recommendation
Quality**, **Hallucination Rate**) use **Groq as an automated LLM
judge**, not a human domain expert. This is stated explicitly in every
table, figure, and report section that uses them — there was no
agricultural expert panel available for this evaluation.

Every metric report states its sample size N, and proportions are
reported with Wilson 95% confidence intervals rather than bare point
estimates, since N=10 is small.

## Files

```
evaluation_latest/
├── dataset/
│   ├── build_dataset.py       # constructs the 10 benchmark scenarios
│   └── benchmark_queries.json # the dataset itself (generated)
├── injection.py                # monkeypatches the 5 collectors with fixed synthetic data
├── baselines.py                # the 4 ablation condition runners
├── evaluator.py                # orchestration loop, checkpointed, TRUSTAI-state-safe
├── metrics.py                  # all 8 metric computations
├── compute_and_report.py       # tables + figures + final report generation
├── run_evaluation.py           # single-command entry point
├── results/
│   ├── raw/                    # one JSON per (scenario, condition) pair
│   ├── run_log.jsonl           # append-only progress log
│   ├── aggregate_metrics.json  # every metric, machine-readable
│   └── per_query_results.csv
├── figures/                    # 4 PNGs at 300 DPI
└── reports/
    ├── table1_overall.{csv,md}
    ├── table1b_routing.{csv,md}
    ├── table2_agents.{csv,md}
    ├── table3_trust_calibration.{csv,md}
    ├── table4_ablation.{csv,md}
    └── final_report.md         # methodology, results, limitations, conclusions
```

## Data-safety note

Condition 4 (`full_system`) runs the real pipeline, which means it
genuinely calls TRUSTAI — `evaluator.py` backs up
`app/governance/state/trust_state.json` and
`app/governance/state/crop_learning_state.json` before running and
restores them afterward (even on a hard stop, via a SIGTERM handler),
so this benchmark's synthetic scenarios never contaminate your
production trust state.
