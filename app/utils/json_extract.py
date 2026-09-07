"""
==========================================================================
AgriMind

JSON Extraction

Shared, escape-aware JSON object extraction for LLM responses.

Every specialist agent's parse_response() and the Explanation
Engine's clean_response() independently implemented:

    start = response.find("{")
    end = response.rfind("}")

That breaks the moment the response contains ANY brace character
outside the JSON payload. openai/gpt-oss-120b is a reasoning model
and can emit commentary before or after the JSON body; if that
commentary mentions a brace anywhere, rfind grabs the LAST "}" in the
WHOLE response rather than the one that actually closes the first
"{", producing a slice that is not valid, self-contained JSON.

BaseAgent.parse() already solved this correctly with an escape-aware,
depth-counted scan that pairs the first "{" with its true matching
"}", ignoring braces inside string literals. This module is that
algorithm, shared, so every caller gets the same correct behaviour
instead of six independent naive copies.

Author : AgriMind Team
==========================================================================
"""

import json


##########################################################################
# Code Fence Stripping
##########################################################################

def strip_code_fences(text) -> str:
    """
    Remove Markdown JSON code fences and surrounding whitespace.
    """

    cleaned = str(text).strip()

    cleaned = cleaned.replace(
        "```json",
        ""
    )

    cleaned = cleaned.replace(
        "```",
        ""
    )

    return cleaned.strip()


##########################################################################
# Substring Extraction
##########################################################################

def _iter_balanced_spans(
    text: str
):
    """
    Yield every top-level, escape-aware brace-balanced {...} span in
    text, left to right.

    Scanning resumes right after each completed span (whether or not
    it turns out to be valid JSON) rather than stopping at the first
    one, so a small decoy object earlier in the text does not hide a
    later, real one.
    """

    index = 0
    length = len(text)

    while index < length:

        start = text.find(
            "{",
            index
        )

        if start == -1:

            return

        depth = 0
        in_string = False
        escape = False
        end = None

        pos = start

        while pos < length:

            char = text[pos]

            if escape:

                escape = False
                pos += 1
                continue

            if char == "\\" and in_string:

                escape = True
                pos += 1
                continue

            if char == '"':

                in_string = not in_string
                pos += 1
                continue

            if in_string:

                pos += 1
                continue

            if char == "{":

                depth += 1

            elif char == "}":

                depth -= 1

                if depth == 0:

                    end = pos
                    break

            pos += 1

        ################################################################
        # Unbalanced from this point on; nothing further to find.
        ################################################################

        if end is None:

            return

        yield text[start:end + 1]

        index = end + 1


def extract_json_substring(
    text,
    error_label: str = "LLM"
) -> str:
    """
    Return a complete, valid JSON object substring from text.

    Tries a direct parse first (the common case for a well-behaved
    model). Otherwise scans every top-level brace-balanced span and
    returns the LAST one that parses as valid JSON, rather than the
    first.

    "Last" is deliberate: a reasoning model (openai/gpt-oss-120b is
    one) can narrate its approach before answering -- "I'll format
    this as an object like {}" -- and a decoy fragment like that can
    itself be complete, valid JSON. The model's actual answer is the
    structured payload it settles on at the end, not whatever brace
    pair happens to close first.

    Raises ValueError if no valid JSON object can be found anywhere
    in the text.
    """

    cleaned = strip_code_fences(
        text
    )

    if not cleaned:

        raise ValueError(
            f"{error_label} returned an empty response."
        )

    ####################################################################
    # Attempt 1: the whole cleaned response is already valid JSON.
    ####################################################################

    try:

        json.loads(
            cleaned
        )

        return cleaned

    except json.JSONDecodeError:

        pass

    ####################################################################
    # Attempt 2: scan every top-level span; keep the last valid one.
    ####################################################################

    best = None

    for candidate in _iter_balanced_spans(
        cleaned
    ):

        try:

            json.loads(
                candidate
            )

            best = candidate

        except json.JSONDecodeError:

            continue

    if best is not None:

        return best

    if "{" not in cleaned:

        raise ValueError(
            f"No JSON object found in {error_label} response."
        )

    raise ValueError(
        f"{error_label} response did not contain a complete "
        "valid JSON object."
    )


##########################################################################
# Object Extraction
##########################################################################

def extract_json_object(
    text,
    error_label: str = "LLM"
) -> dict:
    """
    Return the first complete JSON object in text, parsed to a dict.
    """

    candidate = extract_json_substring(
        text,
        error_label=error_label
    )

    result = json.loads(
        candidate
    )

    if not isinstance(
        result,
        dict
    ):

        raise ValueError(
            f"{error_label} JSON response must be an object."
        )

    return result
