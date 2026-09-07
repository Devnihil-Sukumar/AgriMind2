import json
import os
from dataclasses import asdict

from app.models.specialist_output import SpecialistOutput
from app.utils.json_extract import extract_json_object
from app.utils.llm_client import llm_client
from app.utils.provider_config import get_provider

##########################################################################
# Uniform-provider override
#
# By default the specialists are deliberately split across providers:
# Weather/Soil run a small local model, the rest run a large hosted one.
# That split is right for deployment cost, but it makes any cross-agent
# LATENCY comparison meaningless, because a CPU-hosted 4B model and a
# cloud-hosted 120B model differ by an order of magnitude for reasons
# that have nothing to do with the agent's logic or the architecture.
#
# Setting AGRIMIND_FORCE_PROVIDER=groq (or ollama) routes every
# specialist through one provider, so a latency ablation measures
# architectural overhead on a single hardware tier rather than the
# local-vs-cloud gap. Used for the controlled timing runs reported in
# the evaluation; unset in normal operation.
##########################################################################

FORCE_PROVIDER = os.getenv("AGRIMIND_FORCE_PROVIDER", "").strip().lower() or None


class BaseAgent:
    """
    Base class for all LLM-powered specialist agents.

    Each specialist can select its own provider:

        provider = "ollama"
        provider = "groq"

    If provider is not explicitly defined, the component-level
    provider configuration is used.
    """

    name = "BaseAgent"

    prompt = ""

    # Component used by provider_config.py
    component = None

    # Optional explicit provider
    provider = None

    ####################################################################
    # LLM Provider
    ####################################################################

    def get_llm_provider(self):

        ################################################################
        # A forced provider outranks the per-agent choice, so a timing
        # run can hold hardware constant across all specialists.
        ################################################################

        if FORCE_PROVIDER:

            return FORCE_PROVIDER

        if self.provider:

            return str(
                self.provider
            ).strip().lower()

        if self.component:

            return get_provider(
                self.component
            )

        return "groq"

    ####################################################################
    # Build Prompt
    ####################################################################

    def build_prompt(self, context):

        context_json = json.dumps(
            context,
            indent=4,
            default=str
        )

        return f"""
{self.prompt}

======================================================

Farm Context

{context_json}

======================================================

Return ONLY valid JSON.
"""

    ####################################################################
    # Parse JSON
    ####################################################################

    def parse(self, response):

        if not response:

            raise ValueError(
                "LLM returned an empty response."
            )

        return extract_json_object(
            response,
            error_label=self.name
        )

    ####################################################################
    # Deterministic Summary
    ####################################################################

    def build_summary(
        self,
        analysis,
        risks,
        opportunities
    ):
        """
        Fallback specialist summary (13Q).

        Specialists that define parse_response() build their own
        domain-specific summary. This generic version keeps the
        contract intact for any specialist that does not, so the
        Explanation Engine never receives a blank summary.
        """

        summary_parts = []

        if analysis:

            summary_parts.append(
                analysis
            )

        if risks:

            summary_parts.append(
                f"{len(risks)} risk(s) identified."
            )

        if opportunities:

            summary_parts.append(
                f"{len(opportunities)} opportunity(s) identified."
            )

        if not summary_parts:

            summary_parts.append(
                f"No significant findings were returned by {self.name}."
            )

        return " ".join(
            summary_parts
        )

    ####################################################################
    # Source Availability
    ####################################################################

    def is_source_available(self, context):
        """
        True unless this agent's context section reports a failure.

        A section that is missing entirely, or whose shape does not
        include a status field, is treated as available so agents
        without a single dedicated context key are never blocked.
        """

        if not self.component:

            return True

        section = context.get(
            self.component
        )

        if not isinstance(section, dict):

            return True

        status = str(
            section.get(
                "status",
                ""
            )
        ).strip().lower()

        if not status:

            return True

        return status == "success"

    ####################################################################
    # Unavailable Output
    ####################################################################

    def build_unavailable_output(self, context):
        """
        Deterministic specialist output for a failed evidence source.

        Confidence is 0 and the analysis states the outage explicitly,
        so collaborative reasoning, evidence ranking, runtime
        limitations and Bayesian governance all see a missing source
        rather than a confident empty one.
        """

        section = context.get(
            self.component,
            {}
        )

        if not isinstance(section, dict):

            section = {}

        reason = str(
            section.get(
                "error",
                ""
            )
        ).strip()

        if not reason:

            notes = section.get(
                "assessment",
                {}
            )

            if isinstance(notes, dict):

                reason = str(
                    notes.get(
                        "notes",
                        ""
                    )
                ).strip()

        detail = f" Reason: {reason}" if reason else ""

        label = str(
            self.component
        ).replace(
            "_",
            " "
        )

        analysis = (
            f"{label.title()} evidence is unavailable for this run. "
            f"The {label} data source did not return usable data."
            f"{detail} No {label}-based assessment was produced."
        )

        output = SpecialistOutput(

            agent=self.name,

            status="unavailable",

            analysis=analysis,

            risks=[
                f"{label.title()} evidence could not be verified "
                "this run."
            ],

            opportunities=[],

            confidence=0.0,

            metadata={

                "source_status": section.get(
                    "status",
                    "unavailable"
                ),

                "source_error": reason,

                "generation_mode": "deterministic_unavailable"

            }

        )

        return asdict(
            output
        )

    ####################################################################
    # Empty Result Detection
    ####################################################################

    @staticmethod
    def is_result_empty(analysis, risks, opportunities):
        """
        True when a parsed response has no findings at all: an empty
        analysis with no risks and no opportunities.

        This is the signature of a small/quantized model echoing the
        JSON schema example back verbatim instead of analyzing the
        context (empty strings, empty arrays) rather than a genuine
        "nothing to report" finding. Left unchecked, it passes
        through as a confident-looking empty result -- this happened
        to SatelliteAgent even after real Sentinel-2 data was
        available, at confidence 0.95.
        """

        if str(analysis).strip():

            return False

        if risks:

            return False

        if opportunities:

            return False

        return True

    ####################################################################
    # Empty Response Output
    ####################################################################

    def build_empty_response_output(self, attempts):
        """
        Deterministic specialist output when the model produced no
        usable content after retrying.

        Distinct from build_unavailable_output(): here the evidence
        source itself was fine (is_source_available() already
        passed) -- the MODEL returned an empty analysis with no
        risks or opportunities. Confidence is 0 so this cannot
        masquerade as a real finding downstream.
        """

        label = str(
            self.component or self.name
        ).replace(
            "_",
            " "
        )

        analysis = (
            f"The {label} model did not produce a specific analysis "
            f"for this run after {attempts} attempt(s). No {label} "
            "findings could be extracted."
        )

        output = SpecialistOutput(

            agent=self.name,

            status="unavailable",

            analysis=analysis,

            risks=[
                f"{label.title()} analysis could not be generated "
                "this run."
            ],

            opportunities=[],

            confidence=0.0,

            metadata={

                "generation_mode": "deterministic_empty_response",

                "attempts": attempts

            }

        )

        return asdict(
            output
        )

    ####################################################################
    # Execute
    ####################################################################

    def execute(self, context):

        ############################################################
        # Skip the LLM entirely when the source has no data.
        #
        # Asking a model to analyze an empty or failed payload
        # previously produced a confident-looking but hallucinated
        # analysis (this happened with SatelliteAgent before it got
        # its own guard). Every specialist that reads a single
        # context section is gated the same way here.
        ############################################################

        if not self.is_source_available(context):

            print(
                f"→ {self.name} skipped: "
                f"{self.component} data unavailable"
            )

            return self.build_unavailable_output(
                context
            )

        ############################################################
        # Build Prompt
        ############################################################

        prompt = self.build_prompt(
            context
        )

        ############################################################
        # Select Provider
        ############################################################

        provider = self.get_llm_provider()

        print(
            f"→ {self.name} using {provider}"
        )

        ############################################################
        # Generate + Parse, with one retry on an empty result.
        #
        # A small/quantized model (this happens with qwen3:4b via
        # Ollama) can echo the JSON schema example back verbatim --
        # empty analysis, empty risks, empty opportunities -- rather
        # than analyzing the context. That previously passed straight
        # through as a confident-looking empty finding at whatever
        # confidence the template example happened to show. One retry
        # with a corrective nudge and a higher temperature catches
        # most cases; if the model still returns nothing, the
        # specialist reports itself unavailable at confidence 0
        # instead of a hallucinated non-finding.
        ############################################################

        max_attempts = 2

        analysis = ""
        risks = []
        opportunities = []
        confidence = 0.0
        metadata = {}
        summary = ""

        parse_response = getattr(
            self,
            "parse_response",
            None
        )

        for attempt in range(
            1,
            max_attempts + 1
        ):

            attempt_prompt = prompt

            retry_temperature = None

            if attempt > 1:

                attempt_prompt = (
                    f"{prompt}\n\n"
                    "IMPORTANT: Your previous response only echoed "
                    "the schema template with empty values. Replace "
                    "every field with your own analysis of the farm "
                    "context above. Do not return an empty analysis, "
                    "an empty risks list, and an empty opportunities "
                    "list together."
                )

                retry_temperature = 0.6

            raw = llm_client.generate(

                prompt=attempt_prompt,

                provider=provider,

                component=self.component,

                temperature=retry_temperature

            )

            ########################################################
            # Parse
            #
            # Specialists that define parse_response() own their own
            # extraction and build a deterministic summary (13Q).
            # Everything else falls back to the plain JSON parser.
            ########################################################

            if callable(
                parse_response
            ):

                result = parse_response(
                    raw
                )

            else:

                result = self.parse(
                    raw
                )

            ########################################################
            # Normalize fields
            ########################################################

            risks = result.get(
                "risks",
                []
            )

            opportunities = result.get(
                "opportunities",
                []
            )

            metadata = result.get(
                "metadata",
                {}
            )

            if not isinstance(
                risks,
                list
            ):

                risks = [
                    str(risks)
                ]

            if not isinstance(
                opportunities,
                list
            ):

                opportunities = [
                    str(opportunities)
                ]

            if not isinstance(
                metadata,
                dict
            ):

                metadata = {
                    "raw_metadata":
                        str(metadata)
                }

            try:

                confidence = float(
                    result.get(
                        "confidence",
                        0.0
                    )
                )

            except (
                TypeError,
                ValueError
            ):

                confidence = 0.0

            confidence = max(
                0.0,
                min(
                    confidence,
                    1.0
                )
            )

            analysis = str(
                result.get(
                    "analysis",
                    ""
                )
            )

            summary = str(
                result.get(
                    "summary",
                    ""
                )
            ).strip()

            if not self.is_result_empty(
                analysis,
                risks,
                opportunities
            ):

                break

            print(
                f"⚠ {self.name} returned an empty result "
                f"(attempt {attempt}/{max_attempts})."
            )

        ############################################################
        # Still empty after every attempt: report unavailable rather
        # than pass through a confident empty finding.
        ############################################################

        if self.is_result_empty(
            analysis,
            risks,
            opportunities
        ):

            print(
                f"→ {self.name}: no usable content after "
                f"{max_attempts} attempts."
            )

            return self.build_empty_response_output(
                max_attempts
            )

        ############################################################
        # Specialist Summary (13Q)
        ############################################################

        if not summary:

            summary = self.build_summary(
                analysis,
                risks,
                opportunities
            )

        ############################################################
        # Build Standardized Output
        ############################################################

        output = SpecialistOutput(

            agent=self.name,

            status="completed",

            analysis=analysis,

            summary=summary,

            risks=risks,

            opportunities=opportunities,

            confidence=confidence,

            metadata=metadata

        )

        ############################################################
        # Return
        ############################################################

        return asdict(
            output
        )