from dotenv import load_dotenv
import os


load_dotenv()


class Settings:

    """
    Application Configuration
    """

    ####################################################################
    # SQLite
    ####################################################################

    SQLITE_DB_PATH = os.getenv(

        "SQLITE_DB_PATH",

        "app/database/agrimind.db"

    )

    ####################################################################
    # PostgreSQL
    ####################################################################

    POSTGRES_HOST = os.getenv(

        "POSTGRES_HOST"

    )

    POSTGRES_PORT = int(

        os.getenv(

            "POSTGRES_PORT",

            5432

        )

    )

    POSTGRES_DB = os.getenv(

        "POSTGRES_DB"

    )

    POSTGRES_USER = os.getenv(

        "POSTGRES_USER"

    )

    POSTGRES_PASSWORD = os.getenv(

        "POSTGRES_PASSWORD"

    )

    ####################################################################
    # External APIs
    ####################################################################

    # Weather
    OPEN_METEO_URL = os.getenv(

        "OPEN_METEO_URL"

    )

    ####################################################################
    # Default Location
    ####################################################################

    DEFAULT_LATITUDE = float(

        os.getenv(

            "DEFAULT_LATITUDE",

            "11.0168"

        )

    )

    DEFAULT_LONGITUDE = float(

        os.getenv(

            "DEFAULT_LONGITUDE",

            "76.9558"

        )

    )

    ####################################################################
    # Application
    ####################################################################

    LOG_LEVEL = os.getenv(

        "LOG_LEVEL",

        "INFO"

    )

    PROJECT_NAME = os.getenv(

        "PROJECT_NAME",

        "AgriMind"

    )

    VERSION = os.getenv(

        "VERSION",

        "1.0.0"

    )


##########################################################################
# Singleton
##########################################################################

settings = Settings()