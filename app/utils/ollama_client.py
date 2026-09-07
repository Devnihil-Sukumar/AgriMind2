"""
==========================================================================
AgriMind

Ollama Client

Central wrapper for local Ollama inference.
==========================================================================
"""

import logging
import os
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Shared Ollama client for local specialist inference.

    Responsibilities
    ----------------
    1. Connect to local Ollama.
    2. Execute chat prompts.
    3. Disable unnecessary Qwen thinking.
    4. Enforce JSON output for specialist agents.
    5. Limit generated output size.
    6. Handle timeout/network errors.
    7. Return standardized text responses.
    """

    def __init__(self):

        self.url = os.getenv(
            "OLLAMA_URL",
            "http://localhost:11434/api/chat"
        )

        self.model = os.getenv(
            "OLLAMA_MODEL",
            "gpt-oss:20b"
        )

        self.temperature = float(
            os.getenv(
                "OLLAMA_TEMPERATURE",
                "0.2"
            )
        )

        # Keep 300 because your full specialist prompts
        # are currently taking longer locally.
        self.timeout = int(
            os.getenv(
                "OLLAMA_TIMEOUT",
                "300"
            )
        )

        # Specialist outputs are intentionally compact.
        self.num_predict = int(
            os.getenv(
                "OLLAMA_NUM_PREDICT",
                "512"
            )
        )

        logger.info(
            "Ollama client initialized: model=%s url=%s "
            "timeout=%ss num_predict=%s thinking=False json=True",
            self.model,
            self.url,
            self.timeout,
            self.num_predict
        )

    ####################################################################
    # Generate
    ####################################################################

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate a response from Ollama.

        Qwen3 thinking is disabled because the specialist agents
        require concise structured outputs.

        Ollama JSON mode is enabled so the model is constrained
        to return a JSON object rather than free-form reasoning.
        """

        if not prompt or not str(prompt).strip():

            raise ValueError(
                "Ollama prompt cannot be empty."
            )

        messages = []

        if system_prompt:

            messages.append(
                {
                    "role": "system",
                    "content": system_prompt
                }
            )

        messages.append(
            {
                "role": "user",
                "content": str(prompt)
            }
        )

        payload = {

            "model": self.model,

            "messages": messages,

            "stream": False,

            ############################################################
            # Disable Qwen3 thinking
            ############################################################

            "think": False,

            ############################################################
            # Force JSON output
            ############################################################

            "format": "json",

            ############################################################
            # Generation options
            ############################################################

            "options": {

                "temperature": (
                    self.temperature
                    if temperature is None
                    else temperature
                ),

                "num_predict": (
                    self.num_predict
                    if max_tokens is None
                    else max(1, int(max_tokens))
                )
            }
        }

        logger.debug(
            "Sending Ollama request: model=%s prompt_chars=%d",
            self.model,
            len(str(prompt))
        )

        try:

            response = requests.post(

                self.url,

                json=payload,

                timeout=self.timeout

            )

            response.raise_for_status()

            data = response.json()

        except requests.exceptions.Timeout as error:

            raise RuntimeError(
                f"Ollama request timed out after "
                f"{self.timeout} seconds."
            ) from error

        except requests.exceptions.ConnectionError as error:

            raise RuntimeError(
                "Could not connect to Ollama at "
                f"{self.url}. Make sure Ollama is running."
            ) from error

        except requests.exceptions.RequestException as error:

            raise RuntimeError(
                f"Ollama request failed: {error}"
            ) from error

        except ValueError as error:

            raise RuntimeError(
                "Ollama returned invalid JSON."
            ) from error

        ################################################################
        # Response validation
        ################################################################

        message = data.get(
            "message"
        )

        if not isinstance(
            message,
            dict
        ):

            raise RuntimeError(
                "Ollama returned an invalid response."
            )

        content = message.get(
            "content"
        )

        if not content:

            raise RuntimeError(
                "Ollama returned empty content."
            )

        content = str(
            content
        ).strip()

        ################################################################
        # Final JSON validation
        #
        # Even though Ollama JSON mode is enabled, validate once here
        # so malformed responses are caught before reaching BaseAgent.
        ################################################################

        try:

            import json

            parsed = json.loads(
                content
            )

            if not isinstance(
                parsed,
                dict
            ):

                raise ValueError(
                    "Ollama response is not a JSON object."
                )

        except (json.JSONDecodeError, ValueError) as error:

            raise RuntimeError(
                f"Ollama returned invalid structured JSON: "
                f"{error}"
            ) from error

        return content

    ####################################################################
    # Ping
    ####################################################################

    def ping(self) -> bool:
        """
        Check whether Ollama is reachable.
        """

        try:

            tags_url = self.url.replace(
                "/api/chat",
                "/api/tags"
            )

            response = requests.get(
                tags_url,
                timeout=10
            )

            return response.ok

        except Exception:

            return False

    ####################################################################
    # Model Check
    ####################################################################

    def model_available(self) -> bool:
        """
        Check whether the configured model exists locally.
        """

        try:

            tags_url = self.url.replace(
                "/api/chat",
                "/api/tags"
            )

            response = requests.get(
                tags_url,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

            models = data.get(
                "models",
                []
            )

            for model in models:

                name = model.get(
                    "name",
                    ""
                )

                if name == self.model:

                    return True

            return False

        except Exception:

            return False


##########################################################################
# Singleton
##########################################################################

ollama_client = OllamaClient()