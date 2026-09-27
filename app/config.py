import os
from typing import List

from dotenv import load_dotenv


load_dotenv()


def _get_int(
    name: str,
    default: int,
) -> int:
    value = os.getenv(
        name,
        str(default),
    )

    try:
        return int(value)

    except ValueError:
        return default


def _get_bool(
    name: str,
    default: bool = False,
) -> bool:
    value = os.getenv(
        name,
        str(default),
    )

    return (
        value.strip().lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )


def _get_list(
    name: str,
    default: str,
) -> List[str]:
    value = os.getenv(
        name,
        default,
    )

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


class Settings:
    APP_NAME: str = (
        "AI Resume Job Matcher"
    )

    APP_VERSION: str = "1.0.0"

    ENVIRONMENT: str = os.getenv(
        "ENVIRONMENT",
        "development",
    )

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "",
    )

    GEMINI_API_KEY: str = os.getenv(
        "GEMINI_API_KEY",
        "",
    )

    GEMINI_PRIMARY_MODEL: str = os.getenv(
        "GEMINI_PRIMARY_MODEL",
        "gemini-3.5-flash",
    )

    GEMINI_FALLBACK_MODEL: str = os.getenv(
        "GEMINI_FALLBACK_MODEL",
        "gemini-3.1-flash-lite",
    )

    FORCE_PRIMARY_FAILURE: bool = (
        _get_bool(
            "FORCE_PRIMARY_FAILURE",
            False,
        )
    )

    CORS_ORIGINS: List[str] = (
        _get_list(
            "CORS_ORIGINS",
            (
                "http://localhost:5173,"
                "http://127.0.0.1:5173"
            ),
        )
    )

    MAX_UPLOAD_SIZE_MB: int = (
        _get_int(
            "MAX_UPLOAD_SIZE_MB",
            5,
        )
    )

    @property
    def MAX_UPLOAD_SIZE_BYTES(
        self,
    ) -> int:
        return (
            self.MAX_UPLOAD_SIZE_MB
            * 1024
            * 1024
        )


settings = Settings()