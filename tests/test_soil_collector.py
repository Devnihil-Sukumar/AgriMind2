from pprint import pprint

from app.agents.crop_knowledge_agent import crop_knowledge_agent
from app.collectors.soil_collector import soil_collector


def test(latitude, longitude, crop):

    print("=" * 70)
    print(
        f"TESTING {crop.upper()} @ "
        f"({latitude}, {longitude})"
    )
    print("=" * 70)

    ############################################################
    # Crop Knowledge
    ############################################################

    crop_result = crop_knowledge_agent.execute(

        crop

    )

    crop_profile = crop_result["crop_profile"]

    ############################################################
    # Soil Collector
    ############################################################

    result = soil_collector.collect(

        crop_profile=crop_profile,

        latitude=latitude,

        longitude=longitude

    )

    ############################################################
    # Status
    ############################################################

    print("\nSTATUS")
    print("-" * 70)

    print(

        result.get(

            "status",

            "unknown"

        )

    )

    ############################################################
    # Source
    ############################################################

    print("\nSOURCE")
    print("-" * 70)

    print(

        result.get(

            "source",

            "unknown"

        )

    )

    ############################################################
    # SOIL DATA
    ############################################################

    print("\nSOIL DATA")
    print("-" * 70)

    pprint(

        result.get(

            "soil",

            {}

        )

    )

    ############################################################
    # RAW DATA
    ############################################################

    print("\nRAW DATA")
    print("-" * 70)

    pprint(

        result.get(

            "raw_data",

            {}

        )

    )

    ############################################################
    # ASSESSMENT
    ############################################################

    print("\nASSESSMENT")
    print("-" * 70)

    pprint(

        result.get(

            "assessment",

            {}

        )

    )

    ############################################################
    # METADATA
    ############################################################

    print("\nMETADATA")
    print("-" * 70)

    pprint(

        result.get(

            "metadata",

            {}

        )

    )

    ############################################################
    # CONFIDENCE
    ############################################################

    print("\nCONFIDENCE")
    print("-" * 70)

    print(

        result.get(

            "confidence",

            0

        )

    )

    ############################################################
    # Validation
    ############################################################

    assert result.get(

        "status"

    ) == "success"

    assert result.get(

        "source"

    ) == "soil"

    assert result.get(

        "soil"

    ) is not None

    assert result.get(

        "assessment"

    ) is not None

    print("\n" + "=" * 70)
    print("✓ SOIL COLLECTOR TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":

    test(

        latitude=11.0168,

        longitude=76.9558,

        crop="rice"

    )