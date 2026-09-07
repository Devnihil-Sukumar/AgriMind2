from pprint import pprint

from app.agents.crop_knowledge_agent import crop_knowledge_agent
from app.collectors.market_collector import market_collector


def test(

    latitude,

    longitude,

    crop,

    district="Coimbatore"

):

    print("=" * 80)

    print(

        f"TESTING MARKET COLLECTOR"

    )

    print(

        f"CROP      : {crop.upper()}"

    )

    print(

        f"LOCATION  : {district}"

    )

    print(

        f"COORDINATE: ({latitude}, {longitude})"

    )

    print("=" * 80)

    ############################################################
    # Crop Knowledge
    ############################################################

    crop_result = crop_knowledge_agent.execute(

        crop

    )

    crop_profile = crop_result["crop_profile"]

    ############################################################
    # Market Collector
    ############################################################

    result = market_collector.collect(

        crop_profile=crop_profile,

        district=district,

        latitude=latitude,

        longitude=longitude

    )

    ############################################################
    # Status
    ############################################################

    print("\nSTATUS")
    print("-" * 80)

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
    print("-" * 80)

    print(

        result.get(

            "source",

            "unknown"

        )

    )

    ############################################################
    # Nearest Market
    ############################################################

    print("\nNEAREST MARKET")
    print("-" * 80)

    pprint(

        result.get(

            "nearest_market",

            {}

        )

    )

    ############################################################
    # Top 5 Markets
    ############################################################

    print("\nTOP 5 MARKETS")
    print("-" * 80)

    top_markets = result.get(

        "top_markets",

        []

    )

    for market in top_markets:

        print(

            f"{market.get('rank', '?')}. "

            f"{market.get('market', 'Unknown')} | "

            f"District: "

            f"{market.get('district', 'Unknown')} | "

            f"Price: "

            f"{market.get('price', 0)} | "

            f"Distance: "

            f"{market.get('distance_km', 0)} km | "

            f"Trend: "

            f"{market.get('trend', 'Unknown')} | "

            f"Score: "

            f"{market.get('market_score', 0)}"

        )

    ############################################################
    # RAW DATA
    ############################################################

    print("\nRAW DATA")
    print("-" * 80)

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
    print("-" * 80)

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
    print("-" * 80)

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
    print("-" * 80)

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

    ) == "market"

    assert result.get(

        "nearest_market"

    ) is not None

    assert len(

        top_markets

    ) > 0

    assert len(

        top_markets

    ) <= 5

    ############################################################
    # Ranking Validation
    ############################################################

    distances = [

        market["distance_km"]

        for market in top_markets

    ]

    assert all(

        distance >= 0

        for distance in distances

    )

    print("\n" + "=" * 80)

    print("✓ MARKET COLLECTOR TEST PASSED")

    print("=" * 80)


if __name__ == "__main__":

    test(

        latitude=11.0168,

        longitude=76.9558,

        crop="mango",

        district="Coimbatore"

    )