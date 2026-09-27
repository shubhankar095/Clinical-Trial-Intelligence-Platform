import json
import logging
import os

from datetime import (
    datetime,
    timezone,
)

from rich.logging import RichHandler


DEFAULT_LOG_LEVEL = "info"
DEFAULT_LOG_FORMAT = "console"


class JsonFormatter(
    logging.Formatter
):
    """
    Format log records as JSON for
    CloudWatch Logs.
    """

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:

        payload = {
            "timestamp": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": (
                record.getMessage()
            ),
        }

        if record.exc_info:
            payload["exception"] = (
                self.formatException(
                    record.exc_info
                )
            )

        reserved_fields = {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
        }

        for key, value in (
            record.__dict__.items()
        ):
            if key in reserved_fields:
                continue

            payload[key] = value

        return json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )


def get_logger(
    name: str,
) -> logging.Logger:
    """
    Return a configured logger.

    LOG_FORMAT=json enables structured
    JSON logging.

    LOG_FORMAT=console enables readable
    Rich console logging.
    """

    logger = logging.getLogger(
        name
    )

    logger.handlers.clear()
    logger.propagate = False

    log_level = os.getenv(
        "LOG_LEVEL",
        DEFAULT_LOG_LEVEL,
    ).lower()

    set_log_level(
        logger,
        log_level,
    )

    log_format = os.getenv(
        "LOG_FORMAT",
        DEFAULT_LOG_FORMAT,
    ).lower()

    if log_format == "json":
        handler = (
            logging.StreamHandler()
        )

        handler.setFormatter(
            JsonFormatter()
        )

    else:
        handler = RichHandler(
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
        )

        handler.setFormatter(
            logging.Formatter(
                "%(message)s"
            )
        )

    logger.addHandler(
        handler
    )

    return logger


def set_log_level(
    logger: logging.Logger,
    level: str,
) -> None:
    """
    Set a logger's severity level.
    """

    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    logger.setLevel(
        level_map.get(
            level.lower(),
            logging.INFO,
        )
    )


if __name__ == "__main__":
    logger = get_logger(
        "UTILS"
    )

    logger.debug(
        "Debug log"
    )

    logger.info(
        "Information log",
        extra={
            "event": "logger_test",
            "status": "SUCCESS",
        },
    )

    logger.warning(
        "Warning log"
    )

    logger.error(
        "Error log"
    )

    logger.critical(
        "Critical log"
    )