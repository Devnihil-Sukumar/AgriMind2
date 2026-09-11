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
