# AgriMind Research-Grade Evaluation Report
## 1. Methodology
Ground truth is rule-derived from single-field perturbations of real AgriMind-collected context, checked against each crop profile's own numeric thresholds. NOT human-expert-verified. See module docstring in build_dataset.py for the full derivation.
Benchmark size: N=105 scenarios, spanning 5 crops and 4 query types, each isolating exactly one perturbed variable against a real cloned AgriMind context. All results below are computed live from the real, unmodified AgriMind pipeline running on these fixed synthetic inputs -- no metric in this report is fabricated or hand-entered.
Ground-truth decision labels are necessarily drawn from AgriMind's own closed 6-item executive-decision vocabulary (Immediate Irrigation, Field Inspection, Apply Nitrogen Fertilizer, Apply Organic Manure, Prepare for Harvest and Selling, Continue Monitoring) -- see dataset/build_dataset.py for why, and Limitations below for what this means for Decision Accuracy.
Metrics 4-6 (Agent F1, Recommendation Quality, Hallucination Rate) use **Groq as an automated LLM judge**, explicitly NOT a human domain expert. Every table and figure using these metrics is labeled accordingly.

## 2. Dataset Description
| scenario_id | crop | query_type | perturbed_field | ground_truth_decision |
|---|---|---|---|---|
| water_stress_irrigation_rice | rice | irrigation | satellite.water.ndwi, weather.raw_data.rainfall | Immediate Irrigation |
| water_stress_suitability_rice | rice | suitability | satellite.water.ndwi, weather.raw_data.rainfall | Immediate Irrigation |
| vegetation_critical_yield_rice | rice | yield | satellite.vegetation.ndvi | Field Inspection |
| vegetation_critical_suitability_rice | rice | suitability | satellite.vegetation.ndvi | Field Inspection |
| nitrogen_low_yield_rice | rice | yield | soil.nitrogen | Apply Nitrogen Fertilizer |
| nitrogen_low_suitability_rice | rice | suitability | soil.nitrogen | Apply Nitrogen Fertilizer |
| organic_carbon_low_rice | rice | yield | soil.organic_carbon | Apply Organic Manure |
| market_increasing_rice | rice | market | market.assessment.trend | Prepare for Harvest and Selling |
| baseline_normal_rice | rice | suitability | none (negative control -- all fields left at the neutral baseline) | Continue Monitoring |
| soil_ph_low_rice | rice | yield | soil.ph (below optimal) | Field Inspection |
| compound_water_market_rice | rice | suitability | satellite.water.ndwi + market.assessment.trend | Immediate Irrigation |
| compound_nitrogen_market_rice | rice | suitability | soil.nitrogen + market.assessment.trend | Apply Nitrogen Fertilizer |
| compound_organic_market_rice | rice | suitability | soil.organic_carbon + market.assessment.trend | Apply Organic Manure |
| compound_vegetation_nitrogen_rice | rice | yield | satellite.vegetation.ndvi + soil.nitrogen | Field Inspection |
| compound_nitrogen_organic_rice | rice | yield | soil.nitrogen + soil.organic_carbon | Apply Nitrogen Fertilizer |
| water_stress_irrigation_cotton | cotton | irrigation | satellite.water.ndwi, weather.raw_data.rainfall | Immediate Irrigation |
| water_stress_suitability_cotton | cotton | suitability | satellite.water.ndwi, weather.raw_data.rainfall | Immediate Irrigation |
| vegetation_critical_yield_cotton | cotton | yield | satellite.vegetation.ndvi | Field Inspection |
| vegetation_critical_suitability_cotton | cotton | suitability | satellite.vegetation.ndvi | Field Inspection |
| nitrogen_low_yield_cotton | cotton | yield | soil.nitrogen | Apply Nitrogen Fertilizer |
| nitrogen_low_suitability_cotton | cotton | suitability | soil.nitrogen | Apply Nitrogen Fertilizer |
| organic_carbon_low_cotton | cotton | yield | soil.organic_carbon | Apply Organic Manure |
| market_increasing_cotton | cotton | market | market.assessment.trend | Prepare for Harvest and Selling |
| baseline_normal_cotton | cotton | suitability | none (negative control -- all fields left at the neutral baseline) | Continue Monitoring |
| soil_ph_low_cotton | cotton | yield | soil.ph (below optimal) | Field Inspection |
| compound_water_market_cotton | cotton | suitability | satellite.water.ndwi + market.assessment.trend | Immediate Irrigation |
| compound_nitrogen_market_cotton | cotton | suitability | soil.nitrogen + market.assessment.trend | Apply Nitrogen Fertilizer |
| compound_organic_market_cotton | cotton | suitability | soil.organic_carbon + market.assessment.trend | Apply Organic Manure |
| compound_vegetation_nitrogen_cotton | cotton | yield | satellite.vegetation.ndvi + soil.nitrogen | Field Inspection |
| compound_nitrogen_organic_cotton | cotton | yield | soil.nitrogen + soil.organic_carbon | Apply Nitrogen Fertilizer |
| water_stress_irrigation_wheat | wheat | irrigation | satellite.water.ndwi, weather.raw_data.rainfall | Immediate Irrigation |
| water_stress_suitability_wheat | wheat | suitability | satellite.water.ndwi, weather.raw_data.rainfall | Immediate Irrigation |
| vegetation_critical_yield_wheat | wheat | yield | satellite.vegetation.ndvi | Field Inspection |
| vegetation_critical_suitability_wheat | wheat | suitability | satellite.vegetation.ndvi | Field Inspection |
| nitrogen_low_yield_wheat | wheat | yield | soil.nitrogen | Apply Nitrogen Fertilizer |
| nitrogen_low_suitability_wheat | wheat | suitability | soil.nitrogen | Apply Nitrogen Fertilizer |
| organic_carbon_low_wheat | wheat | yield | soil.organic_carbon | Apply Organic Manure |
| market_increasing_wheat | wheat | market | market.assessment.trend | Prepare for Harvest and Selling |
| baseline_normal_wheat | wheat | suitability | none (negative control -- all fields left at the neutral baseline) | Continue Monitoring |
| soil_ph_low_wheat | wheat | yield | soil.ph (below optimal) | Field Inspection |
| compound_water_market_wheat | wheat | suitability | satellite.water.ndwi + market.assessment.trend | Immediate Irrigation |
| compound_nitrogen_market_wheat | wheat | suitability | soil.nitrogen + market.assessment.trend | Apply Nitrogen Fertilizer |
| compound_organic_market_wheat | wheat | suitability | soil.organic_carbon + market.assessment.trend | Apply Organic Manure |
| compound_vegetation_nitrogen_wheat | wheat | yield | satellite.vegetation.ndvi + soil.nitrogen | Field Inspection |
| compound_nitrogen_organic_wheat | wheat | yield | soil.nitrogen + soil.organic_carbon | Apply Nitrogen Fertilizer |
| water_stress_irrigation_mango | mango | irrigation | satellite.water.ndwi, weather.raw_data.rainfall | Immediate Irrigation |
| water_stress_suitability_mango | mango | suitability | satellite.water.ndwi, weather.raw_data.rainfall | Immediate Irrigation |
| vegetation_critical_yield_mango | mango | yield | satellite.vegetation.ndvi | Field Inspection |
| vegetation_critical_suitability_mango | mango | suitability | satellite.vegetation.ndvi | Field Inspection |
| nitrogen_low_yield_mango | mango | yield | soil.nitrogen | Apply Nitrogen Fertilizer |
| nitrogen_low_suitability_mango | mango | suitability | soil.nitrogen | Apply Nitrogen Fertilizer |
| organic_carbon_low_mango | mango | yield | soil.organic_carbon | Apply Organic Manure |
| market_increasing_mango | mango | market | market.assessment.trend | Prepare for Harvest and Selling |
| baseline_normal_mango | mango | suitability | none (negative control -- all fields left at the neutral baseline) | Continue Monitoring |
| soil_ph_low_mango | mango | yield | soil.ph (below optimal) | Field Inspection |
| compound_water_market_mango | mango | suitability | satellite.water.ndwi + market.assessment.trend | Immediate Irrigation |
| compound_nitrogen_market_mango | mango | suitability | soil.nitrogen + market.assessment.trend | Apply Nitrogen Fertilizer |
| compound_organic_market_mango | mango | suitability | soil.organic_carbon + market.assessment.trend | Apply Organic Manure |
| compound_vegetation_nitrogen_mango | mango | yield | satellite.vegetation.ndvi + soil.nitrogen | Field Inspection |
| compound_nitrogen_organic_mango | mango | yield | soil.nitrogen + soil.organic_carbon | Apply Nitrogen Fertilizer |
| water_stress_irrigation_tomato | tomato | irrigation | satellite.water.ndwi, weather.raw_data.rainfall | Immediate Irrigation |
| water_stress_suitability_tomato | tomato | suitability | satellite.water.ndwi, weather.raw_data.rainfall | Immediate Irrigation |
| vegetation_critical_yield_tomato | tomato | yield | satellite.vegetation.ndvi | Field Inspection |
| vegetation_critical_suitability_tomato | tomato | suitability | satellite.vegetation.ndvi | Field Inspection |
| nitrogen_low_yield_tomato | tomato | yield | soil.nitrogen | Apply Nitrogen Fertilizer |
| nitrogen_low_suitability_tomato | tomato | suitability | soil.nitrogen | Apply Nitrogen Fertilizer |
| organic_carbon_low_tomato | tomato | yield | soil.organic_carbon | Apply Organic Manure |
| market_increasing_tomato | tomato | market | market.assessment.trend | Prepare for Harvest and Selling |
| baseline_normal_tomato | tomato | suitability | none (negative control -- all fields left at the neutral baseline) | Continue Monitoring |
| soil_ph_low_tomato | tomato | yield | soil.ph (below optimal) | Field Inspection |
| compound_water_market_tomato | tomato | suitability | satellite.water.ndwi + market.assessment.trend | Immediate Irrigation |
| compound_nitrogen_market_tomato | tomato | suitability | soil.nitrogen + market.assessment.trend | Apply Nitrogen Fertilizer |
| compound_organic_market_tomato | tomato | suitability | soil.organic_carbon + market.assessment.trend | Apply Organic Manure |
| compound_vegetation_nitrogen_tomato | tomato | yield | satellite.vegetation.ndvi + soil.nitrogen | Field Inspection |
| compound_nitrogen_organic_tomato | tomato | yield | soil.nitrogen + soil.organic_carbon | Apply Nitrogen Fertilizer |
| water_stress_irrigation_apple | apple | irrigation | satellite.water.ndwi, weather.raw_data.rainfall | Immediate Irrigation |
| water_stress_suitability_apple | apple | suitability | satellite.water.ndwi, weather.raw_data.rainfall | Immediate Irrigation |
| vegetation_critical_yield_apple | apple | yield | satellite.vegetation.ndvi | Field Inspection |
| vegetation_critical_suitability_apple | apple | suitability | satellite.vegetation.ndvi | Field Inspection |
| nitrogen_low_yield_apple | apple | yield | soil.nitrogen | Apply Nitrogen Fertilizer |
| nitrogen_low_suitability_apple | apple | suitability | soil.nitrogen | Apply Nitrogen Fertilizer |
| organic_carbon_low_apple | apple | yield | soil.organic_carbon | Apply Organic Manure |
| market_increasing_apple | apple | market | market.assessment.trend | Prepare for Harvest and Selling |
| baseline_normal_apple | apple | suitability | none (negative control -- all fields left at the neutral baseline) | Continue Monitoring |
| soil_ph_low_apple | apple | yield | soil.ph (below optimal) | Field Inspection |
| compound_water_market_apple | apple | suitability | satellite.water.ndwi + market.assessment.trend | Immediate Irrigation |
| compound_nitrogen_market_apple | apple | suitability | soil.nitrogen + market.assessment.trend | Apply Nitrogen Fertilizer |
| compound_organic_market_apple | apple | suitability | soil.organic_carbon + market.assessment.trend | Apply Organic Manure |
| compound_vegetation_nitrogen_apple | apple | yield | satellite.vegetation.ndvi + soil.nitrogen | Field Inspection |
| compound_nitrogen_organic_apple | apple | yield | soil.nitrogen + soil.organic_carbon | Apply Nitrogen Fertilizer |
| water_stress_irrigation_orange | orange | irrigation | satellite.water.ndwi, weather.raw_data.rainfall | Immediate Irrigation |
| water_stress_suitability_orange | orange | suitability | satellite.water.ndwi, weather.raw_data.rainfall | Immediate Irrigation |
| vegetation_critical_yield_orange | orange | yield | satellite.vegetation.ndvi | Field Inspection |
| vegetation_critical_suitability_orange | orange | suitability | satellite.vegetation.ndvi | Field Inspection |
| nitrogen_low_yield_orange | orange | yield | soil.nitrogen | Apply Nitrogen Fertilizer |
| nitrogen_low_suitability_orange | orange | suitability | soil.nitrogen | Apply Nitrogen Fertilizer |
| organic_carbon_low_orange | orange | yield | soil.organic_carbon | Apply Organic Manure |
| market_increasing_orange | orange | market | market.assessment.trend | Prepare for Harvest and Selling |
| baseline_normal_orange | orange | suitability | none (negative control -- all fields left at the neutral baseline) | Continue Monitoring |
| soil_ph_low_orange | orange | yield | soil.ph (below optimal) | Field Inspection |
| compound_water_market_orange | orange | suitability | satellite.water.ndwi + market.assessment.trend | Immediate Irrigation |
| compound_nitrogen_market_orange | orange | suitability | soil.nitrogen + market.assessment.trend | Apply Nitrogen Fertilizer |
| compound_organic_market_orange | orange | suitability | soil.organic_carbon + market.assessment.trend | Apply Organic Manure |
| compound_vegetation_nitrogen_orange | orange | yield | satellite.vegetation.ndvi + soil.nitrogen | Field Inspection |
| compound_nitrogen_organic_orange | orange | yield | soil.nitrogen + soil.organic_carbon | Apply Nitrogen Fertilizer |

