import json
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_json_logger(name: str, log_dir: str, filename: str) -> logging.Logger:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    handler = TimedRotatingFileHandler(
        Path(log_dir) / filename, when="D", interval=1, backupCount=14, encoding="utf-8"
    )

    def format_record(record: logging.LogRecord) -> str:
        payload = {
            "ts": record.created,
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name
        }
        return json.dumps(payload, ensure_ascii=True)

    handler.setFormatter(logging.Formatter(fmt="%(message)s"))

    class JsonAdapter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            record.msg = format_record(record)
            record.args = ()
            return True

    handler.addFilter(JsonAdapter())
    logger.addHandler(handler)
    return logger
