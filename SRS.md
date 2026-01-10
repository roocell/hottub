# Software Requirements Specification (SRS)
Project: LAN Hot Tub Controller (in.touch2 via geckolib)

## 1. Purpose
Build a self-hosted, LAN-only web application that monitors and controls your hot tub (Gecko in.touch2) using geckolib as the protocol interface, with:

- Frontend: Next.js + Tailwind + shadcn/ui + TypeScript
- Backend engine: Python service using geckolib
- Automation/scheduling: built in
- History: lightweight log files (no database)

## 2. Scope
### In scope (v1)
- Live spa dashboard (temps, heater status, pumps, lights, etc., based on what geckolib exposes)
- Control actions (set temperature, toggle pumps/lights, etc.)
- Automation/scheduling (time-based rules)
- Operational logs + state history to local file(s)
- LAN-only deployment to your Coolify instance

### Out of scope (v1)
- Cloud access / public internet exposure
- User accounts/auth (explicitly deferred)
- Database-backed analytics (explicitly avoided)

## 3. Target environment & constraints
### 3.1 Network
- Access only from devices on your LAN
- in.touch2 home transmitter uses DHCP; current IP: 192.168.50.167
- Transmitter MAC: 68:27:19:be:a7:a2
- Network resilience acceptable (disconnect/reconnect OK)

### 3.2 Hosting
- Runs on a Linux server within your home network
- Deploy using Coolify; backend should deploy automatically alongside frontend
- Prefer Python backend in a venv for local testing only; in deployment, run inside Docker (no venv required)

### 3.3 Safety constraints
- Hard max setpoint: 104F
- More safety rules can be added later

## 4. High-level architecture
### 4.1 Components
**Spa Engine (Python)**
- Own service (internal-only) that:
  - Connects to in.touch2 transmitter using geckolib
  - Maintains current state snapshot in memory
  - Executes control commands with validation + rate limits
  - Runs scheduler + automation rules
  - Writes event/state history to log files
  - Streams updates to clients (SSE or WebSocket)

**Web UI (Next.js)**
- Mobile-first UI for:
  - Status dashboard
  - Controls
  - Automation rules editor
  - Logs viewer (basic)
  - Settings page (engine config status, connection health)

**(Optional) Reverse proxy**
- Not required if LAN-only and you are fine with http://... inside LAN
- If you later want HTTPS inside LAN, can be added (Caddy/Traefik)

### 4.2 Communication pattern
Next.js calls the Python engine via a private LAN URL (Coolify internal network)

Two channels:
- REST for commands, config, automation CRUD
- SSE (preferred) or WebSocket for real-time state/events

Rationale: SSE is simpler for server pushes and plays well with proxies.

## 5. Functional requirements
### 5.1 Device discovery & connection
- FR-1 Engine must connect to the in.touch2 transmitter using an address configured via environment variables (see Section 8).
- FR-2 Engine must expose connection state: DISCONNECTED, CONNECTING, CONNECTED, ERROR, plus last error message + timestamp.
- FR-3 Engine must attempt automatic reconnect with backoff.
- FR-4 IP address configuration:
  - Primary: INTOUCH2_HOST via .env
  - Secondary/optional: If host not reachable, attempt to locate by MAC address (INTOUCH2_MAC) using LAN ARP table lookup.
  - If MAC discovery is not feasible in the container/runtime, display actionable message: ?Reserve DHCP lease? / ?Update INTOUCH2_HOST?.
  - Recommendation: add a router DHCP reservation for stability.

### 5.2 State monitoring
- FR-5 UI must show live:
  - Current water temperature
  - Target setpoint temperature
  - Heater status (if available)
  - Pump states (per pump available)
  - Light state/mode (if available)
  - Error codes/fault status (if available)
- FR-6 Update frequency:
  - Engine refresh loop target: every 1?2 seconds
  - UI receives updates within ~2 seconds of change (LAN)

### 5.3 Controls
- FR-7 User can set temperature setpoint (clamped to device min/max and max 104F).
- FR-8 User can toggle pumps/lights and other actuators exposed by geckolib (capability-driven UI).
- FR-9 Command execution must be serialized (one command at a time).
- FR-10 Rate limiting: minimum interval between commands (default 1 second); UI should debounce rapid changes.
- FR-11 Command result feedback: UI shows success/failure toast with reason.

