"""
==========================================================================
AgriMind

Farm Context Summarizer

The full farm context carries every collector payload verbatim:
hourly weather series, the complete market table, raw SoilGrids
responses and full satellite band metadata. Dumping it into a
downstream prompt costs thousands of tokens and contributes nothing
to the decision, because the specialist agents have already reduced
that raw evidence into analyses.

This module produces a decision-grade summary of the farm context for
components that reason ABOUT the decision rather than about raw
measurements: the Recommendation Agent and the Explanation Engine.

Author : AgriMind Team
==========================================================================
"""

from typing import Any, Dict

from app.utils.prompt_budget import prune, truncate_text


##########################################################################
# Helpers
##########################################################################

def _section(
    context: Dict[str, Any],
    key: str
) -> Dict[str, Any]:
    """
    Return a collector section as a dict, tolerating missing sources.
    """

    value = context.get(key)

    if isinstance(value, dict):

        return value

    return {}


def _availability(
    section: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Standard availability descriptor for one evidence source.
    """

    status = str(
        section.get(
            "status",
            "unavailable"
        )
    ).strip().lower()

    descriptor: Dict[str, Any] = {
        "available": status == "success",
        "status": status or "unavailable",
        "confidence": section.get(
            "confidence",
            0
        )
    }

    if descriptor["available"] is False:

        descriptor["reason"] = truncate_text(
            section.get(
                "error",
                "Source did not return usable data."
            ),
            200
        )

    return descriptor


##########################################################################
# Crop Profile Summary
##########################################################################

# Crop profile fields that add prompt weight without informing a
# runtime decision. Provenance and prose blocks are dropped; agronomic
# thresholds are kept.
CROP_PROFILE_NOISE_KEYS = {
    "references",
    "generated_by",
    "version",
    "family",
    "category",
    "type",
    "summary"
}


def summarize_crop_profile(
    crop_profile: Any,
    max_string_chars: int = 220,
    max_list_items: int = 5
) -> Dict[str, Any]:
    """
    Keep the agronomic thresholds a decision layer uses, drop the rest.

    A drop-list is used rather than an allow-list so that profiles with
    differing schemas (cotton, mango, rice) all survive summarization
    with their thresholds intact.
    """

    if not isinstance(crop_profile, dict):

        return {}

    kept = {
        key: value
        for key, value in crop_profile.items()
        if str(key).lower() not in CROP_PROFILE_NOISE_KEYS
        and value not in (None, "", [], {})
    }

    return prune(
        kept,
        max_list_items=max_list_items,
        max_string_chars=max_string_chars
    )


##########################################################################
# Farm Context Summary
##########################################################################

def summarize_farm_context(
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Reduce the full farm context to a compact decision-grade view.

    Raw collector payloads are dropped; assessments, headline values
    and per-source availability are kept.
    """

    if not isinstance(context, dict):

        return {}

    weather = _section(context, "weather")
    soil = _section(context, "soil")
    satellite = _section(context, "satellite")
    market = _section(context, "market")
    historical = _section(context, "historical")

    summary: Dict[str, Any] = {

        "crop": context.get("crop"),

        "location": context.get(
            "location",
            {}
        ),

        ################################################################
        # Headline indicators
        ################################################################

        "headline": {

            "weather_status": context.get("weather_status"),

            "soil_health": context.get("soil_health"),

            "vegetation_health": context.get("vegetation_health"),

            "market_trend": context.get("market_trend"),

            "historical_records": context.get("historical_records"),

            "historical_similarity": context.get("historical_similarity")

        },

        ################################################################
        # Per-source assessments
        ################################################################

        "weather": {
            **_availability(weather),
            "assessment": weather.get("assessment", {})
        },

        "soil": {
            **_availability(soil),
            "assessment": soil.get("assessment", {}),
            "properties": soil.get("soil", {})
        },

        "satellite": {
            **_availability(satellite),
            "assessment": satellite.get("assessment", {}),
            "indices": satellite.get("indices", {}),
            "imagery": satellite.get("imagery", {})
        },

        "market": {
            **_availability(market),
            "assessment": market.get("assessment", {}),
            "best_market": market.get("market"),
            "nearest_market": market.get("nearest_market"),
            "top_markets": market.get("top_markets", [])
        },

        "historical": {
            **_availability(historical),
            "record_count": context.get(
                "historical_records",
                len(
                    historical.get(
                        "records",
                        []
                    )
                    if isinstance(historical.get("records"), list)
                    else []
                )
            ),
            "similarity": context.get("historical_similarity")
        },

        ################################################################
        # Context-level synthesis
        ################################################################

        "risks": context.get("risks", []),

        "opportunities": context.get("opportunities", []),

        "confidence": context.get("confidence")

    }

    return summary


##########################################################################
# Unavailable Source Reporting
##########################################################################

def unavailable_sources(
    context: Dict[str, Any]
) -> list:
    """
    List evidence sources that did not return usable data.

    Used by runtime-aware limitations and by governance so that a
    missing source is stated explicitly rather than silently ignored.
    """

    missing = []

    for key in (
        "weather",
        "soil",
        "satellite",
        "market",
        "historical"
    ):

        section = _section(context, key)

        if not section:

            missing.append(key)

            continue

        status = str(
            section.get(
                "status",
                ""
            )
        ).strip().lower()

        if status != "success":

            missing.append(key)

    return missing
