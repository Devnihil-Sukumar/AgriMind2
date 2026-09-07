"""
==========================================================================
AgriMind Research-Grade Evaluation -- NLI Contradiction Detection

A second LLM-free instrument for factual grounding, complementing the
numeric check in grounding.py.

Why
---
Three benchmark metrics (agent F1, recommendation quality, hallucination
rate) are adjudicated by a language model. That is a real weakness: a
model judging another model's output shares its blind spots, and it
cannot be treated as an independent measurement. grounding.py removes
the model from the loop but only sees fabricated NUMBERS; a fabricated
causal or categorical claim carries no digits and is invisible to it.

This module closes that gap using natural language inference. The raw
collected context is rendered as atomic premise statements; each
sentence of the generated recommendation becomes a hypothesis; a
pre-trained NLI classifier labels each (premise, hypothesis) pair as
entailment, neutral or contradiction. A hypothesis that any premise
CONTRADICTS is a factual error the system produced about evidence it was
given.

Design decisions worth stating
------------------------------
* **Contradiction, not non-entailment.** Most legitimate advisory
  sentences ("apply well-decomposed manure before the next season") are
  neutral with respect to sensor readings -- they are recommendations,
  not claims about the data. Counting non-entailment as error would
  flag nearly every actionable sentence. Only an active contradiction
  is counted.

* **Premises are generated mechanically** from the context dictionary,
  never written by hand per scenario, so the check cannot be tuned to
  produce a flattering result.

* **A confidence floor** is applied. NLI models are noisy on
  domain-specific text; only contradictions above CONTRADICTION_FLOOR
  are counted, and the raw scores are retained for audit.

The model is downloaded once from the HuggingFace hub and cached
locally. It runs on CPU.

Author : AgriMind Team
==========================================================================
"""

import os
import re

MODEL_NAME = os.getenv(
    "AGRIMIND_NLI_MODEL",
    "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
)

# Only contradictions the model is reasonably sure about are counted.
CONTRADICTION_FLOOR = float(os.getenv("AGRIMIND_NLI_FLOOR", "0.70"))

# A premise is only paired with a hypothesis when they share a topic
# term; pairing every sentence with every premise is quadratic and
# mostly noise.
TOPIC_TERMS = [
    "ph", "nitrogen", "organic carbon", "carbon", "texture", "loam",
    "clay", "sand", "silt", "cec", "bulk density",
    "ndvi", "ndwi", "vegetation", "water stress", "canopy", "satellite",
    "temperature", "humidity", "rainfall", "rain", "wind", "weather",
    "price", "market", "trend", "sell", "harvest",
    "moisture", "irrigation", "irrigate", "drainage",
]

_pipeline = None


def _get_pipeline():
    """Lazy-load so importing this module is cheap and the model is only
    fetched when a check actually runs."""
    global _pipeline
    if _pipeline is None:
        from transformers import pipeline
        _pipeline = pipeline(
            "text-classification",
            model=MODEL_NAME,
            tokenizer=MODEL_NAME,
            top_k=None,
            device=-1,          # CPU
            truncation=True,
            max_length=256,
        )
    return _pipeline


##########################################################################
# Premise construction
##########################################################################

def build_premises(context):
    """Render the collected context as atomic natural-language facts.

    Mechanical and scenario-independent: whatever the collectors
    returned becomes a statement, with no hand-authoring.
    """
    premises = []

    def add(text):
        if text:
            premises.append(text)

    soil = ((context.get("soil") or {}).get("soil")
            or (context.get("soil") or {}).get("raw_data") or {})
    if soil:
        if soil.get("ph") is not None:
            add(f"The soil pH is {soil['ph']}.")
        if soil.get("nitrogen"):
            add(f"The soil nitrogen level is {soil['nitrogen']}.")
        if soil.get("organic_carbon"):
            add(f"The soil organic carbon level is {soil['organic_carbon']}.")
        for key, label in (("sand_percent", "sand"), ("clay_percent", "clay"),
                           ("silt_percent", "silt")):
            if soil.get(key) is not None:
                add(f"The soil {label} content is {soil[key]} percent.")

    weather = (context.get("weather") or {}).get("raw_data") or {}
    if weather:
        if weather.get("temperature") is not None:
            add(f"The air temperature is {weather['temperature']} degrees Celsius.")
        if weather.get("humidity") is not None:
            add(f"The relative humidity is {weather['humidity']} percent.")
        if weather.get("rainfall") is not None:
            add(f"The recent rainfall is {weather['rainfall']} millimetres.")

    sat = context.get("satellite") or {}
    veg = sat.get("vegetation") or {}
    wat = sat.get("water") or {}
    if veg.get("ndvi") is not None:
        add(f"The NDVI vegetation index is {veg['ndvi']}.")
    if veg.get("health"):
        add(f"The crop vegetation health is {veg['health']}.")
    if wat.get("ndwi") is not None:
        add(f"The NDWI water index is {wat['ndwi']}.")
    if wat.get("stress"):
        add(f"The crop water stress level is {wat['stress']}.")

    market = context.get("market") or {}
    assessment = market.get("assessment") or {}
    if assessment.get("trend"):
        add(f"The market price trend is {assessment['trend']}.")
    nearest = market.get("nearest_market") or {}
    if nearest.get("price") is not None:
        add(f"The nearest market price is {nearest['price']} rupees per quintal.")

    return premises


