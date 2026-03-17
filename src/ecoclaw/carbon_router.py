"""Carbon router — polls Electricity Maps and switches models based on carbon intensity."""
import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path

import httpx

from . import state as st

log = logging.getLogger(__name__)

CONFIG_FILE = Path.home() / ".ecoclaw" / "carbon-router.yaml"
API_KEY_FILE = Path.home() / ".config" / "electricity_maps" / "api_key"
MOCK_FILE = Path.home() / ".ecoclaw" / "mock_carbon"
ZONE = "US-CAL-CISO"

DEFAULT_CONFIG = {
    "thresholds": [
        {"carbon_gt": 300, "model": "nano", "label": "green mode"},
        {"carbon_lte": 300, "model": "super", "label": "performance mode"},
    ],
    "poll_interval_seconds": 86400,  # manual control only via /demo/poll
    "fallback_carbon": 250,
    "hysteresis": 20,
}

MODELS = {
    "nano": {
        "id": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8",
        "short": "Nemotron Nano 30B",
        "gpu_mem_util": 0.9,
        "max_model_len": 32768,
        "reasoning_parser": "nano_v3",
        "env": "VLLM_USE_FLASHINFER_MOE_FP8=1",
    },
    "super": {
        "id": "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4",
        "short": "Nemotron Super 120B",
        "gpu_mem_util": 0.75,
        "max_model_len": 4096,
        "reasoning_parser": "super_v3",
        "env": "VLLM_USE_FLASHINFER_MOE_FP4=0 VLLM_NVFP4_GEMM_BACKEND=marlin",
    },
}

VLLM_SCREEN = "vllm"

_current_model_key: str = "nano"


def load_config() -> dict:
    try:
        import yaml
        if CONFIG_FILE.exists():
            return yaml.safe_load(CONFIG_FILE.read_text())
    except ImportError:
        pass
    return DEFAULT_CONFIG


def load_api_key() -> str:
    if API_KEY_FILE.exists():
        return API_KEY_FILE.read_text().strip()
    return os.environ.get("ELECTRICITY_MAPS_API_KEY", "")


def fetch_carbon(api_key: str, fallback: float) -> float:
    if MOCK_FILE.exists():
        try:
            val = float(MOCK_FILE.read_text().strip())
            log.info("Using mock carbon: %s gCO2/kWh", val)
            return val
        except Exception:
            pass
    if not api_key:
        log.warning("No Electricity Maps API key — using fallback carbon %s", fallback)
        return fallback
    try:
        r = httpx.get(
            f"https://api.electricitymaps.com/v3/carbon-intensity/latest?zone={ZONE}",
            headers={"auth-token": api_key},
            timeout=10,
        )
        r.raise_for_status()
        value = r.json()["carbonIntensity"]
        log.info("Carbon intensity: %s gCO2/kWh", value)
        return float(value)
    except Exception as e:
        log.warning("Electricity Maps API error: %s — using fallback %s", e, fallback)
        return fallback


def select_model(carbon: float, config: dict, current_model: str) -> tuple[str, str]:
    """Return (model_key, label) based on carbon intensity and thresholds."""
    hysteresis = config.get("hysteresis", 20)
    for threshold in config["thresholds"]:
        if "carbon_gt" in threshold:
            limit = threshold["carbon_gt"]
            # Apply hysteresis: only switch TO green if carbon is clearly above threshold
            if current_model != "nano" and carbon > limit + hysteresis:
                return threshold["model"], threshold["label"]
            if current_model == "nano" and carbon > limit - hysteresis:
                return threshold["model"], threshold["label"]
        elif "carbon_lte" in threshold:
            limit = threshold["carbon_lte"]
            if current_model != "super" and carbon <= limit - hysteresis:
                return threshold["model"], threshold["label"]
            if current_model == "super" and carbon <= limit + hysteresis:
                return threshold["model"], threshold["label"]
    # No change
    return None, None


def _apply_freq_cap(min_mhz: int = 300, max_mhz: int = 1000):
    """Cap GPU SM frequency for green mode."""
    try:
        result = subprocess.run(
            ["sudo", "nvidia-smi", "-lgc", f"{min_mhz},{max_mhz}"],
            capture_output=True, text=True
        )
        log.info("Freq cap applied (%d-%d MHz): %s", min_mhz, max_mhz, result.stdout.strip())
    except Exception as e:
        log.warning("Freq cap failed: %s", e)


def _reset_freq_cap():
    """Remove GPU frequency cap for performance mode."""
    try:
        result = subprocess.run(
            ["sudo", "nvidia-smi", "-rgc"],
            capture_output=True, text=True
        )
        log.info("Freq cap reset: %s", result.stdout.strip())
    except Exception as e:
        log.warning("Freq cap reset failed: %s", e)


