import json
import logging
import time
from pathlib import Path
from typing import Dict, Generator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from .config import get_config
from .gecko_client import SpaClient
from .logging_setup import setup_json_logger
from . import __version__

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

app = FastAPI(title="Spa Engine", version=__version__)

config = get_config()

events_logger = setup_json_logger("events", config["log_dir"], "events.log")

spa_client = SpaClient(config)
app_start = time.time()

def _enable_geckolib_debug() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s> %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("geckolib").setLevel(logging.DEBUG)


@app.on_event("startup")
async def startup() -> None:
    _enable_geckolib_debug()
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
def spa_command(payload: Dict[str, object]) -> Dict[str, object]:
    if not spa_client.is_connected():
        return {"ok": False, "error": "Spa is not connected"}

    events_logger.info("command_received")
    return {"ok": False, "error": "Commands not implemented yet"}


@app.get("/events")
def events() -> StreamingResponse:
    def event_stream() -> Generator[str, None, None]:
        while True:
            data = {"type": "state_update", "payload": spa_client.get_state()}
            yield f"data: {json.dumps(data, ensure_ascii=True)}\n\n"
            time.sleep(2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
