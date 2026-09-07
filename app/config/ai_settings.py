############################################################
# LLM PROVIDER CONFIGURATION
############################################################

import os

from dotenv import load_dotenv

load_dotenv()


############################################################
# Ollama
############################################################

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/api/chat"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3:4b"
)

OLLAMA_TEMPERATURE = float(
    os.getenv(
        "OLLAMA_TEMPERATURE",
        "0.2"
    )
)

OLLAMA_TIMEOUT = int(
    os.getenv(
        "OLLAMA_TIMEOUT",
        "120"
    )
)


############################################################
# Groq
############################################################

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY",
    ""
)

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)

GROQ_TEMPERATURE = float(
    os.getenv(
        "GROQ_TEMPERATURE",
        "0.2"
    )
)

GROQ_MAX_TOKENS = int(
    os.getenv(
        "GROQ_MAX_TOKENS",
        "8000"
    )
)

GROQ_RETRIES = int(
    os.getenv(
        "GROQ_RETRIES",
        "3"
    )
)


############################################################
# Component Providers
############################################################

PLANNER_LLM_PROVIDER = os.getenv(
    "PLANNER_LLM_PROVIDER",
    "groq"
)

WEATHER_LLM_PROVIDER = os.getenv(
    "WEATHER_LLM_PROVIDER",
    "ollama"
)

SOIL_LLM_PROVIDER = os.getenv(
    "SOIL_LLM_PROVIDER",
    "ollama"
)

SATELLITE_LLM_PROVIDER = os.getenv(
    "SATELLITE_LLM_PROVIDER",
    "ollama"
)

MARKET_LLM_PROVIDER = os.getenv(
    "MARKET_LLM_PROVIDER",
    "groq"
)

HISTORICAL_LLM_PROVIDER = os.getenv(
    "HISTORICAL_LLM_PROVIDER",
    "ollama"
)

COLLABORATIVE_LLM_PROVIDER = os.getenv(
    "COLLABORATIVE_LLM_PROVIDER",
    "groq"
)

RECOMMENDATION_LLM_PROVIDER = os.getenv(
    "RECOMMENDATION_LLM_PROVIDER",
    "groq"
)

EXPLANATION_LLM_PROVIDER = os.getenv(
    "EXPLANATION_LLM_PROVIDER",
    "groq"
)
##########################################################################
# GOOGLE EARTH ENGINE
##########################################################################

GEE_PROJECT_ID = "agrimind-503213"

##########################################################################
# SENTINEL-2 SETTINGS
##########################################################################

SATELLITE_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"

SATELLITE_ANALYSIS_DAYS = 30

SATELLITE_BUFFER_METERS = 150

SATELLITE_MAX_CLOUD_PERCENT = 20

##########################################################################
# TRUSTAI GOVERNANCE LAYER
#
# Runtime Bayesian trust + risk-aware decision settings for the
# governance layer sitting between the executor and every agent it
# calls (see app/governance/). Concept source: bayesian.txt.
##########################################################################

# Population-level Beta(alpha, beta) prior for a brand-new category.
GOVERNANCE_PRIOR_ALPHA = float(os.getenv("GOVERNANCE_PRIOR_ALPHA", "2.0"))
GOVERNANCE_PRIOR_BETA = float(os.getenv("GOVERNANCE_PRIOR_BETA", "2.0"))

# Fraction of an agent's posterior retained across updates before new
# evidence is folded in (sequential trust decay, bayesian.txt sec. 11).
GOVERNANCE_TRUST_DECAY = float(os.getenv("GOVERNANCE_TRUST_DECAY", "0.99"))

# Fraction of each evidence weight also absorbed by the category-level
# pooled posterior (hierarchical partial pooling, bayesian.txt sec. 10).
GOVERNANCE_POOLING_STRENGTH = float(
    os.getenv("GOVERNANCE_POOLING_STRENGTH", "0.25")
)

# Evidence weighting (bayesian.txt sec. 8: evidence-aware updating).
GOVERNANCE_BASE_EVIDENCE_WEIGHT = float(
    os.getenv("GOVERNANCE_BASE_EVIDENCE_WEIGHT", "0.5")
)
GOVERNANCE_FALLBACK_DISCOUNT = float(
    os.getenv("GOVERNANCE_FALLBACK_DISCOUNT", "0.5")
)
GOVERNANCE_FAILURE_PENALTY = float(
    os.getenv("GOVERNANCE_FAILURE_PENALTY", "1.5")
)
GOVERNANCE_UNAVAILABLE_PENALTY = float(
    os.getenv("GOVERNANCE_UNAVAILABLE_PENALTY", "0.2")
)

# Expected-utility cost table (bayesian.txt sec. 13).
GOVERNANCE_BASE_BENEFIT = float(
    os.getenv("GOVERNANCE_BASE_BENEFIT", "20.0")
)
GOVERNANCE_BASE_FAILURE_COST = float(
    os.getenv("GOVERNANCE_BASE_FAILURE_COST", "20.0")
)
GOVERNANCE_REVIEW_COST = float(
    os.getenv("GOVERNANCE_REVIEW_COST", "12.0")
)
GOVERNANCE_REJECT_COST_RATIO = float(
    os.getenv("GOVERNANCE_REJECT_COST_RATIO", "0.2")
)
GOVERNANCE_REVIEW_CATCH_RATE = float(
    os.getenv("GOVERNANCE_REVIEW_CATCH_RATE", "0.95")
)

# Extra P(fail) caution added per std-dev of posterior uncertainty, so
# a new agent (wide posterior) is treated more cautiously than a
# proven one at the same mean trust.
GOVERNANCE_UNCERTAINTY_MARGIN = float(
    os.getenv("GOVERNANCE_UNCERTAINTY_MARGIN", "1.0")
)

##########################################################################
# LEGACY / MEMORY SUBSYSTEM DEFAULTS
#
# Referenced by app/memory/chroma_store.py and app/agents/reasoning_agent.py
# (via app/ai/orchestrator.py), which are not part of the current
# dynamic_orchestrator pipeline but are still imported by test modules.
##########################################################################

CHROMA_DB_PATH = os.getenv(
    "CHROMA_DB_PATH",
    "./vector_db"
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "all-MiniLM-L6-v2"
)

LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "qwen3:4b"
)

##########################################################################
# DEFAULT LOCATION
#
# Fallback coordinates used by data_collector.collect() when a caller
# does not supply latitude/longitude explicitly.
##########################################################################

DEFAULT_LATITUDE = float(
    os.getenv(
        "DEFAULT_LATITUDE",
        "11.0168"
    )
)

DEFAULT_LONGITUDE = float(
    os.getenv(
        "DEFAULT_LONGITUDE",
        "76.9558"
    )
)
