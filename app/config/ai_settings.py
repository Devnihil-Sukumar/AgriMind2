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

# Default lightweight model.
# Specialist agents can use this model when no component-specific
# model is selected by the LLM client.
OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "gpt-oss:20b"
)

OLLAMA_TEMPERATURE = float(
    os.getenv(
        "OLLAMA_TEMPERATURE",
        "0.2"
    )
)

# CPU inference can be slow, so keep a generous timeout.
OLLAMA_TIMEOUT = int(
    os.getenv(
        "OLLAMA_TIMEOUT",
        "300"
    )
)


############################################################
# LOCAL OFFLINE OLLAMA MODELS
############################################################

# CPU/GPU-friendly model strategy:
#
# gpt-oss:20b
#   Used uniformly across every component -- reasoning-heavy
#   (Planner, Market, Collaborative Reasoning, Recommendation) and
#   lightweight specialist (Weather, Soil, Satellite, Historical,
#   Explanation) alike. Same architecture family as the Groq-hosted
#   openai/gpt-oss-120b used elsewhere in the study, at a scale that
#   runs locally.
#
# No Groq or Gemini API is required.

OLLAMA_REASONING_MODEL = os.getenv(
    "OLLAMA_REASONING_MODEL",
    "gpt-oss:20b"
)

OLLAMA_SPECIALIST_MODEL = os.getenv(
    "OLLAMA_SPECIALIST_MODEL",
    "gpt-oss:20b"
)

OLLAMA_COLLAB_MODEL = os.getenv(
    "OLLAMA_COLLAB_MODEL",
    "gpt-oss:20b"
)

OLLAMA_REASONING_TEMPERATURE = float(
    os.getenv(
        "OLLAMA_REASONING_TEMPERATURE",
        "0.2"
    )
)

OLLAMA_REASONING_TIMEOUT = int(
    os.getenv(
        "OLLAMA_REASONING_TIMEOUT",
        "300"
    )
)

OLLAMA_REASONING_MAX_TOKENS = int(
    os.getenv(
        "OLLAMA_REASONING_MAX_TOKENS",
        "1024"
    )
)


############################################################
# Component Providers
############################################################

# All AgriMind components run locally through Ollama.

PLANNER_LLM_PROVIDER = os.getenv(
    "PLANNER_LLM_PROVIDER",
    "ollama"
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
    "ollama"
)

HISTORICAL_LLM_PROVIDER = os.getenv(
    "HISTORICAL_LLM_PROVIDER",
    "ollama"
)

COLLABORATIVE_LLM_PROVIDER = os.getenv(
    "COLLABORATIVE_LLM_PROVIDER",
    "ollama"
)

RECOMMENDATION_LLM_PROVIDER = os.getenv(
    "RECOMMENDATION_LLM_PROVIDER",
    "ollama"
)

EXPLANATION_LLM_PROVIDER = os.getenv(
    "EXPLANATION_LLM_PROVIDER",
    "ollama"
)


##########################################################################
# GOOGLE EARTH ENGINE
##########################################################################

GEE_PROJECT_ID = os.getenv(
    "GEE_PROJECT_ID",
    "agrimind-503213"
)


##########################################################################
# SENTINEL-2 SETTINGS
##########################################################################

SATELLITE_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"

SATELLITE_ANALYSIS_DAYS = 30

SATELLITE_BUFFER_METERS = 150

SATELLITE_MAX_CLOUD_PERCENT = 20


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
    "gpt-oss:20b"
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