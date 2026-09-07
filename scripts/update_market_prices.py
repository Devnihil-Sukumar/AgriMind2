"""
==========================================================================
AgriMind

Daily Market Price Updater

data/market_prices.csv is a synthetic, scenario-controlled dataset
(see market_tool.py's own docstring and scripts/generate_synthetic_
agri_data.py) -- there is no live Agmarknet/data.gov.in API key
configured (AGMARKNET_URL in .env only points at the base website,
which has no public JSON endpoint), so this evolves prices forward
one simulated trading day at a time instead of fetching from an
external source:

    Increasing -> small upward drift
    Decreasing -> small downward drift
    Stable     -> small noise, no net drift
    Volatile   -> larger two-sided swing

Each row also has a small daily chance of its trend regime flipping,
so "Increasing" doesn't drift upward forever. Min/Max are rescaled
to keep the same spread around Modal_Price rather than being
re-randomized, so day-over-day changes stay smooth.

Idempotent per calendar day: running it twice on the same day is a
no-op (Last_Updated already matches).

Usage
-----
    python -m scripts.update_market_prices
    python -m scripts.update_market_prices --date 2026-08-30
    python -m scripts.update_market_prices --force

Author : AgriMind Team
==========================================================================
"""

import argparse
import os
import random
import sys
from datetime import date, datetime

import pandas as pd

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

CSV_PATH = os.path.join("data", "market_prices.csv")

RANDOM_SEED_SALT = 90210

##########################################################################
# Trend Drift Model
##########################################################################

DRIFT_RANGE = {

    "Increasing": (0.003, 0.012),
    "Decreasing": (-0.012, -0.003),
    "Stable": (-0.002, 0.002),
    "Volatile": (-0.03, 0.03)

}

# Daily probability a row's trend regime flips to a different one.
REGIME_CHANGE_PROBABILITY = 0.05

TRENDS = list(DRIFT_RANGE.keys())


##########################################################################
# Update One Row
##########################################################################

def evolve_row(row, rng):

    trend = str(row.get("Trend", "Stable")).strip().title()

    if trend not in DRIFT_RANGE:
        trend = "Stable"

    low, high = DRIFT_RANGE[trend]

    drift = rng.uniform(low, high)

    modal = float(row["Modal_Price"])
    minimum = float(row["Min_Price"])
    maximum = float(row["Max_Price"])

    ####################################################################
    # Preserve the existing spread ratio around Modal_Price rather
    # than re-randomizing it, so the CSV evolves smoothly day to day.
    ####################################################################

    min_ratio = minimum / modal if modal else 0.93
    max_ratio = maximum / modal if modal else 1.08

    new_modal = max(1.0, round(modal * (1 + drift)))

    row["Modal_Price"] = int(new_modal)
    row["Min_Price"] = int(round(new_modal * min_ratio))
    row["Max_Price"] = int(round(new_modal * max_ratio))

    if rng.random() < REGIME_CHANGE_PROBABILITY:
        row["Trend"] = rng.choice(TRENDS)
    else:
        row["Trend"] = trend

    return row


##########################################################################
# Update File
##########################################################################

def update_prices(csv_path, target_date, force):

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    already_current = (
        "Last_Updated" in df.columns
        and (df["Last_Updated"].astype(str) == target_date).all()
    )

    if already_current and not force:

        print(
            f"{csv_path} is already up to date for {target_date}. "
            "Nothing to do (pass --force to re-roll anyway)."
        )

        return 0

    ####################################################################
    # Seeded per target date so a re-run for the SAME date with
    # --force reproduces the same draw, but different dates diverge.
    ####################################################################

    seed = RANDOM_SEED_SALT + int(target_date.replace("-", ""))
    rng = random.Random(seed)

    df = df.apply(lambda row: evolve_row(row, rng), axis=1)
    df["Last_Updated"] = target_date

    df.to_csv(csv_path, index=False)

    return len(df)


##########################################################################
# Entry Point
##########################################################################

def main():

    parser = argparse.ArgumentParser(
        description="Evolve data/market_prices.csv forward one simulated "
                     "trading day."
    )

    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Target date (YYYY-MM-DD). Defaults to today."
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-roll even if the CSV is already marked current for "
             "--date."
    )

    args = parser.parse_args()

    ####################################################################
    # Validate date format early rather than let pandas fail later.
    ####################################################################

    datetime.strptime(args.date, "%Y-%m-%d")

    updated = update_prices(CSV_PATH, args.date, args.force)

    if updated:
        print(f"Updated {updated} market rows -> Last_Updated={args.date}")


if __name__ == "__main__":
    main()
