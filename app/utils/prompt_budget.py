"""
==========================================================================
AgriMind

Prompt Budget Utilities

Shared helpers that keep LLM prompts inside provider token limits.

Groq counts BOTH the input prompt and the requested max_tokens against
the per-minute token budget, so a 4096-token completion reservation
consumes half of an 8000 TPM allowance before a single prompt byte is
sent. These helpers exist so downstream components can:

    1. Estimate prompt cost before sending.
    2. Serialize evidence compactly instead of with indent=4.
    3. Strip bulk payloads (raw_data, long record lists).
    4. Hard-trim a finished prompt to a declared budget.

Author : AgriMind Team
==========================================================================
"""

import json
from typing import Any, Iterable, Optional


##########################################################################
# Constants
##########################################################################

# Conservative average for English + JSON text.
CHARS_PER_TOKEN = 3.6

# Keys that carry bulk payloads and never influence the final decision.
BULK_KEYS = {
    "raw_data",
    "raw_metadata",
    "raw_response",
    "hourly",
    "daily",
    "forecast_hourly",
    "all_markets",
    "geometry",
    "bands",
    "image_metadata"
}


##########################################################################
# Token Estimation
##########################################################################

def estimate_tokens(
    text: Any
) -> int:
    """
    Approximate the token count of a prompt.

    Intentionally pessimistic: it is safer to over-estimate and compress
    than to under-estimate and receive an HTTP 413.
    """

    if text is None:

        return 0

    return int(
        len(
            str(text)
        ) / CHARS_PER_TOKEN
    ) + 1


def tokens_to_chars(
    tokens: int
) -> int:
    """
    Convert a token budget into an approximate character budget.
    """

    return max(
        0,
        int(tokens * CHARS_PER_TOKEN)
    )


##########################################################################
# Text Trimming
##########################################################################

def truncate_text(
    value: Any,
    max_chars: int,
    marker: str = " ...[truncated]"
) -> str:
    """
    Trim a string to max_chars, appending a visible truncation marker.
    """

    text = "" if value is None else str(value).strip()

    if max_chars <= 0:

        return ""

    if len(text) <= max_chars:

        return text

    keep = max(
        0,
        max_chars - len(marker)
    )

    return text[:keep].rstrip() + marker


##########################################################################
# Structure Pruning
##########################################################################

def prune(
    value: Any,
    max_list_items: int = 6,
    max_string_chars: int = 400,
    drop_keys: Optional[Iterable[str]] = None,
    _depth: int = 0,
    max_depth: int = 4
) -> Any:
    """
    Recursively shrink a nested structure for prompt inclusion.

    Rules
    -----
    1. Bulk keys are removed entirely.
    2. Lists are capped, with an explicit "+N more" sentinel.
    3. Long strings are truncated.
    4. Nesting deeper than max_depth is collapsed to a placeholder.
    """

    if drop_keys is None:

        drop_keys = BULK_KEYS

    ####################################################################
    # Depth guard
    ####################################################################

    if _depth > max_depth:

        if isinstance(value, dict):

            return f"<{len(value)} nested field(s) omitted>"

        if isinstance(value, list):

            return f"<{len(value)} nested item(s) omitted>"

    ####################################################################
    # Mapping
    ####################################################################

    if isinstance(value, dict):

        pruned = {}

        for key, item in value.items():

            if str(key).lower() in drop_keys:

                continue

            if item is None:

                continue

            if isinstance(item, (dict, list)) and not item:

                continue

            pruned[key] = prune(
                item,
                max_list_items=max_list_items,
                max_string_chars=max_string_chars,
                drop_keys=drop_keys,
                _depth=_depth + 1,
                max_depth=max_depth
            )

        return pruned

    ####################################################################
    # Sequence
    ####################################################################

    if isinstance(value, (list, tuple, set)):

        items = list(value)

        kept = [
            prune(
                item,
                max_list_items=max_list_items,
                max_string_chars=max_string_chars,
                drop_keys=drop_keys,
                _depth=_depth + 1,
                max_depth=max_depth
            )
            for item in items[:max_list_items]
        ]

        remaining = len(items) - max_list_items

        if remaining > 0:

            kept.append(
                f"<+{remaining} more omitted>"
            )

        return kept

    ####################################################################
    # Scalar
    ####################################################################

    if isinstance(value, str):

        return truncate_text(
            value,
            max_string_chars
        )

    if isinstance(value, (int, float, bool)):

        return value

    return truncate_text(
        str(value),
        max_string_chars
    )


##########################################################################
# Compact Serialization
##########################################################################

def compact_json(
    value: Any,
    max_chars: Optional[int] = None,
    max_list_items: int = 6,
    max_string_chars: int = 400,
    drop_keys: Optional[Iterable[str]] = None
) -> str:
    """
    Serialize a structure for prompt inclusion without indentation.

    indent=4 inflates nested agricultural evidence by roughly 30-40%
    in pure whitespace, all of which is billed as tokens.
    """

    pruned = prune(
        value,
        max_list_items=max_list_items,
        max_string_chars=max_string_chars,
        drop_keys=drop_keys
    )

    text = json.dumps(
        pruned,
        separators=(",", ":"),
        default=str,
        ensure_ascii=False
    )

    if max_chars is not None:

        text = truncate_text(
            text,
            max_chars
        )

    return text


##########################################################################
# Prompt Budget Enforcement
##########################################################################

def enforce_budget(
    prompt: str,
    max_prompt_tokens: int,
    tail_chars: int = 1500
) -> str:
    """
    Guarantee a prompt fits a declared token budget.

    The head (task instructions and schema) and the tail (final
    instructions) carry the response contract, so the middle evidence
    block is what gets cut.
    """

    text = str(prompt)

    if estimate_tokens(text) <= max_prompt_tokens:

        return text

    budget_chars = tokens_to_chars(
        max_prompt_tokens
    )

    if budget_chars <= tail_chars:

        return text[:budget_chars]

    head_chars = budget_chars - tail_chars

    head = text[:head_chars]

    tail = text[-tail_chars:]

    return (
        f"{head}\n\n"
        "...[evidence truncated to fit the model token budget]...\n\n"
        f"{tail}"
    )
