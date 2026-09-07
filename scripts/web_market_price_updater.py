"""
==========================================================================
AgriMind

Web Market Price Updater (OPT-IN, manual only -- NOT wired into the app)

This is a SEPARATE tool from scripts/update_market_prices.py, which is
the updater market_tool.py's own docstring documents and which the app
implicitly relies on to keep data/market_prices.csv fresh. That script
deliberately evolves prices with a seeded simulation rather than
fetching live data, because no live Agmarknet/data.gov.in API key is
configured (see its own docstring).

This script instead scrapes public search-engine result pages (Google,
Bing, DuckDuckGo) for crop-price mentions and regex-parses a price out
of whatever snippet text it finds. Before running it, understand the
tradeoffs that kept it out of the automatic pipeline:

  - Scraping Google/Bing search-result pages this way is against both
    platforms' Terms of Service (this is not their official Search
    API), and in practice tends to get rate-limited or served a
    consent/CAPTCHA page rather than usable results, especially over
    repeated runs.
  - The extracted price is a heuristic regex match over noisy natural-
    language snippet text with no structured backing source -- there
    is no guarantee it is correct, current, or even about the right
    market. Treat its output as a rough, unverified signal, not a
    trustworthy price feed.
  - Because AgriMind's MarketAgent and executive decision engine read
    data/market_prices.csv directly, feeding it unreviewed scraped
    numbers could push a real "sell now" / "hold" recommendation to a
    farmer based on a wrong price. For that reason this script never
    overwrites data/market_prices.csv directly -- it writes to a
    separate OUTPUT_FILE that a human must review and copy over
    manually if they trust it.

Run it explicitly and only when you understand the above:

    venv/Scripts/python.exe scripts/web_market_price_updater.py

Dataset schema
--------------
State, District, Latitude, Longitude, Crop, Market, Min_Price,
Max_Price, Modal_Price, Trend, Last_Updated

Purpose
-------
1. Read the AgriMind market-price dataset.
2. Search the public web for current crop-market prices.
3. Extract minimum, maximum and modal prices.
4. Estimate the current price trend from available information.
5. Update Last_Updated.
6. Preserve existing market metadata.
7. Run at most once every 24 hours.
8. Maintain a text log for update history.
==========================================================================
"""

import os
import re
import shutil
import time
from datetime import datetime, timedelta
from urllib.parse import quote_plus

import pandas as pd
import requests

from bs4 import BeautifulSoup


# ======================================================================
# CONFIGURATION
# ======================================================================

INPUT_FILE = os.getenv(
    "MARKET_PRICE_FILE",
    os.path.join("data", "market_prices.csv")
)

# Deliberately NOT data/market_prices.csv -- see module docstring.
# A human must review this file and copy it over the live dataset
# themselves before AgriMind's pipeline will ever see these numbers.
OUTPUT_FILE = os.getenv(
    "MARKET_PRICE_OUTPUT",
    os.path.join("data", "market_prices_live_updated.csv")
)

BACKUP_FILE = os.getenv(
    "MARKET_PRICE_BACKUP",
    os.path.join("data", "market_prices_backup.csv")
)

LOG_FILE = os.getenv(
    "MARKET_PRICE_LOG",
    os.path.join("logs", "web_market_price_updater.log")
)

UPDATE_INTERVAL_HOURS = 24

REQUEST_TIMEOUT = 20

SLEEP_BETWEEN_SEARCHES = 2


# ======================================================================
# WEB SEARCH
# ======================================================================

SEARCH_ENGINES = [

    "https://www.google.com/search?q={query}",

    "https://www.bing.com/search?q={query}",

    "https://html.duckduckgo.com/html/?q={query}"

]


HEADERS = {

    "User-Agent":
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/139.0.0.0 Safari/537.36"
        )

}


# ======================================================================
# TIME / LOG FUNCTIONS
# ======================================================================

def write_log(
    message
):

    timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

    os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)

    try:

        with open(
            LOG_FILE,
            "a",
            encoding="utf-8"
        ) as file:

            file.write(
                f"{timestamp} | {message}\n"
            )

    except OSError as error:

        print(
            f"Could not write log: {error}"
        )


