"""
Logging configuration for the application.
"""
import logging
import logging.config
import sys
from typing import Optional


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> None:
    """
    Setup logging configuration for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for logging output
        format_string: Optional custom format string
    """
    if format_string is None:
        format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(filename)s:%(lineno)d - %(message)s"
        )
    
    handlers = ["console"]
    handler_config = {
        "console": {
            "class": "logging.StreamHandler",
            "level": log_level,
            "formatter": "standard",
            "stream": sys.stdout,
        }
    }
    
    if log_file:
        handlers.append("file")
        handler_config["file"] = {
            "class": "logging.FileHandler",
            "level": log_level,
            "formatter": "standard",
            "filename": log_file,
            "mode": "a",
        }
    
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": format_string,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": handler_config,
        "loggers": {
            "": {  # root logger
                "handlers": handlers,
                "level": log_level,
                "propagate": False,
            },
            "uvicorn": {
                "handlers": handlers,
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": handlers,
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": handlers,
                "level": "INFO",
                "propagate": False,
            },
        },
    }
    
    logging.config.dictConfig(logging_config)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)