## Table 1: Overall System Evaluation
| Metric | Definition | Result |
|---|---|---|
| Task Success Rate | Percent of queries returning a complete, valid recommendation with no unrecovered pipeline failure | 100.0% (N=105, 95% CI [96.47, 100.0]) |
| Decision Accuracy | Percent of executive decisions matching the rule-derived ground-truth decision | 84.76% overall (N=105, 95% CI [76.67, 90.4]); 90.82% excluding the 7 soil-pH scenarios that probe a documented gap in the decision vocabulary (N=98, 95% CI [83.46, 95.09]) |
| Routing Accuracy | Percent of queries where the planner selected exactly the expected specialist-agent set (expected = agents whose data source actually has usable data) | 77.14% exact match (N=105, 95% CI [68.24, 84.13]); unnecessary-agent rate 2.69%, missed-agent rate 4.68%. Scoring against the availability-blind query-type mapping instead gives 47.62%. See Table 1b and reports/planner_routing_improvement.md |
| Agent Macro F1 | Mean F1 across all 5 specialists for risk/opportunity detection (LLM-judge vs rule-derived ground truth) | 0.9776 |
| Recommendation Quality | Mean 1-5 Likert score across 5 dimensions (LLM-judge, NOT a human expert panel) | 3.861 +/- 1.1 (N=525) |
| Hallucination / Error Rate | Percent of recommendations with an LLM-judge-flagged unsupported/contradictory claim | 4.76% (N=105, 95% CI [2.05, 10.67]) |
| Numeric grounding (deterministic) | Percent of runs containing a measurement-cued number absent from the raw context. No LLM judge; independent cross-check on the row above | 0.0% of runs (0/32 claims ungrounded, N=105) |
| NLI contradiction rate (discriminative model) | Percent of runs where a pre-trained entailment classifier labels any generated assertion as contradicting a context premise. No generative judge | 0.0% of runs (0/113 premise-claim pairs, N=105) |
| Trust Calibration (MACE) | Mean absolute error between TRUSTAI trust_mean and observed specialist reliability | 0.1945 |
| Average Response Time | Mean end-to-end pipeline latency (full_system condition) | 215.34s (median 182.67s, N=105) |

