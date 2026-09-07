"""
==========================================================================
AgriMind

Historical Collector

Retrieves historical farm records and prepares context for the
Historical Agent.

Author : AgriMind Team
==========================================================================
"""

import logging
import sqlite3

from app.config.settings import settings

logger = logging.getLogger(__name__)


class HistoricalCollector:

    """
    Historical Collector

    Responsibilities
    ----------------
    1. Retrieve recent farm records for the crop.
    2. Return standardized historical data.
    3. Preserve current context for future similarity search.
    """

    ####################################################################
    # Collect Historical Records
    ####################################################################

    def collect(

        self,

        crop_profile,

        weather=None,

        soil=None,

        satellite=None,

        market=None

    ):

        ############################################################
        # Crop Name
        ############################################################

        crop = crop_profile["crop"]

        ############################################################
        # Database
        #
        # A locked file, a missing database, or a missing table must
        # degrade historical evidence to "no records" rather than
        # crash the whole pipeline. Zero records is itself meaningful
        # input (HistoricalAgent can say "no prior seasons on file"),
        # so this returns status="success" with an empty record set
        # rather than status="failed".
        ############################################################

        try:

            conn = sqlite3.connect(

                settings.SQLITE_DB_PATH

            )

            conn.row_factory = sqlite3.Row

            cursor = conn.cursor()

            cursor.execute(

                """

                SELECT *

                FROM farm_history

                WHERE LOWER(crop)=LOWER(?)

                ORDER BY id DESC

                LIMIT 5

                """,

                (crop,)

            )

            rows = cursor.fetchall()

            conn.close()

            records = [
                dict(row)
                for row in rows
            ]

        except Exception as e:

            logger.warning(

                "Historical collection failed: %s",
                e

            )

            records = []

        ############################################################

        return {

            "source": "historical",

            "status": "success",

            "crop": crop,

            "record_count": len(records),

            "current_context": {

                "weather": weather,

                "soil": soil,

                "satellite": satellite,

                "market": market

            },

            "records": records

        }


##########################################################################

historical_collector = HistoricalCollector()