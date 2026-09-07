# Planner Routing: Root Cause, Fix, and Held-Out Validation

This documents an upgrade made after the main benchmark run. It concerns
**Metric 3 (Routing Accuracy)** only. Every other metric in
`final_report.md` still reflects the original full-pipeline runs and is
unchanged.

---

## 1. The original number, and why it was misleading

The benchmark first reported **40.0% exact-match routing accuracy** with a
27.0% missed-agent rate. Inspecting which agents were "missed" showed the
planner was being penalised for two different things, only one of which
was its fault.

### 1a. The benchmark's ground truth ignored data availability

`expected_agents` came from a static `query_type -> agent set` mapping in
`build_dataset.py` that never asked whether a data source actually had
data. In this benchmark:

- **every** scenario clones a context whose historical table is empty
  (`record_count == 0`), and
- two scenarios additionally carry a **failed** market collection.

So the static mapping "expected" HistoricalAgent in 5 scenarios and
MarketAgent in 1 where those agents had literally nothing to analyse. The
planner correctly declined to invoke them; the benchmark scored that as a
miss.

Scoring instead against an **availability-aware** expected set (an agent
is only expected when its source has usable data) is the correct
measurement:

| Ground truth | Exact-match routing accuracy | Missed-agent rate |
|---|---|---|
| Static query-type mapping (original) | 40.0% | 27.0% |
| Availability-aware (corrected) | **60.0%** | **12.9%** |

That 20-point gap was the benchmark's blind spot, not planner error.
Implemented as `_unavailable_agents()` in `metrics.py`; both figures are
reported side by side so the size of the correction stays visible.

### 1b. A genuine planner weakness in the remaining 40%

The residual failures were real. The planner prompt defined
`MarketAgent = price/selling/profit/markets`, so a crop-**suitability**
question ("Is cotton suitable to grow here?") never matched those literal
terms and MarketAgent was skipped even when market data was available —
MarketAgent recall was 0.25. One irrigation scenario also dropped
SoilAgent, though soil moisture governs irrigation timing.

A silent-fallback explanation was checked and **ruled out**: the
deterministic fallback router stamps `confidence 0.85` and copies the
query verbatim, whereas all 10 runs recorded `0.95`/`0.92` with
paraphrased goals. The LLM planner genuinely ran; the repeated
`[Weather, Soil, Satellite]` triple was a real decision, not a fallback
artifact.

---

## 2. The fix

`app/prompts/planner_prompt.py` now states routing rules by question
type rather than by keyword matching, and codifies the
data-availability rule the planner had only been following incidentally:

- **Suitability / "should I grow this here"** -> agronomic specialists
  **plus** MarketAgent (viability is agronomic *and* economic).
- **Yield optimisation** -> agronomic specialists **only**; adding
  MarketAgent requires the question itself to mention selling, price or
  profit.
- **Irrigation timing** -> Weather, Soil and Satellite together, since
  soil moisture and water-holding capacity drive irrigation timing as
  much as rainfall does.
- **Selling / timing-of-sale** -> MarketAgent (plus HistoricalAgent when
  it has records).
- **Skip any agent whose source failed or is empty**, judged from the
  context rather than the question.

An intermediate version of this prompt over-corrected: it pulled
MarketAgent into yield queries too, trading 3 missed-agent failures for 3
unnecessary-agent failures at an unchanged 60%. That is what motivated
the explicit yield-vs-suitability distinction above.

---

## 3. Results

Routing accuracy depends only on the planner, so it was re-measured with
a **planner-only re-run** (10 planner calls) rather than a full
7-hour pipeline re-run.

| Configuration | Exact-match routing accuracy |
|---|---|
| Original planner, static ground truth | 40.0% (4/10) |
| Original planner, availability-aware ground truth | 60.0% (6/10) |
| **Improved planner, availability-aware ground truth** | **100.0% (10/10)** |

### Held-out validation (the number that actually matters)

100% on the same 10 scenarios the prompt was tuned against proves little.
The rules were therefore re-tested on **8 held-out queries** using crops
that appear nowhere in the benchmark (groundnut, banana, onion,
sugarcane, chilli, turmeric, maize, paddy) and natural phrasings written
independently of the tuning set:

| Held-out query | Expected | Planner | Match |
|---|---|---|---|
| "How can I get a better harvest from my groundnut plot?" | Weather, Soil, Satellite | Weather, Soil, Satellite | yes |
| "Would banana be a good crop to plant on this land?" | + Market | + Market | yes |
| "Where can I get the best price for my onions right now?" | Market | Market | yes |
| "Is there enough moisture or do I need to irrigate the sugarcane?" | Weather, Soil, Satellite | Weather, Soil, Satellite | yes |
| "Is this land right for growing chilli?" | + Market | + Market | yes |
| "Should I sell my turmeric now or wait a few weeks?" | Market | Market | yes |
| "My maize leaves are yellowing, what should I do about it?" | Weather, Soil, Satellite | Weather, Soil, Satellite | yes |
| "My paddy field looks dry, should I water it this week?" | Weather, Soil, Satellite | Weather, Soil, Satellite | yes |

**Held-out exact-match routing accuracy: 100.0% (8/8).**

---

## 4. Honest limitations of this result

- **N is small.** 10 tuning + 8 held-out scenarios support a directional
  claim, not a tight confidence interval.
- **The held-out expectations were authored by the same person who wrote
  the routing rules.** They follow the same agronomic logic, so this
  tests generalisation across crops and phrasings, not independence of
  judgement. An external agronomist labelling the expected agent set
  would be a stronger test.
- **This is a planner-only measurement.** The 100% figure comes from
  re-running the planning stage against the same fixtures; it is not a
  fresh end-to-end pipeline run. Every other metric in `final_report.md`
  still reflects the original pre-fix runs, and Table 1 continues to
  report the 60% availability-aware figure for that reason.
- **Availability-aware ground truth is itself a modelling choice.** It
  assumes an agent over an empty source should be skipped. That is the
  behaviour we want for latency, but a system designed to report "no
  historical data available" as an explicit finding would want the
  opposite.