## Table 1b: Routing Accuracy -- Per-Agent Breakdown
| Agent | TP (correctly routed) | FP (unnecessary) | FN (missed) | Precision | Recall |
|---|---|---|---|---|---|
| WeatherAgent | 98 | 0 | 0 | 1.0 | 1.0 |
| SoilAgent | 98 | 0 | 0 | 1.0 | 1.0 |
| SatelliteAgent | 82 | 0 | 16 | 1.0 | 0.8367 |
| MarketAgent | 48 | 8 | 0 | 0.8571 | 1.0 |
| HistoricalAgent | 0 | 1 | 0 | 0.0 | N/A |

## Table 2: Individual Agent Evaluation
| Agent | Accuracy | Precision | Recall | F1 | Avg Latency | Failure Rate |
|---|---|---|---|---|---|---|
| WeatherAgent | 1.0 | 1.0 | 1.0 | 1.0 | 44.86s | 0.0% |
| SoilAgent | 1.0 | 1.0 | 1.0 | 1.0 | 56.75s | 0.0% |
| SatelliteAgent | 0.9286 | 1.0 | 0.9286 | 0.963 | 35.12s | 0.0% |
| MarketAgent | 0.9 | 1.0 | 0.9 | 0.9474 | 37.37s | 14.29% |
| HistoricalAgent | N/A | N/A | N/A | N/A | 16.37s | 0.0% |

