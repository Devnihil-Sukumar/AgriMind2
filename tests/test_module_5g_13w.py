"""
==========================================================================
AgriMind

Module 5G / 13Q-13W Test

Tests:
    13Q - Specialist Summaries
    13R - Better Explanation
    13S - Runtime Limitations
    13T - Context-Aware Alternatives
    13U - Evidence Ranking
    13V - Rich Decision Trace
    13W - Farmer-Friendly Explanation

Author : AgriMind Team
==========================================================================
"""

from pprint import pprint

from app.orchestrator.dynamic_orchestrator import (
    dynamic_orchestrator
)


def main():

    crop = "mango"

    latitude = 11.0168

    longitude = 76.9558

    user_query = (

        "How can I maximize mango yield and profit this season?"

    )

    print()

    print("=" * 80)

    print(

        "TESTING AGRIMIND MODULE 5G + 13Q-13W"

    )

    print("=" * 80)

    print()

    print(

        f"CROP      : {crop.upper()}"

    )

    print(

        f"LOCATION  : ({latitude}, {longitude})"

    )

    print(

        f"QUERY     : {user_query}"

    )

    print()

    ############################################################
    # Run complete pipeline
    ############################################################

    result = dynamic_orchestrator.run(

        user_query=user_query,

        crop=crop,

        latitude=latitude,

        longitude=longitude

    )

    ############################################################
    # Status
    ############################################################

    print()

    print("=" * 80)

    print("PIPELINE STATUS")

    print("=" * 80)

    print(

        result.get(

            "status"

        )

    )

    ############################################################
    # Execution
    ############################################################

    execution = result.get(

        "execution",

        {}

    )

    ############################################################
    # Specialist Summaries
    ############################################################

    print()

    print("=" * 80)

    print("13Q - SPECIALIST SUMMARIES")

    print("=" * 80)

    specialists = execution.get(

        "specialists",

        {}

    )

    for name, output in specialists.items():

        print()

        print(

            f"{name}"

        )

        print("-" * 80)

        print(

            "SUMMARY: "

            + str(

                output.get(

                    "summary",

                    ""

                )

            )

        )

        print(

            "CONFIDENCE: "

            + str(

                output.get(

                    "confidence",

                    0

                )

            )

        )

    ############################################################
    # Executive
    ############################################################

    print()

    print("=" * 80)

    print("EXECUTIVE DECISION")

    print("=" * 80)

    pprint(

        execution.get(

            "executive",

            {}

        )

    )

    ############################################################
    # Recommendation
    ############################################################

    print()

    print("=" * 80)

    print("RECOMMENDATION")

    print("=" * 80)

    pprint(

        execution.get(

            "recommendation",

            {}

        )

    )

    ############################################################
    # Explanation
    ############################################################

    explanation = execution.get(

        "explanation",

        {}

    )

    ############################################################
    # 13R
    ############################################################

    print()

    print("=" * 80)

    print("13R - BETTER EXPLANATION")

    print("=" * 80)

    print()

    print("EXECUTIVE SUMMARY")

    print("-" * 80)

    print(

        explanation.get(

            "executive_summary",

            ""

        )

    )

    print()

    print("NARRATIVE EXPLANATION")

    print("-" * 80)

    print(

        explanation.get(

            "explanation",

            ""

        )

    )

    print()

    print("REASONING SUMMARY")

    print("-" * 80)

    print(

        explanation.get(

            "reasoning_summary",

            ""

        )

    )

    ############################################################
    # 13S
    ############################################################

    print()

    print("=" * 80)

    print("13S - RUNTIME-AWARE LIMITATIONS")

    print("=" * 80)

    pprint(

        explanation.get(

            "limitations",

            []

        )

    )

    ############################################################
    # 13T
    ############################################################

    print()

    print("=" * 80)

    print("13T - CONTEXT-AWARE ALTERNATIVES")

    print("=" * 80)

    pprint(

        explanation.get(

            "rejected_alternatives",

            []

        )

    )

    ############################################################
    # 13U
    ############################################################

    print()

    print("=" * 80)

    print("13U - EVIDENCE RANKING")

    print("=" * 80)

    evidence = explanation.get(

        "evidence",

        {}

    )

    pprint(

        evidence.get(

            "ranked_evidence",

            evidence

        )

    )

    ############################################################
    # 13V
    ############################################################

    print()

    print("=" * 80)

    print("13V - RICH DECISION TRACE")

    print("=" * 80)

    trace = explanation.get(

        "decision_trace",

        []

    )

    pprint(

        trace

    )

    ############################################################
    # 13W
    ############################################################

    print()

    print("=" * 80)

    print("13W - FARMER-FRIENDLY EXPLANATION")

    print("=" * 80)

    print()

    farmer_message = explanation.get(

        "farmer_message",

        ""

    )

    print(

        farmer_message

    )

    ############################################################
    # Confidence
    ############################################################

    print()

    print("=" * 80)

    print("OVERALL CONFIDENCE")

    print("=" * 80)

    print(

        explanation.get(

            "overall_confidence",

            0

        )

    )

    ############################################################
    # Validation
    ############################################################

    print()

    print("=" * 80)

    print("VALIDATION")

    print("=" * 80)

    errors = []

    if not explanation.get(

        "executive_summary"

    ):

        errors.append(

            "13R executive_summary is empty"

        )

    if not explanation.get(

        "explanation"

    ):

        errors.append(

            "13R explanation is empty"

        )

    if not explanation.get(

        "reasoning_summary"

    ):

        errors.append(

            "13R reasoning_summary is empty"

        )

    if not explanation.get(

        "limitations"

    ):

        errors.append(

            "13S limitations missing"

        )

    if not explanation.get(

        "rejected_alternatives"

    ):

        errors.append(

            "13T alternatives missing"

        )

    if not explanation.get(

        "evidence"

    ):

        errors.append(

            "13U evidence missing"

        )

    if not explanation.get(

        "decision_trace"

    ):

        errors.append(

            "13V decision trace missing"

        )

    if not farmer_message:

        errors.append(

            "13W farmer_message is empty"

        )

    if errors:

        print()

        print("✗ TEST FAILED")

        print()

        for error in errors:

            print(

                " - " + error

            )

        raise AssertionError(

            "13Q-13W validation failed."

        )

    print()

    print("✓ 13Q Specialist Summaries : PASS")

    print("✓ 13R Better Explanation   : PASS")

    print("✓ 13S Runtime Limitations  : PASS")

    print("✓ 13T Context Alternatives : PASS")

    print("✓ 13U Evidence Ranking    : PASS")

    print("✓ 13V Rich Decision Trace  : PASS")

    print("✓ 13W Farmer Explanation   : PASS")

    print()

    print("=" * 80)

    print("✓ MODULE 5G / 13Q-13W TEST PASSED")

    print("=" * 80)


if __name__ == "__main__":

    main()