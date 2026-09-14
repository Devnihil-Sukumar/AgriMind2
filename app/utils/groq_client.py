"""
==========================================================================
AgriMind

Groq Client

Central Groq API wrapper used throughout the project.

Author : AgriMind Team
==========================================================================
"""

import os
import re
import time
import logging
from dotenv import load_dotenv
from groq import Groq

from app.utils.prompt_budget import estimate_tokens
from app.utils.rate_limiter import TokenRateLimiter

load_dotenv()

logger = logging.getLogger(__name__)


class GroqClient:
    """
    Shared Groq Client

    Responsibilities
    ----------------
    1. Connect to Groq
    2. Execute prompts
    3. Retry failed requests
    4. Standardize responses
    """

    ####################################################################
    # Constructor
    ####################################################################

    def __init__(self):

        # Not raising here on a missing key lets this module import
        # cleanly on an Ollama-only setup with no Groq key at all --
        # the module-level singleton below is constructed unconditionally
        # by llm_client.py regardless of which provider is actually
        # configured. The key is only required once generate() is
        # actually called.

        api_key = os.getenv("GROQ_API_KEY")

        self.client = Groq(api_key=api_key) if api_key else None

        ################################################################

        self.model = os.getenv(

            "GROQ_MODEL",

            "openai/gpt-oss-120b"

        )

        self.temperature = float(

            os.getenv(

                "GROQ_TEMPERATURE",

                0.2

            )

        )

        self.max_tokens = int(

            os.getenv(

                "GROQ_MAX_TOKENS",

                4096

            )

        )

        self.retries = int(

            os.getenv(

                "GROQ_RETRIES",

                3

            )

        )

        ################################################################
        # Tokens-per-minute budget
        #
        # Groq counts prompt tokens plus the max_tokens reservation
        # against this allowance. The Recommendation Agent and the
        # Explanation Engine fire back to back, so without pacing the
        # second call lands inside the first request window and fails
        # with HTTP 429 or 413.
        ################################################################

        self.tokens_per_minute = int(

            os.getenv(

                "GROQ_TPM",

                8000

            )

        )

        self.limiter = TokenRateLimiter(

            tokens_per_minute=self.tokens_per_minute,

            name="groq"

        )

        logger.info(

            f"Groq model loaded: {self.model} "
            f"(tpm budget: {self.tokens_per_minute})"

        )

    ####################################################################
    # Generate
    ####################################################################

    def generate(

        self,

        prompt: str,

        system_prompt: str = "",

        temperature: float | None = None,

        max_tokens: int | None = None

    ) -> str:

        if self.client is None:

            raise ValueError(
                "GROQ_API_KEY environment variable not found -- "
                "cannot call Groq's generate()."
            )

        if temperature is None:

            temperature = self.temperature

        ################################################################
        # Completion reservation
        #
        # Groq counts prompt tokens + max_tokens against the per-minute
        # budget, so an oversized default reservation can trigger an
        # HTTP 413 even for a modest prompt. Callers that know how long
        # their answer needs to be pass an explicit ceiling.
        ################################################################

        if max_tokens is None:

            max_tokens = self.max_tokens

        max_tokens = max(
            1,
            int(max_tokens)
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

                "content": prompt

            }

        )

        last_exception = None

        ################################################################
        # Pace against the per-minute token budget
        ################################################################

        estimated_cost = estimate_tokens(
            prompt
        ) + estimate_tokens(
            system_prompt
        ) + max_tokens

        waited = self.limiter.acquire(
            estimated_cost
        )

        if waited:

            logger.info(
                "Groq request paced: waited %.1fs for token budget "
                "(estimated cost %d tokens).",
                waited,
                estimated_cost
            )

        ################################################################

        for attempt in range(

            1,

            self.retries + 1

        ):

            try:

                response = self.client.chat.completions.create(

                    model=self.model,

                    messages=messages,

                    temperature=temperature,

                    max_tokens=max_tokens

                )

                text = (

                    response

                    .choices[0]

                    .message

                    .content

                )

                return self.clean_response(

                    text

                )

            except Exception as e:

                last_exception = e

                logger.warning(

                    f"Groq attempt {attempt} failed: {e}"

                )

                message = str(e)

                ########################################################
                # HTTP 413: the request is larger than the allowance.
                # Retrying cannot help, so fail immediately and let the
                # caller fall back.
                ########################################################

                if self.is_request_too_large(
                    message
                ):

                    raise RuntimeError(

                        "Groq rejected the request as too large. "
                        "Reduce the prompt or the max_tokens budget "
                        "for this component.\n"
                        + message

                    ) from e

                if attempt >= self.retries:

                    break

                ########################################################
                # HTTP 429: honour the cooldown Groq reports rather
                # than retrying after one second and failing again.
                ########################################################

                delay = self.retry_delay(
                    message,
                    attempt
                )

                logger.info(
                    "Retrying Groq in %.1fs",
                    delay
                )

                time.sleep(

                    delay

                )

        ################################################################

        raise RuntimeError(

            f"Groq failed after {self.retries} retries.\n"

            f"{last_exception}"

        )

    ####################################################################
    # Error Classification
    ####################################################################

    @staticmethod
    def is_request_too_large(
        message: str
    ) -> bool:
        """
        True for HTTP 413 / request-too-large responses.
        """

        text = str(message).lower()

        return (
            "413" in text
            or "request too large" in text
            or "request_too_large" in text
        )

    @staticmethod
    def retry_delay(
        message: str,
        attempt: int
    ) -> float:
        """
        Seconds to wait before retrying.

        Groq reports the remaining cooldown inside rate-limit errors,
        for example "Please try again in 12.5s". Honouring that value
        is far more likely to succeed than a one-second backoff.
        """

        match = re.search(
            r"try again in\s+([0-9]+(?:\.[0-9]+)?)\s*(ms|s|m)?",
            str(message),
            re.IGNORECASE
        )

        if match:

            value = float(
                match.group(1)
            )

            unit = (
                match.group(2)
                or "s"
            ).lower()

            if unit == "ms":

                value = value / 1000.0

            elif unit == "m":

                value = value * 60.0

            return min(
                value + 0.5,
                70.0
            )

        text = str(message).lower()

        if "429" in text or "rate limit" in text:

            return min(
                15.0 * attempt,
                70.0
            )

        return float(
            attempt
        )

    ####################################################################
    # Remove Markdown
    ####################################################################

    @staticmethod
    def clean_response(

        text: str

    ) -> str:

        if text is None:

            return ""

        text = text.strip()

        text = text.replace(

            "```json",

            ""

        )

        text = text.replace(

            "```",

            ""

        )

        return text.strip()

    ####################################################################
    # Ping
    ####################################################################

    def ping(self):

        try:

            self.generate(

                "Reply with OK.",

                max_tokens=16

            )

            return True

        except Exception:

            return False


##########################################################################
# Singleton
##########################################################################

groq_client = GroqClient()