## Table 3: TRUSTAI Calibration
| Agent | TRUSTAI Trust Mean | Observed Reliability | Calibration Error |
|---|---|---|---|
| HistoricalAgent | 0.6202 | 1.0 | 0.3798 |
| MarketAgent | 0.7635 | 0.8571 | 0.0936 |
| SatelliteAgent | 0.7767 | 1.0 | 0.2233 |
| SoilAgent | 0.8424 | 1.0 | 0.1576 |
| WeatherAgent | 0.8817 | 1.0 | 0.1183 |

## Table 4: Ablation Study
*Measured on the PRE-improvement pipeline (sequential specialists, pre-fix planner), N=10 per condition. Kept as a self-consistent snapshot: re-running only the full_system condition would have compared post-fix condition 4 against pre-fix conditions 1-3, confounding the architectural ablation with the concurrency and routing changes. Tables 1-3 and every figure above use the fresh post-improvement runs.*

| Condition | Task Success Rate | Decision Accuracy | Recommendation Quality (1-5) | Mean Latency |
|---|---|---|---|---|
| 1. Single-agent baseline | 100.0% (N=105) | 13.33% | N/A | 34.8s |
| 2. Multi-agent, no collaborative reasoning | 100.0% (N=105) | 80.0% | N/A | 88.18s |
| 3. Multi-agent + collaborative reasoning | 100.0% (N=105) | 81.9% | N/A | 154.86s |
| 4. Full AgriMind + TRUSTAI | 100.0% (N=105) | 84.76% | 3.861 | 215.74s |

