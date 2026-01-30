#!/usr/bin/env python3
"""
Enterprise SAP Generation System - Logging Configuration
=========================================================
Centralized structured logging for production-grade error tracking.
"""

import logging
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from functools import wraps
import traceback


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter for production environments."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info) if record.exc_info[0] else None
            }

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data

        return json.dumps(log_data)


class HumanReadableFormatter(logging.Formatter):
    """Human-readable formatter for development/console output."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m"
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        reset = self.COLORS["RESET"]

        # Format: [LEVEL] module.function:line - message
        base_msg = f"{color}[{record.levelname}]{reset} {record.module}.{record.funcName}:{record.lineno} - {record.getMessage()}"

        # Add exception info if present
        if record.exc_info:
            base_msg += f"\n{color}Exception: {record.exc_info[0].__name__}: {record.exc_info[1]}{reset}"

        return base_msg


class SAPLogger:
    """
    Production-grade logger with structured output and context tracking.

    Usage:
        from core.logging_config import get_logger
        logger = get_logger(__name__)

        logger.info("Processing protocol", nct_id="NCT12345678", phase="Phase 3")
        logger.error("Extraction failed", exc_info=True)
    """

    _loggers: Dict[str, logging.Logger] = {}
    _initialized: bool = False
    _log_level: str = "INFO"
    _json_output: bool = False
    _log_file: Optional[Path] = None

    @classmethod
    def initialize(
        cls,
        level: str = "INFO",
        json_output: bool = False,
        log_file: Optional[str] = None
    ) -> None:
        """
        Initialize the logging system.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            json_output: Use JSON format for production
            log_file: Optional file path for log output
        """
        if cls._initialized:
            return

        cls._log_level = level.upper()
        cls._json_output = json_output
        cls._log_file = Path(log_file) if log_file else None

        # Configure root logger
        root_logger = logging.getLogger("sap_generator")
        root_logger.setLevel(getattr(logging, cls._log_level))

        # Remove existing handlers
        root_logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, cls._log_level))

        if json_output:
            console_handler.setFormatter(StructuredFormatter())
        else:
            console_handler.setFormatter(HumanReadableFormatter())

        root_logger.addHandler(console_handler)

        # File handler (always JSON for parsing)
        if cls._log_file:
            cls._log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(cls._log_file)
            file_handler.setLevel(logging.DEBUG)  # Capture everything in file
            file_handler.setFormatter(StructuredFormatter())
            root_logger.addHandler(file_handler)

        cls._initialized = True

    @classmethod
    def get_logger(cls, name: str) -> "SAPLoggerAdapter":
        """Get or create a logger for the given module name."""
        if not cls._initialized:
            cls.initialize()

        if name not in cls._loggers:
            logger = logging.getLogger(f"sap_generator.{name}")
            cls._loggers[name] = logger

        return SAPLoggerAdapter(cls._loggers[name])


class SAPLoggerAdapter:
    """
    Logger adapter that supports structured extra data.

    Allows: logger.info("message", key1=value1, key2=value2)
    """

    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self._context: Dict[str, Any] = {}

    def with_context(self, **kwargs) -> "SAPLoggerAdapter":
        """Create a new adapter with additional context."""
        new_adapter = SAPLoggerAdapter(self._logger)
        new_adapter._context = {**self._context, **kwargs}
        return new_adapter

    def _log(self, level: int, msg: str, exc_info: bool = False, **kwargs):
        """Internal log method with extra data support."""
        extra_data = {**self._context, **kwargs}

        # Create log record with extra data
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "",  # filename (set by handler)
            0,   # lineno (set by handler)
            msg,
            (),
            exc_info if exc_info else None
        )

        if extra_data:
            record.extra_data = extra_data

        self._logger.handle(record)

    def debug(self, msg: str, **kwargs):
        """Log debug message."""
        if self._logger.isEnabledFor(logging.DEBUG):
            self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs):
        """Log info message."""
        if self._logger.isEnabledFor(logging.INFO):
            self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        """Log warning message."""
        if self._logger.isEnabledFor(logging.WARNING):
            self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, exc_info: bool = False, **kwargs):
        """Log error message, optionally with exception info."""
        if self._logger.isEnabledFor(logging.ERROR):
            self._log(logging.ERROR, msg, exc_info=exc_info, **kwargs)

    def critical(self, msg: str, exc_info: bool = False, **kwargs):
        """Log critical message, optionally with exception info."""
        if self._logger.isEnabledFor(logging.CRITICAL):
            self._log(logging.CRITICAL, msg, exc_info=exc_info, **kwargs)

    def exception(self, msg: str, **kwargs):
        """Log error with exception traceback."""
        self.error(msg, exc_info=True, **kwargs)


def get_logger(name: str) -> SAPLoggerAdapter:
    """
    Get a logger for the given module.

    Usage:
        from core.logging_config import get_logger
        logger = get_logger(__name__)

        logger.info("Processing started", nct_id="NCT12345678")

        try:
            risky_operation()
        except Exception:
            logger.exception("Operation failed")
    """
    return SAPLogger.get_logger(name)


def log_function_call(logger: Optional[SAPLoggerAdapter] = None):
    """
    Decorator to log function entry/exit with timing.

    Usage:
        @log_function_call()
        def my_function(arg1, arg2):
            ...
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)

        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            logger.debug(f"Entering {func_name}", args_count=len(args), kwargs_keys=list(kwargs.keys()))

            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.debug(f"Exiting {func_name}", elapsed_seconds=elapsed, success=True)
                return result
            except Exception as e:
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.error(
                    f"Exception in {func_name}: {type(e).__name__}: {str(e)[:200]}",
                    elapsed_seconds=elapsed,
                    exception_type=type(e).__name__
                )
                raise

        return wrapper
    return decorator


# Exception classes for better error categorization
class SAPGeneratorError(Exception):
    """Base exception for SAP generator errors."""
    pass


class ExtractionError(SAPGeneratorError):
    """Error during protocol extraction."""
    def __init__(self, message: str, field: Optional[str] = None, source: Optional[str] = None):
        self.field = field
        self.source = source
        super().__init__(message)


class ValidationError(SAPGeneratorError):
    """Error during validation."""
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        self.field = field
        self.value = value
        super().__init__(message)


class APIError(SAPGeneratorError):
    """Error from external API calls."""
    def __init__(self, message: str, api: str, status_code: Optional[int] = None):
        self.api = api
        self.status_code = status_code
        super().__init__(message)


class LLMError(SAPGeneratorError):
    """Error from LLM calls."""
    def __init__(self, message: str, provider: str, model: Optional[str] = None):
        self.provider = provider
        self.model = model
        super().__init__(message)


class ConfigurationError(SAPGeneratorError):
    """Error in system configuration."""
    def __init__(self, message: str, config_key: Optional[str] = None):
        self.config_key = config_key
        super().__init__(message)


# Initialize with defaults on import
SAPLogger.initialize()
