import logging
import json
from datetime import datetime, timezone
from config.settings import settings


def _json_formatter(record: logging.LogRecord) -> str:
    return json.dumps({
        "time": datetime.now(timezone.utc).isoformat(),
        "level": record.levelname,
        "module": record.module,
        "message": record.getMessage(),
        **({"task_id": record.task_id} if hasattr(record, "task_id") else {}),
    })


class JsonHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord):
        self.stream.write(_json_formatter(record) + "\n")
        self.flush()


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = JsonHandler()
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    return logger
