"""
==========================================================================
AgriMind

Synthetic Agricultural Dataset Generator

Generates reproducible synthetic soil and market datasets for
development, testing, and controlled experimentation.

Author : AgriMind Team
==========================================================================
"""

from pathlib import Path
import random

import pandas as pd


RANDOM_SEED = 2026

random.seed(

    RANDOM_SEED

)

BASE_DIR = Path(

    __file__

).resolve().parents[1]

DATA_DIR = BASE_DIR / "data"

SYNTHETIC_DIR = DATA_DIR / "synthetic"

SYNTHETIC_DIR.mkdir(

    parents=True,

    exist_ok=True

)

LOCATIONS = [

    ("Coimbatore", 11.0168, 76.9558),
    ("Tiruppur", 11.1085, 77.3411),
    ("Erode", 11.3410, 77.7172),
    ("Salem", 11.6643, 78.1460),
    ("Namakkal", 11.2189, 78.1674),
    ("Karur", 10.9601, 78.0766),
    ("Trichy", 10.7905, 78.7047),
    ("Thanjavur", 10.7867, 79.1378),
    ("Tiruvarur", 10.7660, 79.6344),
    ("Nagapattinam", 10.7672, 79.8449),
    ("Madurai", 9.9252, 78.1198),
    ("Dindigul", 10.3673, 77.9803),
    ("Theni", 10.0104, 77.4768),
    ("Sivaganga", 9.8433, 78.4809),
    ("Ramanathapuram", 9.3639, 78.8395),
    ("Tirunelveli", 8.7139, 77.7567),
    ("Thoothukudi", 8.7642, 78.1348),
    ("Kanyakumari", 8.0883, 77.5385),
    ("Cuddalore", 11.7480, 79.7714),
    ("Villupuram", 11.9401, 79.4861),
    ("Kallakurichi", 11.7401, 78.9597),
    ("Vellore", 12.9165, 79.1325),
    ("Ranipet", 12.9240, 79.3333),
    ("Tirupattur", 12.4960, 78.5645),
    ("Tiruvannamalai", 12.2253, 79.0747),
    ("Kanchipuram", 12.8342, 79.7036),
    ("Chengalpattu", 12.6819, 79.9671),
    ("Thiruvallur", 13.1439, 79.9087),
    ("Krishnagiri", 12.5186, 78.2137),
    ("Dharmapuri", 12.1211, 78.1582)

]

CROPS = [

    "Rice",
    "Cotton",
    "Banana",
    "Mango",
    "Maize",
    "Turmeric",
    "Coconut",
    "Groundnut",
    "Tomato",
    "Sugarcane",
    "Chilli",
    "Tapioca",
    "Onion",
    "Gingelly",
    "Black Gram"

]

BASE_PRICES = {

    "Rice": 2350,
    "Cotton": 7150,
    "Banana": 3400,
    "Mango": 3720,
    "Maize": 2050,
    "Turmeric": 9100,
    "Coconut": 12200,
    "Groundnut": 6350,
    "Tomato": 1800,
    "Sugarcane": 3200,
    "Chilli": 7800,
    "Tapioca": 2450,
    "Onion": 2700,
    "Gingelly": 7200,
    "Black Gram": 7600

}


def generate_soil():

    rows = []

    profiles = [

        ("Loam", 6.4, 42, 28, "Good"),
        ("Clay Loam", 6.7, 38, 34, "Good"),
        ("Sandy Loam", 6.8, 58, 18, "Moderate"),
        ("Clay", 6.9, 32, 40, "Moderate"),
        ("Red Loam", 6.2, 48, 24, "Good")

    ]

    for district, latitude, longitude in LOCATIONS:

        for texture, ph_base, sand_base, clay_base, drainage in profiles:

            ph = round(

                max(

                    5.5,

                    min(

                        7.5,

                        ph_base

                        + random.uniform(

                            -0.25,

                            0.25

                        )

                    )

                ),

                2

            )

            sand = max(

                20,

                min(

                    70,

                    sand_base + random.randint(

                        -4,

                        4

                    )

                )

            )

            clay = max(

                12,

                min(

                    50,

                    clay_base + random.randint(

                        -4,

                        4

                    )

                )

            )

            silt = 100 - sand - clay

            rows.append(

                [

                    "Tamil Nadu",
                    district,
                    latitude,
                    longitude,
                    texture,
                    ph,
                    random.choice(

                        [

                            "Low",

                            "Medium",

                            "High"

                        ]

                    ),
                    random.choice(

                        [

                            "Low",

                            "Medium",

                            "High"

                        ]

                    ),
                    sand,
                    clay,
                    silt,
                    round(

                        random.uniform(

                            10,

                            24

                        ),

                        2

                    ),
                    round(

                        random.uniform(

                            1.20,

                            1.60

                        ),

                        2

                    ),
                    round(

                        random.uniform(

                            0.22,

                            0.38

                        ),

                        2

                    ),
                    round(

                        random.uniform(

                            0.09,

                            0.18

                        ),

                        2

                    ),
                    drainage

                ]

            )

    columns = [

        "State",
        "District",
        "Latitude",
        "Longitude",
        "Texture",
        "pH",
        "Nitrogen",
        "Organic_Carbon",
        "Sand",
        "Clay",
        "Silt",
        "CEC",
        "Bulk_Density",
        "Field_Capacity",
        "Wilting_Point",
        "Drainage"

    ]

    output = pd.DataFrame(

        rows,

        columns=columns

    )

    output.to_csv(

        SYNTHETIC_DIR / "soil_data_synthetic.csv",

        index=False

    )

    return len(output)


def generate_market():

    rows = []

    trends = [

        "Increasing",
        "Stable",
        "Decreasing",
        "Volatile"

    ]

    for crop_index, crop in enumerate(CROPS):

        base = BASE_PRICES[crop]

        for location_index, (

            district,

            latitude,

            longitude

        ) in enumerate(LOCATIONS):

            variation = (

                (

                    location_index % 9

                )

                - 4

            ) * (

                base * 0.012

            )

            noise = random.uniform(

                -base * 0.025,

                base * 0.025

            )

            modal = int(

                round(

                    base

                    +

                    variation

                    +

                    noise

                )

            )

            minimum = int(

                round(

                    modal * random.uniform(

                        0.90,

                        0.96

                    )

                )

            )

            maximum = int(

                round(

                    modal * random.uniform(

                        1.04,

                        1.12

                    )

                )

            )

            rows.append(

                [

                    "Tamil Nadu",
                    district,
                    latitude,
                    longitude,
                    crop,
                    f"{district} Market",
                    minimum,
                    maximum,
                    modal,
                    trends[

                        (

                            crop_index

                            +

                            location_index

                        )

                        %

                        len(trends)

                    ],

                    "2026-08-14"

                ]

            )

    columns = [

        "State",
        "District",
        "Latitude",
        "Longitude",
        "Crop",
        "Market",
        "Min_Price",
        "Max_Price",
        "Modal_Price",
        "Trend",
        "Last_Updated"

    ]

    output = pd.DataFrame(

        rows,

        columns=columns

    )

    output.to_csv(

        SYNTHETIC_DIR / "market_prices_synthetic.csv",

        index=False

    )

    return len(output)


if __name__ == "__main__":

    soil_count = generate_soil()

    market_count = generate_market()

    print(

        f"Soil records generated: {soil_count}"

    )

    print(

        f"Market records generated: {market_count}"

    )