def get_last_success_time():

    if not os.path.exists(
        LOG_FILE
    ):

        return None

    try:

        with open(
            LOG_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            lines = file.readlines()

        for line in reversed(
            lines
        ):

            line = line.strip()

            if line.startswith(
                "LAST_SUCCESS="
            ):

                timestamp = line.split(
                    "=",
                    1
                )[1].strip()

                return datetime.fromisoformat(
                    timestamp
                )

    except (
        OSError,
        ValueError
    ):

        return None

    return None


def should_run_update():

    last_success = get_last_success_time()

    if last_success is None:

        print(
            "No previous successful update found."
        )

        write_log(
            "FIRST_RUN=true"
        )

        return True

    now = datetime.now()

    elapsed = (
        now - last_success
    )

    print(
        "Last successful update : "
        f"{last_success.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        f"Elapsed time           : {elapsed}"
    )

    if elapsed >= timedelta(
        hours=UPDATE_INTERVAL_HOURS
    ):

        print(
            "24-hour interval reached."
        )

        write_log(
            "UPDATE_CHECK=ALLOWED"
        )

        return True

    remaining = (
        timedelta(
            hours=UPDATE_INTERVAL_HOURS
        )
        - elapsed
    )

    print(
        "Update skipped."
    )

    print(
        "Next update available in: "
        f"{remaining}"
    )

    write_log(
        "UPDATE_CHECK=SKIPPED"
    )

    return False


def write_last_success():

    timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

    with open(
        LOG_FILE,
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            f"LAST_SUCCESS={timestamp}\n"
        )


# ======================================================================
# NUMBER / UNIT HELPERS
# ======================================================================

NUMBER = (

    r"(?:"

    # Comma-grouped numbers (e.g. "2,600" or "12,345.67") -- the "+"
    # requires at least one comma group so this alternative doesn't
    # also match a plain number's leading digits and then stop, which
    # silently truncated e.g. "2600" to "260" when this was "*".
    r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?"

    r"|"

    r"\d+(?:\.\d+)?"

    r")"

)


UNIT_ALIASES = {

    "kg": "kg",

    "kilogram": "kg",

    "quintal": "quintal",

    "qtl": "quintal",

    "ton": "ton",

    "tonne": "ton"

}


def number(
    value
):

    return float(
        value.replace(
            ",",
            ""
        )
    )


def normalize_to_quintal(
    price,
    unit
):

    unit = UNIT_ALIASES.get(

        unit.lower(),

        unit.lower()

    )

    if unit == "kg":

        return price * 100

    if unit == "quintal":

        return price

    if unit == "ton":

        return price / 10

    return price


def detect_unit(
    text
):

    text = text.lower()

    if re.search(
        r"\b(quintal|qtl)\b",
        text
    ):

        return "quintal"

    if re.search(
        r"\b(kg|kilogram)\b",
        text
    ):

        return "kg"

    if re.search(
        r"\b(ton|tonne)\b",
        text
    ):

        return "ton"

    return None


# ======================================================================
# PRICE PARSER
# ======================================================================

PRICE_RANGE_PATTERNS = [

    # Rs.6,000 to Rs.7,600

    re.compile(

        rf"""
        (?:₹|rs\.?|inr)
        \s*({NUMBER})
        \s*(?:to|-|–|—)
        \s*(?:₹|rs\.?|inr)?
        \s*({NUMBER})
        """,

        re.I | re.X

    ),

    # 6000 to 7600 per quintal

    re.compile(

        rf"""
        ({NUMBER})
        \s*(?:to|-|–|—)
        \s*({NUMBER})
        \s*(?:/|per)?
        \s*
        (kg|kilogram|quintal|qtl|ton|tonne)
        \b
        """,

        re.I | re.X

    )

]


SINGLE_PRICE_PATTERNS = [

    # Rs.6800

    re.compile(

        rf"""
        (?:₹|rs\.?|inr)
        \s*({NUMBER})
        """,

        re.I | re.X

    ),

    # 6800 per quintal

    re.compile(

        rf"""
        ({NUMBER})
        \s*(?:/|per)
        \s*
        (kg|kilogram|quintal|qtl|ton|tonne)
        \b
        """,

        re.I | re.X

    )

]


def parse_prices(
    text
):

    candidates = []

    detected_unit = detect_unit(
        text
    )

    # --------------------------------------------------------------
    # Ranges
    # --------------------------------------------------------------

    for pattern in PRICE_RANGE_PATTERNS:

        for match in pattern.finditer(
            text
        ):

            try:

                low = number(
                    match.group(1)
                )

                high = number(
                    match.group(2)
                )

                explicit_unit = None

                if len(
                    match.groups()
                ) >= 3:

                    explicit_unit = (
                        match.group(3)
                    )

                unit = (
                    explicit_unit
                    or detected_unit
                )

                if not unit:

                    continue

                low_quintal = (
                    normalize_to_quintal(
                        low,
                        unit
                    )
                )

                high_quintal = (
                    normalize_to_quintal(
                        high,
                        unit
                    )
                )

                if low_quintal > high_quintal:

                    low_quintal, high_quintal = (
                        high_quintal,
                        low_quintal
                    )

                candidates.append({

                    "min_price":
                        round(
                            low_quintal,
                            2
                        ),

                    "max_price":
                        round(
                            high_quintal,
                            2
                        ),

                    "modal_price":
                        round(
                            (
                                low_quintal
                                + high_quintal
                            ) / 2,
                            2
                        ),

                    "unit":
                        "quintal",

                    "raw":
                        match.group(0)

                })

            except (
                ValueError,
                TypeError
            ):

                continue

    if candidates:

        return candidates

    # --------------------------------------------------------------
    # Single prices
    # --------------------------------------------------------------

    for pattern in SINGLE_PRICE_PATTERNS:

        for match in pattern.finditer(
            text
        ):

            try:

                raw_price = number(
                    match.group(1)
                )

                explicit_unit = None

                if len(
                    match.groups()
                ) >= 2:

                    explicit_unit = (
                        match.group(2)
                    )

                unit = (
                    explicit_unit
                    or detected_unit
                )

                if not unit:

                    continue

                price_quintal = (
                    normalize_to_quintal(
                        raw_price,
                        unit
                    )
                )

                if not (
                    100
                    <= price_quintal
                    <= 2_000_000
                ):

                    continue

                candidates.append({

                    "min_price":
                        round(
                            price_quintal,
                            2
                        ),

                    "max_price":
                        round(
                            price_quintal,
                            2
                        ),

                    "modal_price":
                        round(
                            price_quintal,
                            2
                        ),

                    "unit":
                        "quintal",

                    "raw":
                        match.group(0)

                })

            except (
                ValueError,
                TypeError
            ):

                continue

    return candidates


# ======================================================================
# WEB SEARCH
# ======================================================================

def search_web(
    query
):

    results = []

    for engine in SEARCH_ENGINES:

        url = engine.format(
            query=quote_plus(
                query
            )
        )

        try:

            response = requests.get(

                url,

                headers=HEADERS,

                timeout=REQUEST_TIMEOUT

            )

            response.raise_for_status()

            soup = BeautifulSoup(

                response.text,

                "html.parser"

            )

            for tag in soup([

                "script",
                "style",
                "noscript"

            ]):

                tag.decompose()

            candidates = []

            for selector in [

                "div",
                "li",
                "article",
                "p"

            ]:

                for node in soup.select(
                    selector
                ):

                    text = node.get_text(

                        " ",

                        strip=True

                    )

                    if text:

                        candidates.append(
                            text
                        )

            for text in candidates:

                if not (
                    40
                    <= len(text)
                    <= 1000
                ):

                    continue

                lower = text.lower()

                if (

                    "₹" in text

                    or "rs." in lower

                    or "inr" in lower

                    or "price" in lower

                    or "quintal" in lower

                    or "per kg" in lower

                    or "mandi" in lower

                ):

                    results.append({

                        "engine":
                            engine.split("/")[2],

                        "url":
                            url,

                        "text":
                            text

                    })

        except requests.RequestException as error:

            print(

                f"Search failed: "
                f"{engine.split('/')[2]} -> "
                f"{error}"

            )

            write_log(

                f"SEARCH_FAILED "
                f"engine={engine.split('/')[2]}"

            )

        time.sleep(
            SLEEP_BETWEEN_SEARCHES
        )

    # --------------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------------

    unique_results = []

    seen = set()

    for result in results:

        key = re.sub(

            r"\s+",

            " ",

            result["text"]

        ).strip().lower()

        if key in seen:

            continue

        seen.add(key)

        unique_results.append(
            result
        )

    return unique_results


# ======================================================================
# RESULT SCORING
# ======================================================================

def score_result(

    text,

    crop,

    market,

    district,

    state

):

    lower = text.lower()

    score = 0

    # Crop.

    if crop and crop.lower() in lower:

        score += 6

    # Market.

    if market and market.lower() in lower:

        score += 7

    # District.

    if district and district.lower() in lower:

        score += 4

    # State.

    if state and state.lower() in lower:

        score += 2

    # Agricultural keywords.

    keywords = [

        "mandi",
        "agmarknet",
        "market",
        "wholesale",
        "agriculture",
        "commodity",
        "farmer",
        "krishi"

    ]

    for keyword in keywords:

        if keyword in lower:

            score += 1

    # Freshness.

    if "today" in lower:

        score += 3

    if "latest" in lower:

        score += 3

    # Units.

    if "quintal" in lower:

        score += 2

    # Currency.

    if (

        "₹" in text

        or "rs." in lower

        or "inr" in lower

    ):

        score += 2

    return score


# ======================================================================
# TREND DETECTION
# ======================================================================

def detect_trend(
    text
):

    lower = text.lower()

    if any(

        phrase in lower

        for phrase in [

            "price increased",
            "price rises",
            "price rose",
            "price up",
            "increased today",
            "up today",
            "rising",
            "upward trend"

        ]

    ):

        return "rising"

    if any(

        phrase in lower

        for phrase in [

            "price decreased",
            "price falls",
            "price fell",
            "price down",
            "decreased today",
            "down today",
            "falling",
            "downward trend"

        ]

    ):

        return "falling"

    if any(

        phrase in lower

        for phrase in [

            "stable",
            "unchanged",
            "no change",
            "steady"

        ]

    ):

        return "stable"

    return "unknown"


# ======================================================================
# CHOOSE BEST PRICE
# ======================================================================

def choose_best_price(

    search_results,

    crop,

    market,

    district,

    state

):

    extracted = []

    for result in search_results:

        text = result["text"]

        score = score_result(

            text=text,

            crop=crop,

            market=market,

            district=district,

            state=state

        )

        if score < 7:

            continue

        parsed_prices = parse_prices(
            text
        )

        for price in parsed_prices:

            extracted.append({

                **price,

                "source":
                    result["engine"],

                "source_url":
                    result["url"],

                "evidence":
                    text[:500],

                "trend":
                    detect_trend(
                        text
                    ),

                "score":
                    score

            })

    if not extracted:

        return None

    extracted.sort(

        key=lambda item: (

            item["score"],

            len(
                item["evidence"]
            )

        ),

        reverse=True

    )

    best = extracted[0]

    if not (

        100
        <= best["modal_price"]
        <= 2_000_000

    ):

        return None

    return best


# ======================================================================
# DATASET VALIDATION
# ======================================================================

def validate_dataset(
    df
):

    required_columns = {

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

    }

    missing = (
        required_columns
        - set(df.columns)
    )

    if missing:

        raise ValueError(

            "Dataset is missing required columns: "
            f"{sorted(missing)}"

        )


# ======================================================================
# UPDATE DATASET
# ======================================================================

def perform_update():

    print("=" * 70)

    print(
        "AGRIMIND WEB MARKET PRICE UPDATER (opt-in, manual only)"
    )

    print("=" * 70)

    print(
        f"Input dataset  : {INPUT_FILE}"
    )

    print(
        f"Output dataset : {OUTPUT_FILE}  (NOT the live dataset -- "
        "review before copying over data/market_prices.csv)"
    )

    print(
        f"Log file       : {LOG_FILE}"
    )

    print("=" * 70)

    # --------------------------------------------------------------
    # Load
    # --------------------------------------------------------------

    try:

        df = pd.read_csv(
            INPUT_FILE
        )

    except FileNotFoundError:

        write_log(
            "UPDATE_FAILED=INPUT_FILE_NOT_FOUND"
        )

        raise FileNotFoundError(

            f"Dataset not found: {INPUT_FILE}"

        )

    validate_dataset(
        df
    )

    # --------------------------------------------------------------
    # Backup
    # --------------------------------------------------------------

    shutil.copy2(

        INPUT_FILE,

        BACKUP_FILE

    )

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    updated_count = 0

    unchanged_count = 0

    # --------------------------------------------------------------
    # Process every row
    # --------------------------------------------------------------

    for index, row in df.iterrows():

        state = str(
            row["State"]
        ).strip()

        district = str(
            row["District"]
        ).strip()

        crop = str(
            row["Crop"]
        ).strip()

        market = str(
            row["Market"]
        ).strip()

        print()

        print(
            f"[{index + 1}/{len(df)}] "
            f"{crop} | "
            f"{market} | "
            f"{district}, {state}"
        )

        # ----------------------------------------------------------
        # Search queries
        # ----------------------------------------------------------

        queries = [

            (
                f"{crop} price "
                f"{market} "
                f"{district} "
                f"{state} "
                f"today"
            ),

            (
                f"{crop} mandi price "
                f"{market} "
                f"{district} "
                f"{state} "
                f"today"
            ),

            (
                f"{crop} market price "
                f"{district} "
                f"{state} "
                f"today wholesale"
            )

        ]

        all_results = []

        for query in queries:

            print(
                f"Searching: {query}"
            )

            results = search_web(
                query
            )

            all_results.extend(
                results
            )

        # ----------------------------------------------------------
        # Choose best price
        # ----------------------------------------------------------

        best = choose_best_price(

            search_results=
                all_results,

            crop=crop,

            market=market,

            district=district,

            state=state

        )

        if best is None:

            print(
                "No reliable current price found."
            )

            print(
                "Keeping previous values."
            )

            unchanged_count += 1

            write_log(

                f"ROW_UNCHANGED "
                f"crop={crop} "
                f"market={market}"

            )

            continue

        old_modal = row[
            "Modal_Price"
        ]

        # ----------------------------------------------------------
        # Update live market fields
        # ----------------------------------------------------------

        df.at[
            index,
            "Min_Price"
        ] = best["min_price"]

        df.at[
            index,
            "Max_Price"
        ] = best["max_price"]

        df.at[
            index,
            "Modal_Price"
        ] = best["modal_price"]

        # Update trend only when source provides evidence.
        if best["trend"] != "unknown":

            df.at[
                index,
                "Trend"
            ] = best["trend"]

        df.at[
            index,
            "Last_Updated"
        ] = today

        updated_count += 1

        # ----------------------------------------------------------
        # Display
        # ----------------------------------------------------------

        print(
            f"Previous modal : {old_modal}"
        )

        print(
            f"Min price      : "
            f"Rs.{best['min_price']:,.2f}/quintal"
        )

        print(
            f"Max price      : "
            f"Rs.{best['max_price']:,.2f}/quintal"
        )

        print(
            f"Modal price    : "
            f"Rs.{best['modal_price']:,.2f}/quintal"
        )

        print(
            f"Trend          : "
            f"{best['trend']}"
        )

        print(
            f"Source         : "
            f"{best['source']}"
        )

        print(
            f"Evidence       : "
            f"{best['evidence'][:250]}"
        )

        write_log(

            f"ROW_UPDATED "
            f"crop={crop} "
            f"market={market} "
            f"min={best['min_price']} "
            f"max={best['max_price']} "
            f"modal={best['modal_price']} "
            f"trend={best['trend']}"

        )

    # --------------------------------------------------------------
    # Save (to the SEPARATE output file -- see module docstring)
    # --------------------------------------------------------------

    df.to_csv(

        OUTPUT_FILE,

        index=False

    )

    # --------------------------------------------------------------
    # Success
    # --------------------------------------------------------------

    write_last_success()

    write_log(

        f"UPDATE_COMPLETED "
        f"rows_updated={updated_count} "
        f"rows_unchanged={unchanged_count}"

    )

    print()

    print("=" * 70)

    print(
        "WEB MARKET PRICE UPDATE COMPLETED"
    )

    print("=" * 70)

    print(
        f"Total rows     : {len(df)}"
    )

    print(
        f"Rows updated   : {updated_count}"
    )

    print(
        f"Rows unchanged : {unchanged_count}"
    )

    print(
        f"Output         : {OUTPUT_FILE}"
    )

    print(
        f"Backup         : {BACKUP_FILE}"
    )

    print(
        f"Log            : {LOG_FILE}"
    )

    print(
        "NOTE: data/market_prices.csv was NOT modified. Review "
        f"{OUTPUT_FILE} and copy it over the live dataset yourself "
        "if you trust the results."
    )

    print("=" * 70)


# ======================================================================
# DAILY UPDATE GUARD
# ======================================================================

def update_market_prices():

    print()

    print("=" * 70)

    print(
        "AGRIMIND DAILY WEB MARKET UPDATE CHECK"
    )

    print("=" * 70)

    if not should_run_update():

        write_log(
            "UPDATE_SKIPPED_REASON=LESS_THAN_24_HOURS"
        )

        return

    write_log(
        "UPDATE_STARTED=true"
    )

    try:

        perform_update()

    except Exception as error:

        # Do not write LAST_SUCCESS after a failed update.

        write_log(
            f"UPDATE_FAILED={error}"
        )

        print()

        print(
            f"Market updater failed: {error}"
        )

        raise


# ======================================================================
# MAIN
# ======================================================================

if __name__ == "__main__":
    update_market_prices()
