import os


def getenv_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_config() -> dict:
    return {
        "intouch2_host": os.getenv("INTOUCH2_HOST", ""),
        "intouch2_mac": os.getenv("INTOUCH2_MAC", ""),
        "max_setpoint_f": getenv_int("MAX_SETPOINT_F", 104),
        "command_rate_limit_ms": getenv_int("COMMAND_RATE_LIMIT_MS", 1000),
        "state_poll_interval_ms": getenv_int("STATE_POLL_INTERVAL_MS", 1500),
        "state_log_interval_s": getenv_int("STATE_LOG_INTERVAL_S", 60),
        "log_dir": os.getenv("LOG_DIR", "./logs"),
        "automations_file": os.getenv("AUTOMATIONS_FILE", "./automations.json")
    }
