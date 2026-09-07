"""
==========================================================================
AgriMind

Dynamic Planner

Responsibilities
----------------
1. Build a compact planner prompt.
2. Call the centralized LLM client.
3. Parse planner response.
4. Normalize malformed/legacy planner schemas.
5. Normalize agent aliases.
6. Validate the final execution plan.
7. Dynamically route queries when the LLM planner fails.
8. Guarantee RecommendationAgent is last.

The planner no longer communicates directly with Ollama.
All LLM calls go through app.utils.llm_client.
==========================================================================
"""

import json
import re

import numpy as np

from app.prompts.planner_prompt import PLANNER_PROMPT
from app.utils.llm_client import llm_client


##########################################################################
# JSON SERIALIZATION
##########################################################################


def json_converter(value):
    """
    Convert NumPy values into JSON-compatible values.
    """

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        return float(value)

    if isinstance(value, np.ndarray):
        return value.tolist()

    return str(value)


##########################################################################
# PLANNER
##########################################################################


class Planner:

    """
    Dynamic planning engine.

    The LLM is responsible for query-aware agent selection.

    The deterministic router remains available as a safety fallback when
    the LLM produces invalid output or becomes unavailable.
    """

    ######################################################################
    # Initialization
    ######################################################################

    def __init__(self):

        ############################################################
        # Canonical agents
        ############################################################

        self.allowed_agents = {
            "WeatherAgent",
            "SoilAgent",
            "SatelliteAgent",
            "MarketAgent",
            "HistoricalAgent",
            "RecommendationAgent"
        }

        ############################################################
        # Agent purposes
        ############################################################

        self.agent_purposes = {

            "WeatherAgent":
                "Analyze weather conditions relevant to the request.",

            "SoilAgent":
                "Analyze soil conditions relevant to the request.",

            "SatelliteAgent":
                "Analyze vegetation health, crop condition, and water stress.",

            "MarketAgent":
                "Analyze market prices, trends, and selling opportunities.",

            "HistoricalAgent":
                "Analyze historical farm information and previous outcomes.",

            "RecommendationAgent":
                "Generate the final recommendation from specialist evidence."
        }

        ############################################################
        # Alias normalization
        ############################################################

        self.agent_aliases = {

            "weather": "WeatherAgent",
            "weatheragent": "WeatherAgent",
            "weather specialist": "WeatherAgent",
            "weatherspecialist": "WeatherAgent",

            "soil": "SoilAgent",
            "soilagent": "SoilAgent",
            "soil specialist": "SoilAgent",
            "soilspecialist": "SoilAgent",

            "satellite": "SatelliteAgent",
            "satelliteagent": "SatelliteAgent",
            "satellite specialist": "SatelliteAgent",
            "satellitespecialist": "SatelliteAgent",

            "vegetation": "SatelliteAgent",
            "vegetationagent": "SatelliteAgent",
            "vegetation specialist": "SatelliteAgent",
            "vegetationspecialist": "SatelliteAgent",

            "water": "WeatherAgent",
            "wateragent": "WeatherAgent",
            "water specialist": "WeatherAgent",
            "waterspecialist": "WeatherAgent",

            "market": "MarketAgent",
            "marketagent": "MarketAgent",
            "market specialist": "MarketAgent",
            "marketspecialist": "MarketAgent",

            "historical": "HistoricalAgent",
            "historicalagent": "HistoricalAgent",
            "historical specialist": "HistoricalAgent",
            "historicalspecialist": "HistoricalAgent",
            "history": "HistoricalAgent",

            "recommendation": "RecommendationAgent",
            "recommendationagent": "RecommendationAgent",
            "recommendation specialist": "RecommendationAgent",
            "recommendationspecialist": "RecommendationAgent"
        }

    ######################################################################
    # Compact Context
    ######################################################################

    def build_compact_context(self, context):
        """
        Extract only the information required for agent selection.

        The original planner sent the complete farm context, including
        crop profiles, market lists, historical objects and duplicate
        nested structures. That created oversized Groq requests.

        The planner does NOT need full analytical evidence.
        It only needs enough context to understand which specialist
        domains are relevant.
        """

        if not isinstance(context, dict):
            return {}

        compact = {}

        ############################################################
        # Basic farm identity
        ############################################################

        compact["crop"] = context.get("crop")

        compact["location"] = context.get(
            "location",
            {}
        )

        ############################################################
        # Weather summary
        ############################################################

        weather = context.get("weather", {})

        if isinstance(weather, dict):

            raw_weather = weather.get(
                "raw_data",
                {}
            ) or {}

            compact["weather"] = {
                "temperature": raw_weather.get("temperature"),
                "humidity": raw_weather.get("humidity"),
                "rainfall": raw_weather.get("rainfall"),
                "wind_speed": raw_weather.get("wind_speed"),
                "status": weather.get("status")
            }

        ############################################################
        # Soil summary
        ############################################################

        soil = context.get("soil", {})

        if isinstance(soil, dict):

            raw_soil = soil.get(
                "raw_data",
                {}
            ) or {}

            compact["soil"] = {
                "ph": raw_soil.get("ph"),
                "nitrogen": raw_soil.get("nitrogen"),
                "organic_carbon": raw_soil.get("organic_carbon"),
                "texture": (soil.get(
                    "assessment",
                    {}
                ) or {}).get("texture")
            }

        ############################################################
        # Satellite summary
        ############################################################

        satellite = context.get("satellite", {})

        if isinstance(satellite, dict):

            vegetation = satellite.get(
                "vegetation",
                {}
            ) or {}

            water = satellite.get(
                "water",
                {}
            ) or {}

            compact["satellite"] = {
                "ndvi": vegetation.get("ndvi"),
                "evi": vegetation.get("evi"),
                "savi": vegetation.get("savi"),
                "health": vegetation.get("health"),
                "ndwi": water.get("ndwi"),
                "stress": water.get("stress")
            }

        ############################################################
        # Market summary
        ############################################################

        market = context.get("market", {})

        if isinstance(market, dict):

            nearest = market.get(
                "nearest_market",
                {}
            ) or {}

            compact["market"] = {
                "market": market.get("market"),
                "trend": market.get("market_trend"),
                "price": nearest.get("price"),
                "distance_km": nearest.get("distance_km")
            }

        ############################################################
        # Historical availability only
        ############################################################

        historical = context.get(
            "historical",
            {}
        )

        if isinstance(historical, dict):

            compact["historical"] = {
                "status": historical.get("status"),
                "record_count": historical.get("record_count", 0)
            }

        return compact

    ######################################################################
    # Build Prompt
    ######################################################################

    def build_prompt(
        self,
        user_query,
        context
    ):
        """
        Build a compact planning prompt.

        IMPORTANT:
        The planner performs routing only.
        It does not analyze the farm or generate recommendations.
        """

        compact_context = self.build_compact_context(
            context
        )

        context_json = json.dumps(
            compact_context,
            separators=(",", ":"),
            default=json_converter
        )

        return f"""
{PLANNER_PROMPT}

USER REQUEST:
{user_query}

COMPACT FARM CONTEXT:
{context_json}

TASK:
Select only the specialist agents needed to answer the USER REQUEST.

AVAILABLE AGENTS:
WeatherAgent
SoilAgent
SatelliteAgent
MarketAgent
HistoricalAgent
RecommendationAgent

RULES:
1. Select only relevant specialist agents.
2. Do not analyze the farm.
3. Do not generate a farmer recommendation.
4. RecommendationAgent must always be included.
5. RecommendationAgent must be the final agent.
6. Do not duplicate agents.
7. Return ONLY valid JSON.

REQUIRED FORMAT:
{{
  "goal": "user request",
  "execution_plan": [
    {{
      "agent": "WeatherAgent",
      "priority": 1,
      "purpose": "Analyze weather conditions relevant to the request."
    }},
    {{
      "agent": "RecommendationAgent",
      "priority": 2,
      "purpose": "Generate the final recommendation from specialist evidence."
    }}
  ],
  "confidence": 0.90
}}
""".strip()

    ######################################################################
    # LLM Call
    ######################################################################

    def call_llm(
        self,
        prompt
    ):
        """
        Call the centralized LLM client, routed through whichever
        provider PLANNER_LLM_PROVIDER configures (see
        app/utils/provider_config.py) rather than llm_client's own
        Groq-default fallback.
        """

        return llm_client.generate(
            prompt=prompt,
            component="planner",
            system_prompt=(
                "You are the AgriMind Dynamic Planner. "
                "Your only task is to select relevant specialist agents. "
                "Return valid JSON only."
            ),
            temperature=0.0
        )

    ######################################################################
    # Extract JSON
    ######################################################################

    def extract_json(
        self,
        raw
    ):

        if not raw:

            raise ValueError(
                "Planner returned an empty response."
            )

        text = str(raw).strip()

        ############################################################
        # Remove markdown fences
        ############################################################

        text = text.replace(
            "```json",
            ""
        )

        text = text.replace(
            "```",
            ""
        )

        text = text.strip()

        ############################################################
        # Extract outer JSON object
        ############################################################

        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:

            raise ValueError(
                "Planner response does not contain a JSON object."
            )

        try:

            result = json.loads(
                text[start:end + 1]
            )

        except json.JSONDecodeError as error:

            raise ValueError(
                f"Planner returned malformed JSON: {error}"
            ) from error

        if not isinstance(
            result,
            dict
        ):

            raise ValueError(
                "Planner JSON must be an object."
            )

        return result

    ######################################################################
    # Normalize Agent Name
    ######################################################################

    def normalize_agent(
        self,
        value
    ):

        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        ############################################################
        # Exact canonical name
        ############################################################

        if text in self.allowed_agents:
            return text

        ############################################################
        # Normalize case / spacing
        ############################################################

        normalized = re.sub(
            r"\s+",
            " ",
            text.lower()
        )

        if normalized in self.agent_aliases:
            return self.agent_aliases[normalized]

        ############################################################
        # Normalize hyphens / underscores / spaces
        ############################################################

        compact = (
            normalized
            .replace("-", "")
            .replace("_", "")
            .replace(" ", "")
        )

        return self.agent_aliases.get(
            compact
        )

    ######################################################################
    # Normalize Planner Schema
    ######################################################################

    def normalize_schema(
        self,
        raw_plan,
        user_query
    ):
        """
        Convert supported LLM response formats into canonical schema.
        """

        if not isinstance(
            raw_plan,
            dict
        ):

            raise ValueError(
                "Planner output must be a JSON object."
            )

        ############################################################
        # Unwrap nested planner object
        ############################################################

        if isinstance(
            raw_plan.get("planner"),
            dict
        ):

            nested = raw_plan["planner"]

            merged = dict(nested)

            if "goal" in raw_plan:
                merged["goal"] = raw_plan["goal"]

            if "confidence" in raw_plan:
                merged["confidence"] = raw_plan["confidence"]

            raw_plan = merged

        ############################################################
        # Goal
        ############################################################

        goal = raw_plan.get(
            "goal",
            user_query
        )

        ############################################################
        # Locate agent source
        ############################################################

        if isinstance(
            raw_plan.get("execution_plan"),
            list
        ):

            source = raw_plan["execution_plan"]

        elif isinstance(
            raw_plan.get("agents"),
            list
        ):

            source = raw_plan["agents"]

        elif isinstance(
            raw_plan.get("specialist_agents"),
            list
        ):

            source = raw_plan["specialist_agents"]

        else:

            raise ValueError(
                "Planner output does not contain an execution plan."
            )

        ############################################################
        # Convert agents
        ############################################################

        normalized_steps = []
        seen = set()

        for item in source:

            if isinstance(
                item,
                str
            ):

                agent_name = self.normalize_agent(
                    item
                )

                purpose = None
                priority = None

            elif isinstance(
                item,
                dict
            ):

                raw_agent = item.get(
                    "agent",
                    item.get(
                        "name"
                    )
                )

                agent_name = self.normalize_agent(
                    raw_agent
                )

                purpose = item.get(
                    "purpose"
                )

                priority = item.get(
                    "priority"
                )

            else:

                continue

            ########################################################
            # Unknown agent
            ########################################################

            if agent_name is None:
                continue

            ########################################################
            # Avoid duplicates
            ########################################################

            if agent_name in seen:
                continue

            seen.add(
                agent_name
            )

            normalized_steps.append(
                {
                    "agent": agent_name,
                    "priority": priority,
                    "purpose":
                        purpose or self.agent_purposes[agent_name]
                }
            )

        ############################################################
        # No specialist survived normalization
        ############################################################

        if not normalized_steps:

            raise ValueError(
                "Planner selected no valid agents."
            )

        return {
            "goal": str(goal),
            "execution_plan": normalized_steps,
            "confidence": raw_plan.get(
                "confidence",
                0.90
            )
        }

    ######################################################################
    # Validate Plan
    ######################################################################

    def validate_plan(
        self,
        plan,
        user_query=None
    ):

        if not isinstance(
            plan,
            dict
        ):

            raise ValueError(
                "Planner output must be an object."
            )

        ############################################################
        # Required goal
        ############################################################

        goal = plan.get(
            "goal"
        )

        if not goal:
            goal = user_query

        if not goal:

            raise ValueError(
                "Planner output missing 'goal'."
            )

        ############################################################
        # Required execution plan
        ############################################################

        execution_plan = plan.get(
            "execution_plan"
        )

        if not isinstance(
            execution_plan,
            list
        ):

            raise ValueError(
                "execution_plan must be a list."
            )

        ############################################################
        # Validate agents
        ############################################################

        specialists = []
        recommendation = None
        seen = set()

        for step in execution_plan:

            if not isinstance(
                step,
                dict
            ):

                raise ValueError(
                    "Every execution_plan item must be an object."
                )

            agent = self.normalize_agent(
                step.get("agent")
            )

            if agent is None:

                raise ValueError(
                    "Execution plan contains an unknown agent."
                )

            ########################################################
            # Duplicate protection
            ########################################################

            if agent in seen:
                continue

            seen.add(
                agent
            )

            normalized_step = {
                "agent": agent,
                "priority": 0,
                "purpose":
                    step.get("purpose")
                    or self.agent_purposes[agent]
            }

            if agent == "RecommendationAgent":

                recommendation = normalized_step

            else:

                specialists.append(
                    normalized_step
                )

        ############################################################
        # At least one specialist required
        ############################################################

        if not specialists:

            raise ValueError(
                "Planner produced no specialist agents."
            )

        ############################################################
        # Recommendation is mandatory
        ############################################################

        if recommendation is None:

            recommendation = {
                "agent":
                    "RecommendationAgent",
                "priority":
                    0,
                "purpose":
                    self.agent_purposes[
                        "RecommendationAgent"
                    ]
            }

        ############################################################
        # Recommendation always last
        ############################################################

        final_steps = specialists + [
            recommendation
        ]

        ############################################################
        # Sequential priority
        ############################################################

        for priority, step in enumerate(
            final_steps,
            start=1
        ):

            step["priority"] = priority

        ############################################################
        # Confidence
        ############################################################

        try:

            confidence = float(
                plan.get(
                    "confidence",
                    0.90
                )
            )

        except (
            TypeError,
            ValueError
        ):

            confidence = 0.90

        if confidence > 1:
            confidence /= 100.0

        confidence = max(
            0.0,
            min(
                confidence,
                1.0
            )
        )

        ############################################################
        # Final canonical plan
        ############################################################

        return {
            "goal": str(goal),
            "execution_plan": final_steps,
            "confidence": round(
                confidence,
                2
            )
        }

    ######################################################################
    # Query Matching
    ######################################################################

    def contains_any(
        self,
        query,
        keywords
    ):

        return any(
            keyword in query
            for keyword in keywords
        )

    ######################################################################
    # Deterministic Router
    ######################################################################

    def build_fallback_plan(
        self,
        user_query
    ):
        """
        Query-aware deterministic fallback.
        """

        query = str(
            user_query or ""
        ).lower().strip()

        query = re.sub(
            r"[^a-z0-9\s]",
            " ",
            query
        )

        query = re.sub(
            r"\s+",
            " ",
            query
        )

        ############################################################
        # Intent groups
        ############################################################

        weather_terms = [
            "weather",
            "rain",
            "rainfall",
            "temperature",
            "humidity",
            "forecast",
            "climate",
            "drought",
            "heat stress",
            "cold stress"
        ]

        soil_terms = [
            "soil",
            "soil health",
            "soil fertility",
            "soil texture",
            "ph",
            "nitrogen",
            "phosphorus",
            "potassium",
            "npk",
            "nutrient",
            "nutrients",
            "fertilizer",
            "fertiliser",
            "organic carbon"
        ]

        satellite_terms = [
            "satellite",
            "ndvi",
            "ndwi",
            "savi",
            "vegetation",
            "crop health",
            "plant health",
            "crop stress",
            "water stress",
            "remote sensing",
            "field condition",
            "disease"
        ]

        market_terms = [
            "market",
            "price",
            "prices",
            "sell",
            "selling",
            "buyer",
            "buyers",
            "mandi",
            "profit",
            "profitability",
            "revenue",
            "income",
            "where to sell",
            "best market",
            "nearby market"
        ]

        historical_terms = [
            "historical",
            "history",
            "previous",
            "past",
            "previous season",
            "last season",
            "previous yield",
            "previous harvest",
            "historical comparison",
            "what worked before",
            "what failed before"
        ]

        ############################################################
        # Explicit decision intents
        ############################################################

        irrigation = self.contains_any(
            query,
            [
                "irrigate",
                "irrigation",
                "should i water",
                "when should i water",
                "water my crop"
            ]
        )

        crop_health = self.contains_any(
            query,
            [
                "crop health",
                "plant health",
                "crop stress",
                "disease",
                "vegetation health"
            ]
        )

        yield_request = self.contains_any(
            query,
            [
                "maximize yield",
                "improve yield",
                "increase yield",
                "improve productivity",
                "maximize crop performance",
                "improve crop performance"
            ]
        )

        profit_request = self.contains_any(
            query,
            [
                "profit",
                "profitability",
                "revenue",
                "income",
                "selling",
                "sell"
            ]
        )

        ############################################################
        # Selected agents
        ############################################################

        selected = []

        ############################################################
        # Irrigation
        ############################################################

        if irrigation:

            selected.extend(
                [
                    "WeatherAgent",
                    "SoilAgent",
                    "SatelliteAgent"
                ]
            )

        ############################################################
        # Crop health
        ############################################################

        elif crop_health:

            selected.extend(
                [
                    "SatelliteAgent",
                    "WeatherAgent",
                    "SoilAgent"
                ]
            )

        ############################################################
        # Yield optimization
        ############################################################

        elif yield_request:

            selected.extend(
                [
                    "WeatherAgent",
                    "SoilAgent",
                    "SatelliteAgent"
                ]
            )

            if profit_request:

                selected.append(
                    "MarketAgent"
                )

        ############################################################
        # Explicit specialist intents
        ############################################################

        else:

            if self.contains_any(
                query,
                weather_terms
            ):

                selected.append(
                    "WeatherAgent"
                )

            if self.contains_any(
                query,
                soil_terms
            ):

                selected.append(
                    "SoilAgent"
                )

            if self.contains_any(
                query,
                satellite_terms
            ):

                selected.append(
                    "SatelliteAgent"
                )

            if self.contains_any(
                query,
                market_terms
            ):

                selected.append(
                    "MarketAgent"
                )

            if self.contains_any(
                query,
                historical_terms
            ):

                selected.append(
                    "HistoricalAgent"
                )

        ############################################################
        # Remove duplicates
        ############################################################

        selected = list(
            dict.fromkeys(
                selected
            )
        )

        ############################################################
        # Conservative fallback
        ############################################################

        if not selected:

            selected = [
                "WeatherAgent",
                "SoilAgent",
                "SatelliteAgent"
            ]

        ############################################################
        # Recommendation always last
        ############################################################

        selected.append(
            "RecommendationAgent"
        )

        ############################################################
        # Build execution plan
        ############################################################

        execution_plan = []

        for priority, agent in enumerate(
            selected,
            start=1
        ):

            execution_plan.append(
                {
                    "agent": agent,
                    "priority": priority,
                    "purpose":
                        self.agent_purposes[agent]
                }
            )

        return {
            "goal": user_query,
            "execution_plan": execution_plan,
            "confidence": 0.85
        }

    ######################################################################
    # Public Planning Method
    ######################################################################

    def plan(
        self,
        user_query,
        context,
        retries=1
    ):
        """
        Generate a dynamic execution plan.

        The LLM is attempted first.
        Deterministic routing is used only if the LLM fails.
        """

        prompt = self.build_prompt(
            user_query,
            context
        )

        ############################################################
        # LLM planner
        ############################################################

        for attempt in range(
            retries + 1
        ):

            try:

                raw = self.call_llm(
                    prompt
                )

                print()
                print("=" * 70)
                print("RAW PLANNER RESPONSE")
                print("=" * 70)
                print()
                print(raw)
                print()

                ####################################################
                # Parse
                ####################################################

                parsed = self.extract_json(
                    raw
                )

                ####################################################
                # Normalize
                ####################################################

                normalized = self.normalize_schema(
                    parsed,
                    user_query
                )

                ####################################################
                # Validate
                ####################################################

                validated = self.validate_plan(
                    normalized,
                    user_query
                )

                return validated

            except Exception as error:

                print()

                print(
                    f"Planner attempt {attempt + 1} failed: "
                    f"{error}"
                )

                print()

        ############################################################
        # Deterministic fallback
        ############################################################

        print(
            "⚠ LLM planner failed validation."
        )

        print(
            "Using query-aware deterministic routing."
        )

        print()

        fallback = self.build_fallback_plan(
            user_query
        )

        return self.validate_plan(
            fallback,
            user_query
        )


##########################################################################
# Singleton
##########################################################################

planner = Planner()