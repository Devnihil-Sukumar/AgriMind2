"""
Baseline evaluation matrix: 5 crops x 4 query types, with the
yield-optimization query repeated 3x per crop for consistency /
variance analysis. 30 runs total. Uses the server default location
for every run (location held constant as a controlled variable).

Resumable: re-running this script skips any run_id that already has
a saved result in evaluation/data/raw/.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness_utils import run_and_save, RAW_DIR, log_event  # noqa: E402

DEFAULT_LAT = 11.0168
DEFAULT_LON = 76.9558

CROPS = ["rice", "cotton", "wheat", "mango", "tomato"]

QUERY_TEMPLATES = {
    "yield": "What should I do to maximize {crop} yield this season?",
    "irrigation": "Is it a good time to irrigate my {crop} field?",
    "suitability": "Is {crop} suitable to grow in this location right now, and what are the risks?",
    "market": "Is now a good time to sell my {crop} harvest?",
}

REPEATS = {
    "yield": 3,
    "irrigation": 1,
    "suitability": 1,
    "market": 1,
}


def build_matrix():
    jobs = []
    for crop in CROPS:
        for query_type, template in QUERY_TEMPLATES.items():
            for rep in range(1, REPEATS[query_type] + 1):
                run_id = f"{crop}_{query_type}_r{rep}"
                jobs.append({
                    "run_id": run_id,
                    "crop": crop,
                    "query_type": query_type,
                    "repeat": rep,
                    "query": template.format(crop=crop),
                })
    return jobs


def main():
    jobs = build_matrix()
    log_event({"phase": "baseline", "run_id": "-", "status": "matrix_built",
                "note": f"{len(jobs)} jobs"})

    for job in jobs:
        run_and_save(
            directory=RAW_DIR,
            run_id=job["run_id"],
            user_query=job["query"],
            crop=job["crop"],
            latitude=DEFAULT_LAT,
            longitude=DEFAULT_LON,
            phase="baseline",
            extra_meta={"query_type": job["query_type"], "repeat": job["repeat"]},
        )

    log_event({"phase": "baseline", "run_id": "-", "status": "matrix_complete"})


if __name__ == "__main__":
    main()
