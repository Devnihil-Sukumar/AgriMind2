"""
==========================================================================
AgriMind

Central LLM Client

Provider-agnostic LLM routing for:
    - Groq
    - Ollama
    - Gemini
==========================================================================
"""

import logging
from typing import Optional

from app.utils.groq_client import groq_client
from app.utils.ollama_client import ollama_client
from app.utils.gemini_client import gemini_client
from app.utils.provider_config import get_provider, get_max_tokens
from app.utils.prompt_budget import enforce_budget, estimate_tokens

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Central provider-agnostic LLM client.

    Providers
    ---------
    Groq
        Planner, Market, Recommendation, Explanation

    Ollama
        Weather, Soil, Satellite, Historical

    Gemini
        Collaborative Reasoning
    """

    def __init__(self):

        self.groq_client = groq_client

        self.ollama_client = ollama_client

        self.gemini_client = gemini_client

    ####################################################################
    # Generate
    ####################################################################

    def generate(
        self,
        prompt: str,
        provider: Optional[str] = None,
        component: Optional[str] = None,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_prompt_tokens: Optional[int] = None
    ) -> str:
        """
        Generate text using the selected provider.

        Provider priority

        1. Explicit provider
        2. Component-specific provider
        3. Default provider = Groq

        Token budget
        ------------
        Groq counts prompt tokens plus the completion reservation
        against the per-minute allowance, so both are bounded here
        rather than at each call site.
        """

        ############################################################
        # Select provider
        ############################################################

        if provider:

            selected_provider = str(
                provider
            ).strip().lower()

        elif component:

            selected_provider = get_provider(
                component
            )

        else:

            selected_provider = "groq"

        ############################################################
        # Token budget
        ############################################################

        if max_tokens is None and component:

            max_tokens = get_max_tokens(
                component
            )

        if max_prompt_tokens is not None:

            prompt = enforce_budget(
                prompt,
                max_prompt_tokens
            )

        logger.info(
            "LLM request routed to provider=%s component=%s "
            "prompt_tokens~%s max_tokens=%s",
            selected_provider,
            component,
            estimate_tokens(prompt),
            max_tokens
        )

        ############################################################
        # Groq
        ############################################################

        if selected_provider == "groq":

            return self.groq_client.generate(

                prompt=prompt,

                system_prompt=system_prompt,

                temperature=temperature,

                max_tokens=max_tokens

            )

        ############################################################
        # Ollama, with a Groq fallback.
        #
        # The local model has genuinely taken 200-300s on this
        # machine even when it succeeds (see the comment in
        # ollama_client.py), so a hard timeout occasionally clips a
        # call that was simply slow, not stuck. Rather than gamble on
        # a shorter timeout -- which would fail MORE legitimate calls
        # -- fall back to the already-configured, network-fast Groq
        # provider on any Ollama failure (timeout, connection refused,
        # malformed JSON) so the specialist still gets a usable
        # response instead of reporting itself failed.
        ############################################################

        if selected_provider == "ollama":

            try:

                return self.ollama_client.generate(

                    prompt=prompt,

                    system_prompt=system_prompt,

                    temperature=temperature,

                    max_tokens=max_tokens

                )

            except Exception as error:

                logger.warning(
                    "Ollama failed for component=%s (%s); "
                    "falling back to Groq.",
                    component,
                    error
                )

                print(
                    f"⚠ Ollama unavailable for {component or 'request'} "
                    f"({error}); falling back to Groq."
                )

                ####################################################
                # Ollama-routed components have no entry in
                # DEFAULT_MAX_TOKENS (provider_config.py) since they
                # normally rely on Ollama's own, much smaller
                # num_predict -- so max_tokens is still None here.
                # Leaving it None would let Groq apply ITS OWN larger
                # default reservation on top of these components'
                # full-context prompts, which is exactly what blew
                # through Groq's 8000 TPM budget (HTTP 413) the first
                # time this fallback fired for real.
                #
                # Capping it to Ollama's own num_predict (512) is too
                # tight for this specific fallback: the Groq model
                # (openai/gpt-oss-120b) is a reasoning model that can
                # spend its whole completion budget on a chain-of-
                # thought preamble before ever emitting the JSON
                # answer, which produced a *fallback that itself
                # fails* ("did not contain a complete valid JSON
                # object") instead of the intended safety net. Give it
                # 3x the Ollama budget -- enough headroom for a short
                # reasoning preamble plus the JSON payload, while
                # still far under Groq's own 4096-token default that
                # caused the original TPM blowout.
                ####################################################

                return self.groq_client.generate(

                    prompt=prompt,

                    system_prompt=system_prompt,

                    temperature=temperature,

                    max_tokens=(
                        max_tokens
                        or self.ollama_client.num_predict * 3
                    )

                )

        ############################################################
        # Gemini
        ############################################################

        if selected_provider == "gemini":

            return self.gemini_client.generate(

                prompt=prompt,

                system_prompt=system_prompt,

                temperature=temperature,

                max_tokens=max_tokens

            )

        ############################################################
        # Unsupported
        ############################################################

        raise ValueError(

            f"Unsupported LLM provider: "
            f"{selected_provider}. "

            f"Supported providers: "
            f"groq, ollama, gemini"

        )

    ####################################################################
    # Generate JSON
    ####################################################################

    def generate_json(
        self,
        prompt: str,
        schema: dict,
        provider: Optional[str] = None,
        component: Optional[str] = None,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_prompt_tokens: Optional[int] = None
    ) -> dict:
        """
        Generate structured JSON.

        Gemini uses native structured output.
        Other providers fall back to normal text generation
        followed by JSON parsing.
        """

        ############################################################
        # Resolve provider
        ############################################################

        if provider:

            selected_provider = str(
                provider
            ).strip().lower()

        elif component:

            selected_provider = get_provider(
                component
            )

        else:

            selected_provider = "groq"

        ############################################################
        # Gemini native structured output
        ############################################################

        if selected_provider == "gemini":

            return self.gemini_client.generate_json(

                prompt=prompt,

                schema=schema,

                system_prompt=system_prompt,

                temperature=temperature,

                max_tokens=max_tokens

            )

        ############################################################
        # Other providers
        ############################################################

        import json

        raw = self.generate(

            prompt=prompt,

            provider=selected_provider,

            component=component,

            system_prompt=system_prompt,

            temperature=temperature,

            max_tokens=max_tokens,

            max_prompt_tokens=max_prompt_tokens

        )

        text = str(
            raw
        ).strip()

        text = text.replace(
            "```json",
            ""
        )

        text = text.replace(
            "```",
            ""
        )

        text = text.strip()

        start = text.find(
            "{"
        )

        end = text.rfind(
            "}"
        )

        if start == -1 or end == -1:

            raise ValueError(
                f"{selected_provider} did not return "
                "a JSON object."
            )

        try:

            result = json.loads(
                text[start:end + 1]
            )

        except json.JSONDecodeError as error:

            raise ValueError(
                f"{selected_provider} returned invalid JSON: "
                f"{error}"
            ) from error

        if not isinstance(
            result,
            dict
        ):

            raise ValueError(
                f"{selected_provider} JSON response "
                "must be an object."
            )

        return result

    ####################################################################
    # Ping
    ####################################################################

    def ping(
        self,
        provider: str
    ) -> bool:
        """
        Test connectivity to a specific provider.
        """

        selected_provider = str(
            provider
        ).strip().lower()

        ############################################################
        # Groq
        ############################################################

        if selected_provider == "groq":

            return self.groq_client.ping()

        ############################################################
        # Ollama
        ############################################################

        if selected_provider == "ollama":

            return self.ollama_client.ping()

        ############################################################
        # Gemini
        ############################################################

        if selected_provider == "gemini":

            return self.gemini_client.ping()

        return False


##########################################################################
# Singleton
##########################################################################

llm_client = LLMClient()