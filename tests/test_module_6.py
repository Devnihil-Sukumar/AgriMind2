"""
==========================================================================
AgriMind

Module 6 Test

Tests the complete dynamic crop knowledge pipeline.

Author : AgriMind Team
==========================================================================
"""

from pprint import pprint

from app.orchestrator.dynamic_orchestrator import dynamic_orchestrator


def run_test(crop, query):

    print("\n" + "=" * 80)
    print(f"TESTING CROP : {crop.upper()}")
    print("=" * 80)

    result = dynamic_orchestrator.run(

        user_query=query,

        crop=crop,

        latitude=11.0168,

        longitude=76.9558

    )

    ####################################################################
    # Crop Profile
    ####################################################################

    print("\nCROP PROFILE")
    print("-" * 80)

    pprint(result["crop_profile"])

    ####################################################################
    # Context
    ####################################################################

    print("\nCONTEXT")
    print("-" * 80)

    pprint(result["context"])

    ####################################################################
    # Planner
    ####################################################################

    print("\nEXECUTION PLAN")
    print("-" * 80)

    pprint(result["plan"])

    ####################################################################
    # Specialist Outputs
    ####################################################################

    print("\nSPECIALIST OUTPUTS")
    print("-" * 80)

    for agent, output in result["execution"]["specialists"].items():

        print(f"\n{agent}")

        pprint(output)

    ####################################################################
    # Collaborative Reasoning
    ####################################################################

    print("\nCOLLABORATIVE REASONING")
    print("-" * 80)

    pprint(result["execution"]["reasoning"])

    ####################################################################
    # Recommendation
    ####################################################################

    print("\nFINAL RECOMMENDATION")
    print("-" * 80)

    pprint(result["execution"]["recommendation"])

    ####################################################################
    # TRUSTAI Governance
    ####################################################################

    print("\nTRUSTAI GOVERNANCE")
    print("-" * 80)

    pprint(result["execution"]["governance"])

    ####################################################################

    print("\nExecution Time:", result["total_time"], "seconds")


##########################################################################


def main():

    # Another unseen crop
    run_test(

        crop="cotton",

        query="What should I do to maximize cotton yield?"

    )


##########################################################################

if __name__ == "__main__":

    main()