"""
==========================================================================
AgriMind Research-Grade Evaluation -- Deterministic Numeric Grounding

An independent, non-LLM check on whether the generated recommendation
invents quantities that do not exist in the evidence it was given.

Why this exists
---------------
Three of the benchmark's metrics use a language model as judge. That is
disclosed, but it is a genuine weakness: an LLM judging another LLM's
output shares failure modes with it, and cannot be treated as an
objective instrument. This module provides a second, fully deterministic
measurement of the same underlying property -- factual grounding -- so
the LLM-judged hallucination rate can be corroborated (or contradicted)
by something with no model in the loop.

What it measures
----------------
A MEASUREMENT CLAIM is a number in the generated text that sits next to
a measurement cue (pH, NDVI, a percentage, a temperature, a price, and
so on). Each such number is checked against the pool of numeric values
actually present in the raw collected context. A claim is GROUNDED if
some context value matches within a relative tolerance; otherwise it is
UNGROUNDED and counted as a numeric hallucination.

What it deliberately does NOT measure
-------------------------------------
Numbers that carry no measurement cue are ignored, because agronomic
advice legitimately contains quantities that are not readings: "recheck
in 3-5 days", "apply at 2-3 week intervals". Counting those as
hallucinations would manufacture false positives, so the check is
scoped to numbers the text itself frames as observations.

This is therefore a PRECISION-ORIENTED check: it will miss non-numeric
hallucinations (a fabricated causal claim carries no digits), but a
positive finding is objective and auditable. It complements, and does
not replace, the LLM judge.

Author : AgriMind Team
==========================================================================
"""

import re

##########################################################################
# Cue vocabulary
#
# A number counts as a measurement claim only when one of these appears
# within CUE_WINDOW characters of it. Chosen to match the quantities the
# pipeline actually collects.
##########################################################################

MEASUREMENT_CUES = [
    "ph", "ndvi", "ndwi", "evi", "savi",
    "nitrogen", "organic carbon", "carbon",
    "sand", "clay", "silt", "cec", "bulk density",
    "temperature", "humidity", "rainfall", "rain", "wind", "pressure",
    "moisture", "field capacity", "wilting",
    "price", "modal", "quintal", "rupee", "rs.", "inr",
    "cloud cover", "vegetation index", "water index",
    "score", "confidence",
    "degree", "celsius", "mm", "percent", "%",
]

##########################################################################
# A number is disqualified outright when one of these sits immediately
# after it. Agronomic advice is full of legitimate quantities that are
# not readings -- "recheck in 3-5 days", "at 2-3 week intervals" -- and
# an earlier version of this check counted them as hallucinations
# because a measurement cue happened to appear elsewhere in the same
# sentence. Disqualification is applied before the cue test.
##########################################################################

EXCLUSION_TERMS = [
    "day", "days", "week", "weeks", "month", "months", "year", "years",
    "hour", "hours", "time", "times", "stage", "stages", "step", "steps",
    "interval", "intervals", "season", "seasons", "cycle", "cycles",
    "phase", "phases", "point", "points",
]

# The cue must sit close to the number; a sentence-wide window lets an
# unrelated cue validate an unrelated number.
CUE_WINDOW = 22

# Characters after the number searched for a disqualifying unit.
EXCLUSION_WINDOW = 14

# Relative tolerance when matching a claimed number to a context value.
REL_TOLERANCE = 0.02

# Numbers this small are almost always list indices, day counts or
# section numbers rather than readings.
MIN_ABS_VALUE = 0.001

##########################################################################
# The lookbehinds are load-bearing and easy to get wrong:
#   (?<!\w)     -- do not match digits embedded in an identifier
#   (?<!\d\.)   -- do not match the fractional half of a decimal, i.e.
#                  the "25" of "6.25"
# The second must test digit-then-dot rather than just dot, otherwise a
# currency prefix such as "Rs.2450" is rejected and every market price
# claim silently disappears from the audit -- which is exactly what an
# earlier version of this pattern did.
##########################################################################

NUMBER_RE = re.compile(
    r"(?<!\w)(?<!\d\.)(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)(?!\w)"
)


def _to_float(token):
    try:
        return float(token.replace(",", ""))
    except (TypeError, ValueError):
        return None


def collect_context_numbers(obj, acc=None):
    """Every numeric value anywhere in the raw collected context."""
    if acc is None:
        acc = []

    if isinstance(obj, dict):
        for v in obj.values():
            collect_context_numbers(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            collect_context_numbers(v, acc)
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, (int, float)):
        acc.append(float(obj))
    elif isinstance(obj, str):
        # numbers embedded in stringified context blocks count too
        for m in NUMBER_RE.finditer(obj):
            val = _to_float(m.group(1))
            if val is not None:
                acc.append(val)

    return acc


