# Engine (Python)

Scaffold placeholder for the spa engine (geckolib integration).

## Local venv
Run the setup script from repo root.

## Run locally
From repo root:

  scripts\\setup-venv.ps1
  scripts\\run-engine.ps1

# Run locally with debug
.\engine\.venv\Scripts\python.exe -m uvicorn spa_engine.api:app --app-dir engine --host 0.0.0.0 --port 8000 --reload

## Test with curl
From another terminal:

  curl http://localhost:8000/health
  curl http://localhost:8000/spa/state
  curl http://localhost:8000/events

## Idle mode
The engine starts idle and only connects to the spa after a `/spa/state` request.
If no `/spa/state` request is seen for `UI_IDLE_TIMEOUT_S` seconds (default 10),
it disconnects and returns to idle.
