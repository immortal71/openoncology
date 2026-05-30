"""
Structured JSON logging configuration using structlog.

Replaces the default Python text logging with JSON output suitable for
log aggregation (Loki, CloudWatch, Datadog, Elastic).

Every log line automatically includes:
  - timestamp (ISO-8601 UTC)
  - level
  - logger
  - event (the message)
  - Any keyword arguments passed to the logger become searchable JSON fields.

Usage:
    from middleware.logging_config import configure_logging
    configure_logging()   # call once at startup in main.py

    import structlog
    logger = structlog.get_logger("openoncology.api")
    logger.info("request.completed", method="GET", path="/api/results/123", duration_ms=45.2)
"""
import logging
import logging.config
import sys

try:
    import structlog

    def configure_logging(log_level: str = "INFO", json_logs: bool = True) -> None:
        """Configure structlog with JSON output for production or pretty output for dev."""
        shared_processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
        ]

        if json_logs:
            renderer = structlog.processors.JSONRenderer()
        else:
            renderer = structlog.dev.ConsoleRenderer(colors=True)

        structlog.configure(
            processors=shared_processors + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        formatter = structlog.stdlib.ProcessorFormatter(
            processor=renderer,
            foreign_pre_chain=shared_processors,
        )

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)

        root_logger = logging.getLogger()
        root_logger.handlers = [handler]
        root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        # Silence noisy third-party loggers in production
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(
            logging.INFO if log_level == "DEBUG" else logging.WARNING
        )

except ImportError:
    # structlog not installed — fall back to stdlib JSON-ish format
    def configure_logging(log_level: str = "INFO", json_logs: bool = True) -> None:  # type: ignore[misc]
        logging.basicConfig(
            stream=sys.stdout,
            level=getattr(logging, log_level.upper(), logging.INFO),
            format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","event":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