def _notify_openclaw(message: str, token: str | None = None):
    """Push a message into the active OpenClaw WebChat session via chat.inject.

    Uses sync websocket-client (not async websockets) since this runs in a
    daemon thread where creating a new event loop is fragile.
    Token is read from OPENCLAW_TOKEN env var or ~/.openclaw/openclaw.json.
    """
    if token is None:
        token = os.environ.get("OPENCLAW_TOKEN", "")
    if not token:
        # Try to read from OpenClaw config
        oc_config = Path.home() / ".openclaw" / "openclaw.json"
        if oc_config.exists():
            try:
                token = json.loads(oc_config.read_text()).get("gateway", {}).get("auth", {}).get("token", "")
            except Exception:
                pass
    if not token:
        log.warning("No OpenClaw token — skipping chat.inject notification")
        return
    try:
        from websocket import create_connection

        ws = create_connection("ws://localhost:18789", timeout=5)
        try:
            # Step 1: connect handshake with admin scope
            ws.send(json.dumps({
                "type": "req", "id": "notify-1", "method": "connect",
                "params": {"token": token, "scope": "operator.admin"},
            }))
            connect_resp = json.loads(ws.recv())
            if connect_resp.get("type") == "error" or connect_resp.get("error"):
                log.warning("chat.inject connect failed: %s", connect_resp)
                return
            log.info("chat.inject connect ok: %s", connect_resp.get("type"))

            # Step 2: inject the message
            ws.send(json.dumps({
                "type": "req", "id": "notify-2", "method": "chat.inject",
                "params": {"sessionKey": "main", "message": message, "label": "EcoClaw"},
            }))
            inject_resp = json.loads(ws.recv())
            if inject_resp.get("type") == "error" or inject_resp.get("error"):
                log.warning("chat.inject rejected: %s", inject_resp)
            else:
                log.info("chat.inject ok: %s", inject_resp)
        finally:
            ws.close()
    except ImportError:
        log.warning("websocket-client not installed — skipping chat.inject notification")
    except Exception as e:
        log.warning("chat.inject failed: %s", e)


def apply_carbon_action(model_key: str, label: str):
    """Apply carbon-aware action: freq cap for green mode, reset for performance mode."""
    model = MODELS[model_key]
    log.info("Carbon action: %s (%s)", model["short"], label)

    _notify_openclaw(
        f"⚡ Grid carbon: {st.get().carbon_gco2:.0f} gCO₂/kWh — switching to {label}. "
        f"{'Throttling GPU to save energy.' if model_key == 'nano' else 'Restoring full GPU performance.'}"
    )

    if model_key == "nano":
        # Dirty grid: cap frequency to reduce energy
        _apply_freq_cap(300, 1000)
        gpu_status = "throttled @ 1000 MHz"
    else:
        # Clean grid: restore full frequency
        _reset_freq_cap()
        gpu_status = "full speed @ 2398 MHz"

    # Never change state.model — we're freq-capping, not switching models.
    # The loaded model (Nano FP8) stays constant; only GPU clock and display change.
    nano = MODELS["nano"]
    st.update(
        model_short=f"{nano['short']} · {gpu_status}",
        mode=label,
    )
    log.info("Carbon action complete: %s", gpu_status)


def _current_label(carbon: float, config: dict, model_key: str) -> str:
    """Return the mode label for the current carbon level regardless of whether a switch is needed."""
    for threshold in config["thresholds"]:
        if "carbon_gt" in threshold and carbon > threshold["carbon_gt"]:
            return threshold["label"]
        if "carbon_lte" in threshold and carbon <= threshold["carbon_lte"]:
            return threshold["label"]
    return MODELS[model_key]["short"]


def _demo_poll():
    """One-shot poll used by the /demo/poll endpoint."""
    global _current_model_key
    config = load_config()
    api_key = load_api_key()
    carbon = fetch_carbon(api_key, config.get("fallback_carbon", 250))
    st.update(carbon_gco2=carbon)
    new_key, label = select_model(carbon, config, _current_model_key)
    if new_key and new_key != _current_model_key:
        apply_carbon_action(new_key, label)
        _current_model_key = new_key
    else:
        # No switch needed — still update mode + apply/remove freq cap based on carbon level
        label = _current_label(carbon, config, _current_model_key)
        if label == "green mode":
            _apply_freq_cap(300, 1000)
            st.update(mode=label, model_short=f"{MODELS['nano']['short']} · throttled @ 1000 MHz")
        else:
            _reset_freq_cap()
            st.update(mode=label, model_short=f"{MODELS['nano']['short']} · full speed @ 2398 MHz")


def run(initial_model_key: str = "nano", poll_event: threading.Event | None = None):
    """Main carbon router loop. Runs forever."""
    global _current_model_key
    config = load_config()
    api_key = load_api_key()
    current_model_key = initial_model_key
    _current_model_key = initial_model_key

    log.info("Carbon router started — initial model: %s (no switch on first poll)", current_model_key)
    st.update(
        model=MODELS[current_model_key]["id"],
        model_short=MODELS[current_model_key]["short"],
        mode="startup",
    )

    first_poll = True
    while True:
        carbon = fetch_carbon(api_key, config.get("fallback_carbon", 250))
        st.update(carbon_gco2=carbon)

        if first_poll:
            # On startup, apply freq cap based on carbon level, then defer model switch.
            label = _current_label(carbon, config, current_model_key)
            if label == "green mode":
                _apply_freq_cap(300, 1000)
                st.update(mode=label, model_short=f"{MODELS['nano']['short']} · throttled @ 1000 MHz")
            else:
                _reset_freq_cap()
                st.update(mode=label, model_short=f"{MODELS['nano']['short']} · full speed @ 2398 MHz")
            new_model_key, label = select_model(carbon, config, current_model_key)
            if new_model_key and new_model_key != current_model_key:
                log.info(
                    "Startup: carbon=%s → would switch to %s, but deferring until next poll",
                    carbon, new_model_key,
                )
            first_poll = False
        else:
            new_model_key, label = select_model(carbon, config, current_model_key)
            if new_model_key and new_model_key != current_model_key:
                apply_carbon_action(new_model_key, label)
                current_model_key = new_model_key
                _current_model_key = new_model_key

        interval = config.get("poll_interval_seconds", 600)
        if poll_event is not None:
            poll_event.wait(timeout=interval)
            poll_event.clear()
        else:
            time.sleep(interval)
