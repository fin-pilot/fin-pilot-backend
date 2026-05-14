from logging.config import dictConfig

from uvicorn.logging import DefaultFormatter

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": DefaultFormatter,
            "fmt": (
                "%(levelprefix)s " "%(asctime)s | " "%(name)s | " "%(message)s"
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["default"],
        "level": "INFO",
    },
}


def setup_logging() -> None:
    dictConfig(LOGGING_CONFIG)