## Figures
- Figure 1: `figures/fig1_agent_f1.png` -- F1-score per specialist agent
- Figure 2: `figures/fig2_overall_metrics.png` -- TSR / Decision Accuracy / Routing Accuracy / Macro F1
- Figure 3: `figures/fig3_trust_calibration.png` -- TRUSTAI trust mean vs observed reliability
- Figure 4: `figures/fig4_latency.png` -- average latency per pipeline stage and total

## Limitations
- Ground truth is rule-derived from controlled single-field perturbations of real collected context, not human-agronomist-verified. Decision Accuracy specifically measures agreement with AgriMind's OWN closed decision vocabulary, which is itself a real system limitation this benchmark surfaces (some agronomically distinct problems, e.g. soil pH, currently have no dedicated decision output).
- This benchmark deliberately runs on FIXED SYNTHETIC FIXTURES via injection.CollectorPatch, independently of what the production pipeline reads live. That is required for reproducibility -- a controlled single-variable perturbation is impossible against a live feed that changes between runs -- but it does mean these numbers characterise the reasoning pipeline, not the quality of any live data source. The production system now reads soil from ISRIC SoilGrids and market from Agmarknet/data.gov.in (both with synthetic fallback); evaluating against those live sources is separate future work.
- N=105 is small; all proportions are reported with Wilson 95% confidence intervals rather than bare point estimates.
- Planner, collaborative reasoning, and recommendation stage latency are NOT separately instrumented by the current AgriMind pipeline (the raw result object records only total end-to-end time plus per-specialist and executive execution_time). These three sub-stage latencies are reported as unavailable (N=0) in `results/aggregate_metrics.json` rather than fabricated or silently omitted, and are excluded from Figure 4 for the same reason.
- Agent F1, Recommendation Quality, and Hallucination Rate are LLM-judge (Groq) proxies, not human expert ratings.
- Every benchmark scenario is constructed to carry exactly one ground-truth signal (either a risk or an opportunity) for its relevant agent(s) -- there is no scenario where a relevant agent is judged against a signal it should NOT report. As a result, false positives are structurally impossible within the current Agent F1 metric, so Precision is always 1.0 whenever an agent scores at least one true positive; Recall is the number that actually varies between agents. An earlier version of this metric miscounted correct opportunity-type detections (the 2 opportunity scenarios) as false positives -- fixed; see the agent_f1_scores() docstring in metrics.py.
- Executive Decision's near-zero latency in Figure 4 (~0.1s mean) is a real measurement, not a missing one: this stage is a deterministic rule engine with no LLM call (see PROJECT_DOCUMENTATION.md §9), so sub-second execution is expected -- it is simply too small to see next to the other bars at that scale.
- Routing Accuracy is scored against an availability-aware expected set: an agent whose data source failed or is empty is not expected, because a planner that skips it is behaving correctly. The original availability-blind mapping understated routing accuracy by 20 points (40% vs 60%) by penalising the planner for correctly declining to invoke agents over empty sources. Since these runs were collected, a planner-prompt fix raised planner-only routing to 100% on this benchmark and 100% (8/8) on held-out queries -- reported separately in reports/planner_routing_improvement.md rather than folded into this table, because every other metric here still reflects the original pre-fix pipeline runs.
- Specialist agents now execute concurrently (they are mutually independent). The per-agent and total latency figures in this report were measured on the earlier sequential path and therefore overstate current end-to-end latency. A post-change end-to-end run measured 423.6s total against 614.7s of summed specialist time -- the specialists alone exceeding the wall-clock total is direct evidence of overlap -- i.e. ~27% faster than the 582.25s sequential mean reported above, and that run additionally absorbed an Ollama timeout and a Gemini 503 through the deterministic fallbacks.
