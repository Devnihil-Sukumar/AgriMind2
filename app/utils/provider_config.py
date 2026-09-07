"""
==========================================================================
AgriMind

Provider Configuration

Central provider routing for all LLM-enabled modules.
==========================================================================
"""

import os
from typing import Dict

from dotenv import load_dotenv

load_dotenv()


SUPPORTED_PROVIDERS = {
    "groq",
    "ollama",
    "gemini"
}


DEFAULT_PROVIDERS: Dict[str, str] = {

    "planner": "groq",

    "weather": "ollama",

    "soil": "ollama",

    "satellite": "ollama",

    "market": "groq",

    "historical": "ollama",

    "collaborative": "gemini",

    "executive": "groq",

    "recommendation": "groq",

    "explanation": "groq"
}


##########################################################################
# Completion Token Budgets
##########################################################################

# Groq counts prompt tokens PLUS the completion reservation against the
# per-minute allowance. A blanket 4096-token reservation consumes half
# of an 8000 TPM tier before any prompt is sent, so each component
# declares the response length it actually needs.

# Components backed by Ollama are intentionally absent: they keep the
# locally configured OLLAMA_NUM_PREDICT, because raising their output
# ceiling directly increases local generation time.

DEFAULT_MAX_TOKENS: Dict[str, int] = {

    "planner": 1200,

    "market": 1400,

    "collaborative": 2500,

    "executive": 1200,

    "recommendation": 1400,

    "explanation": 2600
}


##########################################################################
# Prompt Token Budgets
##########################################################################

# Upper bound on the prompt itself, enforced before the request is sent.
# prompt budget + completion budget must stay under the provider tier
# limit (Groq free tier for gpt-oss-120b is 8000 TPM).

DEFAULT_MAX_PROMPT_TOKENS: Dict[str, int] = {

    "planner": 3000,

    "collaborative": 12000,

    "executive": 3500,

    "recommendation": 3800,

    "explanation": 4300
}


def normalize_provider(
    provider: str
) -> str:
    """
    Normalize and validate provider names.
    """

    normalized = str(
        provider
    ).strip().lower()

    if normalized not in SUPPORTED_PROVIDERS:

        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported providers: "
            f"{sorted(SUPPORTED_PROVIDERS)}"
        )

    return normalized


def get_provider(
    component: str,
    default: str | None = None
) -> str:
    """
    Get provider for a specific AgriMind component.

    Environment variable format:

        WEATHER_LLM_PROVIDER=ollama
        SOIL_LLM_PROVIDER=ollama
        PLANNER_LLM_PROVIDER=groq
    """

    component_key = str(
        component
    ).strip().lower()

    env_name = (
        f"{component_key.upper()}_LLM_PROVIDER"
    )

    configured = os.getenv(
        env_name
    )

    if configured:

        return normalize_provider(
            configured
        )

    if default:

        return normalize_provider(
            default
        )

    return normalize_provider(
        DEFAULT_PROVIDERS.get(
            component_key,
            "groq"
        )
    )


def get_all_providers() -> Dict[str, str]:
    """
    Return the currently configured provider map.
    """

    providers = {}

    for component, fallback in DEFAULT_PROVIDERS.items():

        providers[component] = get_provider(
            component,
            fallback
        )

    return providers

##########################################################################
# Token Budget Accessors
##########################################################################

def _env_int(
    name: str
) -> int | None:
    """
    Read an integer environment override, ignoring malformed values.
    """

    raw = os.getenv(
        name
    )

    if not raw:

        return None

    try:

        value = int(
            str(raw).strip()
        )

    except (TypeError, ValueError):

        return None

    return value if value > 0 else None


def get_max_tokens(
    component: str,
    default: int | None = None
) -> int | None:
    """
    Completion token ceiling for a component.

    Environment override format:

        RECOMMENDATION_MAX_TOKENS=1400
        EXPLANATION_MAX_TOKENS=2000
    """

    component_key = str(
        component
    ).strip().lower()

    override = _env_int(
        f"{component_key.upper()}_MAX_TOKENS"
    )

    if override is not None:

        return override

    return DEFAULT_MAX_TOKENS.get(
        component_key,
        default
    )


def get_max_prompt_tokens(
    component: str,
    default: int | None = None
) -> int | None:
    """
    Prompt token ceiling for a component.

    Environment override format:

        EXPLANATION_MAX_PROMPT_TOKENS=3500
    """

    component_key = str(
        component
    ).strip().lower()

    override = _env_int(
        f"{component_key.upper()}_MAX_PROMPT_TOKENS"
    )

    if override is not None:

        return override

    return DEFAULT_MAX_PROMPT_TOKENS.get(
        component_key,
        default
    )
