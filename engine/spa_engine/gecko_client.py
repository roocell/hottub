import asyncio
import copy
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv
from geckolib.async_spa_manager import GeckoAsyncSpaMan
from geckolib.automation.async_facade import GeckoAsyncFacade
from geckolib.const import GeckoConstants
from geckolib.spa_events import GeckoSpaEvent
from geckolib.spa_state import GeckoSpaState

from .config import get_config

def _map_connection_state(spa_state: GeckoSpaState) -> str:
    if spa_state == GeckoSpaState.CONNECTED:
        return "CONNECTED"
    if spa_state in (
        GeckoSpaState.CONNECTING,
        GeckoSpaState.LOCATING_SPAS,
        GeckoSpaState.LOCATED_SPAS,
        GeckoSpaState.SPA_READY,
    ):
        return "CONNECTING"
    if spa_state in (
        GeckoSpaState.ERROR_SPA_NOT_FOUND,
        GeckoSpaState.ERROR_NEEDS_ATTENTION,
        GeckoSpaState.ERROR_PING_MISSED,
        GeckoSpaState.ERROR_RF_FAULT,
    ):
        return "ERROR"
    return "DISCONNECTED"


def _to_fahrenheit(value: Optional[float], temp_units: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    if temp_units is None:
        return float(value)
    if str(temp_units).upper().startswith("C"):
        return float(value) * 9.0 / 5.0 + 32.0
    return float(value)


def _to_native_temp(value_f: float, temp_units: Optional[str]) -> float:
    if temp_units is None:
        return float(value_f)
    if str(temp_units).upper().startswith("C"):
        return (float(value_f) - 32.0) * 5.0 / 9.0
    return float(value_f)


def _accessor_value(accessors: dict, keys: list[str]) -> Optional[float]:
    for key in keys:
        accessor = accessors.get(key)
        if accessor is not None:
            return accessor.value
    return None


class EngineSpaManager(GeckoAsyncSpaMan):
    def __init__(self, client_uuid: str, spa_address: str) -> None:
        super().__init__(client_uuid, spa_address=spa_address)
        self.last_error: Optional[str] = None
        self.last_error_at: Optional[float] = None

    async def handle_event(self, event: GeckoSpaEvent, **_kwargs) -> None:
        details = ""
        if _kwargs:
            parts = []
            for key in sorted(_kwargs.keys()):
                value = _kwargs[key]
                parts.append(f"{key}={value}")
            details = " " + " ".join(parts)
        print(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [spa] event={event.name}{details}"
        )
        if event in (
            GeckoSpaEvent.SPA_NOT_FOUND,
            GeckoSpaEvent.CONNECTION_CANNOT_FIND_CONFIG_VERSION,
            GeckoSpaEvent.CONNECTION_CANNOT_FIND_LOG_VERSION,
            GeckoSpaEvent.CONNECTION_CANNOT_FIND_SPA_PACK,
            GeckoSpaEvent.CONNECTION_PROTOCOL_RETRY_TIME_EXCEEDED,
            GeckoSpaEvent.ERROR_PROTOCOL_RETRY_TIME_EXCEEDED,
            GeckoSpaEvent.ERROR_RF_ERROR,
            GeckoSpaEvent.ERROR_TOO_MANY_RF_ERRORS,
        ):
            self.last_error = event.name
            self.last_error_at = time.time()

        if event == GeckoSpaEvent.CLIENT_FACADE_TEARDOWN:
            if self._facade is not None:
                await self._facade.disconnect()
            self._facade = None


class SpaClient:
    def __init__(self, config: dict) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._manager: Optional[EngineSpaManager] = None
        self._command_lock = asyncio.Lock()
        self._state_request_event = asyncio.Event()
        self._last_state_request = 0.0
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self._state: Dict[str, object] = {
            "temps": {"current_f": None, "setpoint_f": None, "units": "F"},
            "heater": {"on": False},
            "pumps": [],
            "lights": {"on": False, "color_rgb": None, "inmix": None},
            "errors": [],
            "capabilities": {
                "canSetTemp": False,
                "pumpsCount": 0,
                "hasLights": False,
                "hasInMix": False,
                "maxSetpointF": self._config.get("max_setpoint_f", 104),
            },
            "meta": {
                "lastUpdated": time.time(),
                "connectionState": "DISCONNECTED",
                "lastError": None,
                "lastErrorAt": None,
                "lastContactAt": None,
            },
        }

    def get_state(self) -> Dict[str, object]:
        with self._lock:
            return copy.deepcopy(self._state)

    def note_state_request(self) -> None:
        with self._lock:
            self._last_state_request = time.time()
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._state_request_event.set)
        else:
            self._state_request_event.set()

    def _recent_state_request(self, timeout_s: float) -> bool:
        with self._lock:
            last_request = self._last_state_request
        if last_request <= 0:
            return False
        return (time.time() - last_request) <= timeout_s

    async def _wait_for_state_request(self, timeout_s: float) -> bool:
        try:
            await asyncio.wait_for(self._state_request_event.wait(), timeout=timeout_s)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            self._state_request_event.clear()

    def is_connected(self) -> bool:
        with self._lock:
            meta = self._state.get("meta", {})
            return meta.get("connectionState") == "CONNECTED"

    async def command(self, payload: Dict[str, object]) -> Dict[str, object]:
        async with self._command_lock:
            manager = self._manager
            if manager is None or manager.facade is None:
                return {"ok": False, "error": "Spa is not connected"}

            command_type = payload.get("type")
            command_payload = payload.get("payload", {}) or {}
            facade = manager.facade

            if command_type == "light.toggle":
                if not facade.lights:
                    return {"ok": False, "error": "No lights available"}
                light = facade.lights[0]
                target_on = command_payload.get("on")
                if target_on is None:
                    target_on = not light.is_on
                if target_on:
                    await light.async_turn_on()
                else:
                    await light.async_turn_off()
                self._update_state_from_facade(facade, manager)
                return {"ok": True}

            if command_type == "pump.cycle":
                pumps = list(facade.pumps)
                if not pumps:
                    return {"ok": False, "error": "No pumps available"}
                pump_id = command_payload.get("id")
                pump = None
                if pump_id is not None:
                    for candidate in pumps:
                        if candidate.key == pump_id or candidate.name == pump_id:
                            pump = candidate
                            break
                if pump is None:
                    pump = pumps[0]

                if getattr(pump, "is_variable_speed", False):
                    if pump.is_on:
                        await pump.async_turn_off()
                    else:
                        await pump.async_turn_on()
                else:
                    modes = pump.modes or []
                    current_mode = pump.mode
                    if modes:
                        if current_mode in modes:
                            next_index = (modes.index(current_mode) + 1) % len(modes)
                        else:
                            next_index = 0
                        next_mode = modes[next_index]
                        if str(next_mode).upper() == "OFF":
                            await pump.async_turn_off()
                        else:
                            await pump.async_set_mode(next_mode)
                    else:
                        if pump.is_on:
                            await pump.async_turn_off()
                        else:
                            await pump.async_turn_on()
                self._update_state_from_facade(facade, manager)
                return {"ok": True}

            if command_type == "temp.set":
                if facade.water_heater is None or not facade.water_heater.is_available:
                    return {"ok": False, "error": "Temperature control unavailable"}
                setpoint_f = command_payload.get("setpoint_f")
                if setpoint_f is None:
                    return {"ok": False, "error": "Missing setpoint_f"}
                try:
                    setpoint_f_value = float(setpoint_f)
                except (TypeError, ValueError):
                    return {"ok": False, "error": "Invalid setpoint_f"}
                max_setpoint_f = self._config.get("max_setpoint_f", 104)
                if setpoint_f_value > max_setpoint_f:
                    setpoint_f_value = float(max_setpoint_f)

                accessors = facade.spa.accessors
                temp_units = None
                if GeckoConstants.KEY_TEMP_UNITS in accessors:
                    temp_units = accessors[GeckoConstants.KEY_TEMP_UNITS].value
                native_value = _to_native_temp(setpoint_f_value, temp_units)
                await facade.water_heater.async_set_target_temperature(native_value)
                self._update_state_from_facade(facade, manager)
                return {"ok": True}

            return {"ok": False, "error": "Unknown command"}

    async def start(self) -> None:
        if self._task is None:
            self._stop_event.clear()
            self._loop = asyncio.get_running_loop()
            self._task = asyncio.create_task(self._run(), name="spa-client")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        backoff_s = 2

        try:
            while not self._stop_event.is_set():
                env_path = Path(__file__).resolve().parent.parent / ".env"
                load_dotenv(dotenv_path=env_path, override=True)
                self._config = get_config()
                host = self._config.get("intouch2_host", "")
                poll_interval = self._config.get("state_poll_interval_ms", 1500) / 1000.0
                ui_idle_timeout = self._config.get("ui_idle_timeout_s", 10)
                if not host:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [spa] INTOUCH2_HOST not set")
                    self._set_error_state("INTOUCH2_HOST not set")
                    await asyncio.sleep(backoff_s)
                    continue

                if not self._recent_state_request(ui_idle_timeout):
                    self._set_connection_state("DISCONNECTED")
                    await self._wait_for_state_request(ui_idle_timeout)
                    continue

                try:
                    backoff_s = 2
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [spa] starting discovery against {host}")
                    self._set_connection_state("CONNECTING")
                    client_uuid = str(uuid.uuid4()).replace("-", "")
                    async with EngineSpaManager(client_uuid, host) as manager:
                        self._manager = manager
                        await manager.wait_for_descriptors()
                        descriptors = manager.spa_descriptors or []
                        if len(descriptors) == 0:
                            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [spa] discovery found no spas for {host}")
                            self._set_error_state("Spa not found at configured host")
                            await asyncio.sleep(backoff_s)
                            continue

                        spa_descriptor = descriptors[0]
                        print(
                            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [spa] discovered spa {spa_descriptor.name} at {spa_descriptor.destination}"
                        )
                        await manager.async_set_spa_info(
                            spa_descriptor.ipaddress,
                            spa_descriptor.identifier_as_string,
                            spa_descriptor.name,
                        )
                        await manager.wait_for_facade()
                        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [spa] connect attempt finished")
                        facade = manager.facade
                        if facade is None:
                            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [spa] connect failed: facade not created")
                            self._set_error_state("Failed to create facade")
                            await asyncio.sleep(backoff_s)
                            continue

                        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [spa] connected, waiting for first state update")
                        await facade.wait_for_one_update()
                        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [spa] state updates running")

                        idle_disconnect = False
                        while (
                            not self._stop_event.is_set()
                            and manager.facade is not None
                            and manager.spa_state == GeckoSpaState.CONNECTED
                        ):
                            self._update_state_from_facade(facade, manager)
                            if not self._recent_state_request(ui_idle_timeout):
                                idle_disconnect = True
                                break
                            await asyncio.sleep(poll_interval)

                        if idle_disconnect and not self._stop_event.is_set():
                            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [spa] idle: disconnecting until /spa/state requested")
                            self._set_connection_state("DISCONNECTED")
                            continue

                except Exception as exc:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [spa] exception: {exc}")
                    self._set_error_state(f"Exception: {exc}")
                    await asyncio.sleep(backoff_s)

                backoff_s = min(backoff_s * 2, 30)
        except asyncio.CancelledError:
            pass

    def _set_error_state(self, message: str) -> None:
        now = time.time()
        with self._lock:
            meta = self._state["meta"]
            meta["connectionState"] = "ERROR"
            meta["lastError"] = message
            meta["lastErrorAt"] = now
            meta["lastUpdated"] = now

    def _set_connection_state(self, state: str) -> None:
        now = time.time()
        with self._lock:
            meta = self._state["meta"]
            meta["connectionState"] = state
            meta["lastUpdated"] = now

    def _update_state_from_facade(
        self, facade: GeckoAsyncFacade, manager: EngineSpaManager
    ) -> None:
        accessors = facade.spa.accessors
        temp_units = None
        if GeckoConstants.KEY_TEMP_UNITS in accessors:
            temp_units = accessors[GeckoConstants.KEY_TEMP_UNITS].value

        current_temp = _accessor_value(
            accessors,
            [
                GeckoConstants.KEY_DISPLAYED_TEMP_G,
                GeckoConstants.KEY_RH_WATER_TEMP,
            ],
        )
        setpoint = _accessor_value(
            accessors,
            [
                GeckoConstants.KEY_REAL_SETPOINT_G,
                GeckoConstants.KEY_SETPOINT_G,
            ],
        )

        heater_on = False
        heating_accessor = accessors.get(GeckoConstants.KEY_HEATING)
        if heating_accessor is not None:
            heater_on = bool(heating_accessor.value)

        pumps = []
        for idx, pump in enumerate(facade.pumps, start=1):
            pump_id = getattr(pump, "key", None)
            if pump_id is None:
                pump_id = getattr(pump, "name", None) or f"pump-{idx}"
            pumps.append(
                {
                    "id": pump_id,
                    "label": pump.name,
                    "state": "on" if pump.is_on else "off",
                    "speed": str(pump.mode) if pump.mode is not None else None,
                }
            )

        lights: Dict[str, object] = {"on": False, "color_rgb": None, "inmix": None}
        if facade.lights:
            lights["on"] = any(light.is_on for light in facade.lights)

        inmix = facade.inmix
        inmix_info: Dict[str, object] = {"available": False, "zones": []}
        if inmix is not None and inmix.is_available:
            inmix_info["available"] = True
            zones = []
            for zone in inmix.zones:
                rgb = zone.rgb_color
                zones.append(
                    {
                        "key": zone.key,
                        "name": zone.name,
                        "on": zone.is_on,
                        "rgb": list(rgb) if rgb else None,
                        "brightness": zone.brightness,
                    }
                )
            inmix_info["zones"] = zones
            lights["inmix"] = inmix_info
            if zones and zones[0].get("rgb") is not None:
                lights["color_rgb"] = zones[0].get("rgb")

        errors = []
        error_state = facade.error_sensor.state if facade.error_sensor else "None"
        if error_state and error_state not in ("None", "No errors or warnings"):
            for entry in str(error_state).split(","):
                code = entry.strip()
                if code:
                    errors.append({"code": code, "message": code, "severity": "unknown"})

        last_contact = None
        if manager.ping_sensor and manager.ping_sensor.state is not None:
            last_contact = manager.ping_sensor.state.timestamp()

        now = time.time()
        with self._lock:
            self._state = {
                "temps": {
                    "current_f": _to_fahrenheit(current_temp, temp_units),
                    "setpoint_f": _to_fahrenheit(setpoint, temp_units),
                    "units": str(temp_units) if temp_units is not None else "F",
                },
                "heater": {"on": heater_on},
                "pumps": pumps,
                "lights": lights,
                "errors": errors,
                "capabilities": {
                    "canSetTemp": setpoint is not None,
                    "pumpsCount": len(pumps),
                    "hasLights": len(facade.lights) > 0,
                    "hasInMix": inmix is not None and inmix.is_available,
                },
                "meta": {
                    "lastUpdated": now,
                    "connectionState": _map_connection_state(manager.spa_state),
                    "lastError": manager.last_error,
                    "lastErrorAt": manager.last_error_at,
                    "lastContactAt": last_contact,
                },
            }
