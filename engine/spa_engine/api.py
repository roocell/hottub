import json
import logging
import time
from pathlib import Path
from typing import Dict, Generator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from dotenv import load_dotenv

from .config import get_config
from .gecko_client import SpaClient
from .logging_setup import setup_json_logger
from . import __version__

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

app = FastAPI(title="Spa Engine", version=__version__)

config = get_config()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.50.33:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

events_logger = setup_json_logger("events", config["log_dir"], "events.log")

spa_client = SpaClient(config)
app_start = time.time()
LOG_TAIL_BYTES = 1024

def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s> %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("geckolib").setLevel(logging.WARNING)


def _read_tail_bytes(path: Path, size: int) -> bytes:
    with path.open("rb") as handle:
        handle.seek(0, 2)
        end = handle.tell()
        if end > size:
            handle.seek(end - size)
        else:
            handle.seek(0)
        return handle.read()


@app.on_event("startup")
async def startup() -> None:
    _configure_logging()
    await spa_client.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await spa_client.stop()


@app.get("/health")
def health() -> Dict[str, object]:
    state_snapshot = spa_client.get_state()
    return {
        "status": "ok",
        "version": __version__,
        "uptime_s": int(time.time() - app_start),
        "connection": state_snapshot.get("meta", {})
    }


@app.get("/spa/state")
def spa_state() -> Dict[str, object]:
    return spa_client.get_state()


@app.post("/spa/command")
async def spa_command(payload: Dict[str, object]) -> Dict[str, object]:
    events_logger.info("command_received")
    return await spa_client.command(payload)


@app.get("/events")
def events() -> StreamingResponse:
    def event_stream() -> Generator[str, None, None]:
        while True:
            data = {"type": "state_update", "payload": spa_client.get_state()}
            yield f"data: {json.dumps(data, ensure_ascii=True)}\n\n"
            time.sleep(2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/logs")
def logs(log_type: str = "events") -> PlainTextResponse:
    filenames = {
        "events": "events.log",
        "state": "state.log",
    }
    if log_type not in filenames:
        raise HTTPException(status_code=400, detail="Unknown log type")

    log_path = Path(config["log_dir"]) / filenames[log_type]
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    data = _read_tail_bytes(log_path, LOG_TAIL_BYTES)
    return PlainTextResponse(content=data, media_type="text/plain; charset=utf-8")