### 5.4 Automation & scheduling
- FR-12 User can create automation rules that trigger actions on a schedule (time-of-day, day-of-week, one-shot, enable/disable).
- FR-13 Actions supported: set temperature, toggle pumps/lights (future scenes later).
- FR-14 Persistence: store automation rules in a local file (e.g., automations.json) on a persistent volume.
- FR-15 Scheduler reliability: reload on restart; missed triggers not replayed by default.

### 5.5 History & logs
- FR-16 Engine writes append-only logs to disk:
  - events.log (commands, connection changes, automation runs)
  - state.log (optional periodic sampling)
- FR-17 Log rotation: daily or size-based; keep last N days (default: 14)
- FR-18 UI log viewer: tail last 500 lines, filter by type, download logs

### 5.6 Settings and status UI
- FR-19 UI System page shows engine version, uptime, configured transmitter IP, last contact time, connection status + last error, and capabilities.

## 6. Non-functional requirements
### 6.1 Performance
- UI initial load < 2 seconds on LAN
- Smooth updates on mobile

### 6.2 Reliability
- Engine recovers from transmitter IP changes (DHCP reservation recommended or MAC lookup fallback)
- Engine does not crash on malformed responses; log and retry

### 6.3 Security (LAN-only posture)
- No user auth
- Only bind engine to internal interface (not public)
- Restrict CORS to web app origin
- Optional shared secret header later

### 6.4 Maintainability
- Monorepo:
  - /web (Next.js)
  - /engine (Python)
- Documented API contracts; optional TS type generation later
- Structured logs (JSON lines preferred)

## 7. API specification (proposed)
### 7.1 REST
**Health**
- GET /health -> engine status, version, uptime, connection state

**State**
- GET /spa/state -> normalized state JSON

**Commands**
- POST /spa/command { type, payload } -> { ok, error? }

**Automations**
- GET /automations
- POST /automations
- PUT /automations/:id
- DELETE /automations/:id
- POST /automations/:id/run

**Logs**
- GET /logs?type=events|state&tail=500
- GET /logs/download?type=events|state&date=YYYY-MM-DD (optional)

### 7.2 Real-time updates
- GET /events (SSE)
- emits: state_update, connection_update, event_log

## 8. Configuration (environment variables)
### Engine (.env)
- INTOUCH2_HOST=192.168.50.167
- INTOUCH2_PORT=... (only if needed by geckolib)
- INTOUCH2_MAC=68:27:19:be:a7:a2
- MAX_SETPOINT_F=104
- COMMAND_RATE_LIMIT_MS=1000
- STATE_POLL_INTERVAL_MS=1500
- STATE_LOG_INTERVAL_S=60
- LOG_DIR=/data/logs
- AUTOMATIONS_FILE=/data/automations.json

### Web app (.env)
- NEXT_PUBLIC_ENGINE_BASE_URL=http://engine:8000

## 9. Deployment on Coolify
- Single compose app (monorepo)
- Two services (web + engine) with shared internal network + volume
- Single git push triggers redeploy of both services

## 10. UI requirements (Next.js + Tailwind + shadcn)
### 10.1 Pages
- Dashboard: temp, setpoint, heater, toggles, status banner
- Controls: pumps, lighting, advanced settings
- Automations: list, create/edit modal, enable/disable, run now
- Logs: tabs for events/state, tail view, filter
- System: engine health, capabilities, transmitter info

### 10.2 UX behavior
- Optimistic UI where safe (pending state)
- Toasts for results
- Disable controls when engine disconnected (except refresh)

## 11. Data model
### 11.1 Normalized state schema (engine-owned)
- temps: { current_f, setpoint_f }
- heater: { on, mode? }
- pumps: [{ id, label, state, speed? }]
- lights: { on, mode? }
- errors: [{ code, message, severity }]
- capabilities: { canSetTemp, pumpsCount, hasLights, ... }
- meta: { lastUpdated, connectionState }

## 12. Acceptance criteria
- AC-1 Phone on LAN shows current temp/setpoint reliably.
- AC-2 Set temp clamps at 104F and reflects change within 5s.
- AC-3 At least one actuator toggles successfully with UI confirmation.
- AC-4 Engine reconnects after transmitter reboot/IP change or alerts if not.
- AC-5 Automations execute and write to events.log.
- AC-6 Logs persist across redeploys (volume-backed).

## 13. Risks & mitigations
- DHCP IP changes break connectivity -> DHCP reservation or MAC lookup fallback.
- Capability variance by spa model -> capability-driven UI.
- Scheduling edge cases -> single timezone setting.

## 14. Milestones
- M1: Connectivity + live dashboard
- M2: Controls
- M3: Automations
- M4: Logs + system page
