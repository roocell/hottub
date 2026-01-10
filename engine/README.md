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
