# LAN Hot Tub Controller

Monorepo scaffold for the LAN-only hot tub controller.

## Structure
- web/: Next.js frontend
- engine/: Python spa engine
- docker-compose.yml: local/coolify compose app scaffold
- scripts/: local dev setup helpers

## Local dev (engine)
Use a venv for local testing. Docker is for deployment only.

PowerShell:
  scripts\setup-venv.ps1

bash:
  scripts/setup-venv.sh