##########################################################################
# Hypothesis extraction
##########################################################################

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

##########################################################################
# Prescriptive / forward-looking filter
#
# Only ASSERTIONS about the current state can contradict a sensor
# reading. Advisory text is dominated by instructions and targets, which
# legitimately name values different from the present one:
#
#   "Re-sample soil pH 10-14 days after the first lime application and
#    adjust the second dose to reach the target pH 5.5-6.5."
#
# against the premise "The soil pH is 3.2." was flagged as a
# contradiction at 0.972 by an earlier version of this check. The system
# was correct -- it was prescribing liming to RAISE pH from 3.2 toward
# 5.5-6.5 -- and the check was wrong. Counting such sentences would
# report treatment plans as hallucinations, inflating the error rate
# precisely on the scenarios where the system behaved best.
#
# Sentences are therefore excluded when they open in the imperative or
# contain target/futurity markers.
##########################################################################

PRESCRIPTIVE_OPENERS = {
    "apply", "re-sample", "resample", "recheck", "re-check", "retest",
    "re-test", "adjust", "monitor", "irrigate", "inspect", "walk",
    "incorporate", "prepare", "target", "maintain", "increase",
    "decrease", "reduce", "raise", "lower", "schedule", "plan",
    "consider", "avoid", "ensure", "continue", "repeat", "record",
    "harvest", "sell", "use", "add", "check", "review", "take",
}

TARGET_MARKERS = [
    "target", "aim ", "aim,", "goal", "desired", "to reach", "reach the",
    "should be", "should reach", "bring to", "raise to", "lower to",
    "until", "after the", "next season", "following season",
    "over the next", "within the next", "expected to",
]


def is_prescriptive(sentence):
    """True when the sentence instructs or sets a target rather than
    asserting the present state."""
    s = sentence.strip().lower()

    first = re.sub(r"^[^a-z]*", "", s).split(" ", 1)[0].strip(".,:;")
    if first in PRESCRIPTIVE_OPENERS:
        return True

    return any(marker in s for marker in TARGET_MARKERS)


def split_claims(text, min_words=4):
    """Present-tense assertions from the generated text, as candidate
    hypotheses. Prescriptive and forward-looking sentences are dropped
    (see above)."""
    if not text:
        return []
    parts = [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()]
    return [
        p for p in parts
        if len(p.split()) >= min_words and not is_prescriptive(p)
    ]


def shares_topic(premise, hypothesis):
    p, h = premise.lower(), hypothesis.lower()
    return any(t in p and t in h for t in TOPIC_TERMS)


##########################################################################
# Check
##########################################################################

def check_run(context, text):
    """Return contradiction findings for one run."""
    premises = build_premises(context)
    claims = split_claims(text)

    if not premises or not claims:
        return {"pairs_tested": 0, "contradictions": []}

    clf = _get_pipeline()

    pairs = []
    for h in claims:
        for p in premises:
            if shares_topic(p, h):
                pairs.append((p, h))

    if not pairs:
        return {"pairs_tested": 0, "contradictions": []}

    inputs = [{"text": p, "text_pair": h} for p, h in pairs]
    outputs = clf(inputs)

    contradictions = []
    for (p, h), scores in zip(pairs, outputs):
        best = {s["label"].lower(): s["score"] for s in scores}
        contra = max(
            (v for k, v in best.items() if k.startswith("contradict")),
            default=0.0,
        )
        if contra >= CONTRADICTION_FLOOR:
            contradictions.append({
                "premise": p,
                "claim": h[:200],
                "contradiction_score": round(float(contra), 3),
            })

    return {"pairs_tested": len(pairs), "contradictions": contradictions}


def nli_contradiction_rate(full_system_results):
    """Deterministic-model (non-generative) contradiction measurement
    across runs."""
    rows = []
    runs_with_contradiction = 0
    total_pairs = 0
    total_contradictions = 0
    n = 0

    for r in full_system_results:
        if r.get("status") != "success":
            continue
        n += 1

        text_parts = [(r.get("recommendation") or {}).get("recommendation")]
        actions = (r.get("recommendation") or {}).get("actions") or []
        if isinstance(actions, list):
            text_parts.extend(str(a) for a in actions)
        text = " ".join(p for p in text_parts if p)

        found = check_run(r.get("context") or {}, text)

        total_pairs += found["pairs_tested"]
        total_contradictions += len(found["contradictions"])
        if found["contradictions"]:
            runs_with_contradiction += 1

        rows.append({
            "scenario_id": r.get("scenario_id"),
            "pairs_tested": found["pairs_tested"],
            "contradictions": len(found["contradictions"]),
            "examples": found["contradictions"][:3],
        })

    return {
        "metric": "NLI Contradiction Rate (no generative judge)",
        "model": MODEL_NAME,
        "contradiction_floor": CONTRADICTION_FLOOR,
        "methodology":
            "Context rendered as atomic premises; each generated sentence "
            "is a hypothesis; a pre-trained NLI classifier labels each "
            "topically-linked pair. Only active contradictions above the "
            "confidence floor are counted -- neutral sentences are "
            "expected, since advice is not a claim about sensor data.",
        "n_runs": n,
        "runs_with_contradiction": runs_with_contradiction,
        "contradiction_run_rate_pct":
            round(100 * runs_with_contradiction / n, 2) if n else None,
        "total_pairs_tested": total_pairs,
        "total_contradictions": total_contradictions,
        "rows": rows,
    }
