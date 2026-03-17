"""Carbon router — polls Electricity Maps and switches models based on carbon intensity."""
import asyncio
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
    "poll_interval_seconds": 10,
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


def _notify_openclaw(message: str, token: str = "439368c7ef3a54d50317db8d985c5b2829ab2e494ec24e26"):
    async def _send():
        try:
            import websockets
            async with websockets.connect("ws://localhost:18789") as ws:
                await ws.send(json.dumps({"type": "req", "id": "notify-1", "method": "connect", "params": {"token": token, "scope": "operator.admin"}}))
                connect_resp_raw = await ws.recv()
                connect_resp = json.loads(connect_resp_raw)
                if connect_resp.get("type") == "error" or connect_resp.get("error"):
                    log.warning("chat.inject connect failed: %s", connect_resp)
                    return
                log.info("chat.inject connect ok: %s", connect_resp.get("type"))
                await ws.send(json.dumps({"type": "req", "id": "notify-2", "method": "chat.inject", "params": {"sessionKey": "main", "message": message, "label": "EcoClaw"}}))
                inject_resp_raw = await ws.recv()
                inject_resp = json.loads(inject_resp_raw)
                log.info("chat.inject response: %s", inject_resp)
        except Exception as e:
            log.warning("chat.inject failed: %s", e)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_send())
    except Exception as e:
        log.warning("notify_openclaw error: %s", e)
    finally:
        loop.close()


def switch_model(model_key: str, label: str):
    """Stop vLLM and restart with the new model."""
    model = MODELS[model_key]
    log.info("Switching to %s (%s)", model["short"], label)

    _notify_openclaw(
        f"⚠️ Grid carbon: {st.get().carbon_gco2:.0f} gCO₂/kWh — switching to {model['short']} ({label}). Back in ~2 min."
    )

    # Stop current vLLM
    subprocess.run(["screen", "-S", VLLM_SCREEN, "-X", "quit"], capture_output=True)
    time.sleep(2)

    # Start new vLLM
    cmd = (
        f"source ~/.profile && ml && "
        f"{model['env']} "
        f"vllm serve {model['id']} "
        f"--trust-remote-code "
        f"--reasoning-parser {model['reasoning_parser']} "
        f"--max-model-len {model['max_model_len']} "
        f"--gpu-memory-utilization {model['gpu_mem_util']} "
        f"2>&1 | tee /tmp/vllm-{model_key}.log"
    )
    subprocess.Popen(["screen", "-dmS", VLLM_SCREEN, "bash", "-lc", cmd])
    log.info("vLLM restarting with %s", model["short"])

    # Wait for vLLM to be ready
    _wait_for_vllm()

    # Update shared state
    st.update(
        model=model["id"],
        model_short=model["short"],
        mode=label,
    )
    log.info("Switch complete: now serving %s", model["short"])


def _wait_for_vllm(timeout: int = 300, poll: int = 5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get("http://localhost:8000/v1/models", timeout=2)
            if r.status_code == 200:
                log.info("vLLM is ready")
                return
        except Exception:
            pass
        time.sleep(poll)
    log.error("vLLM did not become ready within %ds", timeout)


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
        switch_model(new_key, label)
        _current_model_key = new_key
    else:
        # No switch needed — still update mode label to reflect current carbon state
        st.update(mode=_current_label(carbon, config, _current_model_key))


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
            # On startup, accept whatever model is currently running. Only log what
            # we would do — don't kill a running vLLM instance on first check.
            st.update(mode=_current_label(carbon, config, current_model_key))
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
                switch_model(new_model_key, label)
                current_model_key = new_model_key
                _current_model_key = new_model_key

        interval = config.get("poll_interval_seconds", 600)
        if poll_event is not None:
            poll_event.wait(timeout=interval)
            poll_event.clear()
        else:
            time.sleep(interval)