def extract_measurement_claims(text):
    """Numbers in `text` that sit next to a measurement cue."""
    if not text:
        return []

    lowered = text.lower()
    claims = []

    for m in NUMBER_RE.finditer(text):
        value = _to_float(m.group(1))
        if value is None or abs(value) < MIN_ABS_VALUE:
            continue

        ############################################################
        # Disqualify time horizons and ordinals before anything else.
        ############################################################

        trailing = lowered[m.end():m.end() + EXCLUSION_WINDOW]
        trailing_words = re.findall(r"[a-z]+", trailing)
        if trailing_words and trailing_words[0] in EXCLUSION_TERMS:
            continue

        ############################################################
        # Disqualify list enumeration: a small integer followed by
        # ". " and a capital letter is a numbered step, not a
        # reading. Observed in real output ("... moisture daily.
        # 7. Record harvest quantity"), where the preceding cue
        # would otherwise validate the list marker.
        ############################################################

        after = text[m.end():m.end() + 3]
        if (float(value).is_integer() and value <= 20
                and re.match(r"\.\s+[A-Z]", after)):
            continue

        start = max(0, m.start() - CUE_WINDOW)
        end = min(len(lowered), m.end() + CUE_WINDOW)
        window = lowered[start:end]

        cue = next((c for c in MEASUREMENT_CUES if c in window), None)
        if cue is None:
            continue

        claims.append({
            "value": value,
            "cue": cue,
            "snippet": text[start:end].replace("\n", " ").strip(),
        })

    return claims


def is_grounded(value, context_values, rel_tolerance=REL_TOLERANCE):
    """True when some context value matches `value` within tolerance.

    Percentages are additionally checked against their fractional form,
    since the pipeline stores some quantities as fractions (0.32) while
    the generated text may render them as percentages (32%).
    """
    candidates = {value, value / 100.0, value * 100.0}

    for cand in candidates:
        for ctx in context_values:
            if cand == 0 or ctx == 0:
                if abs(cand - ctx) < 1e-9:
                    return True
                continue
            if abs(cand - ctx) / max(abs(cand), abs(ctx)) <= rel_tolerance:
                return True

    return False


def numeric_grounding(full_system_results):
    """Deterministic counterpart to the LLM-judged hallucination rate.

    Returns the proportion of runs containing at least one ungrounded
    measurement claim, plus claim-level totals.
    """
    rows = []
    runs_with_ungrounded = 0
    total_claims = 0
    total_ungrounded = 0
    n = 0

    for r in full_system_results:

        if r.get("status") != "success":
            continue

        n += 1

        context_values = collect_context_numbers(r.get("context") or {})

        text_parts = [
            ((r.get("recommendation") or {}).get("recommendation")),
            ((r.get("executive") or {}).get("decision")),
        ]
        actions = (r.get("recommendation") or {}).get("actions") or []
        if isinstance(actions, list):
            text_parts.extend(str(a) for a in actions)

        text = " ".join(p for p in text_parts if p)

        claims = extract_measurement_claims(text)
        ungrounded = [c for c in claims
                      if not is_grounded(c["value"], context_values)]

        total_claims += len(claims)
        total_ungrounded += len(ungrounded)
        if ungrounded:
            runs_with_ungrounded += 1

        rows.append({
            "scenario_id": r.get("scenario_id"),
            "claims": len(claims),
            "ungrounded": len(ungrounded),
            "examples": [
                {"value": c["value"], "cue": c["cue"], "snippet": c["snippet"][:160]}
                for c in ungrounded[:3]
            ],
        })

    run_rate = round(100 * runs_with_ungrounded / n, 2) if n else None
    claim_rate = round(100 * total_ungrounded / total_claims, 2) if total_claims else None

    return {
        "metric": "Numeric Grounding (deterministic, no LLM judge)",
        "methodology":
            "Measurement-cued numbers in the generated text are matched "
            "against every numeric value in the raw collected context "
            f"within {REL_TOLERANCE:.0%} relative tolerance. Numbers "
            "without a measurement cue (advice horizons such as "
            "'3-5 days') are excluded by design.",
        "n_runs": n,
        "runs_with_ungrounded_claim": runs_with_ungrounded,
        "ungrounded_run_rate_pct": run_rate,
        "total_claims": total_claims,
        "total_ungrounded_claims": total_ungrounded,
        "ungrounded_claim_rate_pct": claim_rate,
        "scope_note":
            "Detects fabricated QUANTITIES only. A non-numeric fabricated "
            "claim carries no digits and is invisible to this check, so "
            "this is a lower bound on hallucination and a complement to, "
            "not a replacement for, the LLM-judged rate.",
        "rows": rows,
    }
