import json
import logging
from logging import FileHandler, LogRecord
from pathlib import Path
from typing import Callable
LOG_MAX_BYTES = 100 * 1024


class BoundedFileHandler(FileHandler):
    def __init__(self, filename: str | Path, max_bytes: int) -> None:
        super().__init__(filename, encoding="utf-8")
        self._max_bytes = max_bytes
        self._path = Path(filename)

    def emit(self, record: LogRecord) -> None:
        super().emit(record)
        self._truncate_if_needed()

    def _truncate_if_needed(self) -> None:
        try:
            size = self._path.stat().st_size
        except FileNotFoundError:
            return
        if size <= self._max_bytes:
            return
        with self._path.open("rb") as source:
            source.seek(-self._max_bytes, 2)
            data = source.read(self._max_bytes)
        with self._path.open("wb") as target:
            target.write(data)


def setup_json_logger(name: str, log_dir: str, filename: str) -> logging.Logger:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    handler = BoundedFileHandler(Path(log_dir) / filename, LOG_MAX_BYTES)

    def format_record(record: LogRecord) -> str:
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
