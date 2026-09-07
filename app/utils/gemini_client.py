"""
==========================================================================
AgriMind

Gemini Client

Central wrapper for Google Gemini API.
==========================================================================
"""

import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Shared Google Gemini client.

    Intended primarily for Collaborative Reasoning.
    """

    def __init__(self):

        self.api_key = os.getenv(
            "GEMINI_API_KEY"
        )

        if not self.api_key:

            raise ValueError(
                "GEMINI_API_KEY environment variable not found."
            )

        self.model = os.getenv(
            "GEMINI_MODEL",
            "gemini-3.6-flash"
        )

        self.temperature = float(
            os.getenv(
                "GEMINI_TEMPERATURE",
                "0.2"
            )
        )

        self.max_output_tokens = int(
            os.getenv(
                "GEMINI_MAX_OUTPUT_TOKENS",
                "4096"
            )
        )

        self.client = genai.Client(
            api_key=self.api_key
        )

        print(
            f"✓ Gemini model: {self.model}"
        )

    ####################################################################
    # Generate
    ####################################################################

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        response_schema: Optional[dict] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate a Gemini response.

        When response_schema is supplied, Gemini is instructed to return
        JSON conforming to that schema.
        """

        if not prompt or not str(prompt).strip():

            raise ValueError(
                "Gemini prompt cannot be empty."
            )

        selected_temperature = (
            self.temperature
            if temperature is None
            else temperature
        )

        config_kwargs = {
            "temperature": selected_temperature,
            "max_output_tokens": (
                self.max_output_tokens
                if max_tokens is None
                else max(1, int(max_tokens))
            ),
        }

        if system_prompt:

            config_kwargs[
                "system_instruction"
            ] = system_prompt

        ################################################################
        # Structured output
        ################################################################

        if response_schema is not None:

            config_kwargs[
                "response_mime_type"
            ] = "application/json"

            config_kwargs[
                "response_schema"
            ] = response_schema

        config = types.GenerateContentConfig(
            **config_kwargs
        )

        try:

            response = self.client.models.generate_content(

                model=self.model,

                contents=str(prompt),

                config=config

            )

        except Exception as error:

            raise RuntimeError(
                f"Gemini request failed: {error}"
            ) from error

        text = getattr(
            response,
            "text",
            None
        )

        if not text:

            raise RuntimeError(
                "Gemini returned an empty response."
            )

        text = str(
            text
        ).strip()

        ################################################################
        # Clean markdown fences if present
        ################################################################

        if text.startswith(
            "```"
        ):

            text = text.replace(
                "```json",
                ""
            )

            text = text.replace(
                "```",
                ""
            )

            text = text.strip()

        return text

    ####################################################################
    # JSON Generate Helper
    ####################################################################

    def generate_json(
        self,
        prompt: str,
        schema: dict,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> dict:
        """
        Generate and parse a structured JSON response.
        """

        raw = self.generate(

            prompt=prompt,

            system_prompt=system_prompt,

            temperature=temperature,

            response_schema=schema,

            max_tokens=max_tokens

        )

        try:

            result = json.loads(
                raw
            )

        except json.JSONDecodeError as error:

            raise RuntimeError(
                f"Gemini returned invalid JSON: {error}"
            ) from error

        if not isinstance(
            result,
            dict
        ):

            raise RuntimeError(
                "Gemini JSON response must be an object."
            )

        return result

    ####################################################################
    # Ping
    ####################################################################

    def ping(self) -> bool:

        try:

            self.client.models.get(
                model=self.model
            )

            return True

        except Exception as error:

            logger.warning(
                "Gemini ping failed: %s",
                error
            )

            return False


gemini_client = GeminiClient()