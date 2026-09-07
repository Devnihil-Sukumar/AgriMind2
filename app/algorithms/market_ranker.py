"""
==========================================================================
AgriMind

Market Ranker

Responsibilities
----------------
1. Calculate geographic distance using Haversine formula.
2. Filter nearby markets.
3. Score markets using price, trend, and distance.
4. Return top-ranked markets.

Author : AgriMind Team
==========================================================================
"""

import math


class MarketRanker:

    ####################################################################
    # Haversine Distance
    ####################################################################

    def haversine(

        self,

        latitude_1,
        longitude_1,

        latitude_2,
        longitude_2

    ):

        radius = 6371.0

        lat1 = math.radians(latitude_1)
        lat2 = math.radians(latitude_2)

        delta_lat = math.radians(

            latitude_2 - latitude_1

        )

        delta_lon = math.radians(

            longitude_2 - longitude_1

        )

        value = (

            math.sin(delta_lat / 2) ** 2

            +

            math.cos(lat1)

            * math.cos(lat2)

            * math.sin(delta_lon / 2) ** 2

        )

        return (

            2

            * radius

            * math.asin(

                math.sqrt(value)

            )

        )

    ####################################################################
    # Trend Score
    ####################################################################

    def trend_score(

        self,

        trend

    ):

        trend = str(

            trend

        ).strip().lower()

        scores = {

            "increasing": 1.0,

            "stable": 0.7,

            "volatile": 0.4,

            "decreasing": 0.2

        }

        return scores.get(

            trend,

            0.5

        )

    ####################################################################
    # Rank Markets
    ####################################################################

    def rank(

        self,

        markets,

        latitude,

        longitude,

        top_k=5

    ):

        if not markets:

            return []

        records = list(markets)

        prices = [

            float(

                row.get(

                    "Modal_Price",

                    row.get(

                        "Price",

                        0

                    )

                )

            )

            for row in records

        ]

        max_price = max(

            prices

        ) if prices else 1

        min_price = min(

            prices

        ) if prices else 0

        price_range = max(

            max_price - min_price,

            1

        )

        ranked = []

        for row in records:

            market_lat = float(

                row["Latitude"]

            )

            market_lon = float(

                row["Longitude"]

            )

            distance = self.haversine(

                latitude,

                longitude,

                market_lat,

                market_lon

            )

            price = float(

                row.get(

                    "Modal_Price",

                    row.get(

                        "Price",

                        0

                    )

                )

            )

            normalized_price = (

                (price - min_price)

                / price_range

            )

            distance_score = 1 / (

                1 + distance

            )

            trend = self.trend_score(

                row.get(

                    "Trend",

                    "Stable"

                )

            )

            score = (

                0.50 * normalized_price

                +

                0.30 * trend

                +

                0.20 * distance_score

            )

            item = dict(row)

            item["distance_km"] = round(

                distance,

                2

            )

            item["market_score"] = round(

                score,

                4

            )

            ranked.append(

                item

            )

        ranked.sort(

            key=lambda x: (

                x["market_score"],

                x.get(

                    "Modal_Price",

                    x.get(

                        "Price",

                        0

                    )

                )

            ),

            reverse=True

        )

        for index, item in enumerate(

            ranked[:top_k],

            start=1

        ):

            item["rank"] = index

        return ranked[:top_k]


##########################################################################

market_ranker = MarketRanker()