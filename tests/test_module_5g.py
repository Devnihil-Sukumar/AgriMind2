from pprint import pprint

from app.orchestrator.dynamic_orchestrator import (
    dynamic_orchestrator
)


def run_test():

    print("=" * 80)
    print("TESTING MODULE 5G - EXPLAINABLE RECOMMENDATION")
    print("=" * 80)

    result = dynamic_orchestrator.run(

        user_query="How can I maximize mango yield and profit this season?",

        crop="mango",

        latitude=11.0168,

        longitude=76.9558

    )

    execution = result["execution"]

    print("\n")
    print("=" * 80)
    print("EXECUTIVE DECISION")
    print("=" * 80)

    pprint(

        execution["executive"]

    )

    print("\n")
    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    pprint(

        execution["recommendation"]

    )

    print("\n")
    print("=" * 80)
    print("EXPLAINABLE RECOMMENDATION")
    print("=" * 80)

    pprint(

        execution["explanation"]

    )

    print("\n")
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(

        "Executive Decision :",

        execution["executive"].get(

            "executive_decision"

        )

    )

    print(

        "Recommendation :",

        execution["recommendation"].get(

            "recommendation"

        )

    )

    print(

        "Confidence :",

        execution["explanation"].get(

            "overall_confidence"

        )

    )

    print("\n")
    print("=" * 80)
    print("MODULE 5G TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":

    run_test()
    