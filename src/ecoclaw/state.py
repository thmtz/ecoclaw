"""Shared state between energy proxy and carbon router."""
import json
import threading
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timezone

STATE_FILE = Path.home() / ".ecoclaw" / "state.json"


@dataclass
class EcoClawState:
    carbon_gco2: float = 250.0
    mode: str = "balanced"
    model: str = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4"
    model_short: str = "Nemotron Nano 30B"
    updated_at: str = ""

    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc).isoformat()


_lock = threading.Lock()
_state = EcoClawState()


def get() -> EcoClawState:
    with _lock:
        return EcoClawState(**asdict(_state))


def update(**kwargs) -> EcoClawState:
    global _state
    with _lock:
        for k, v in kwargs.items():
            setattr(_state, k, v)
        _state.updated_at = datetime.now(timezone.utc).isoformat()
        _persist()
        return EcoClawState(**asdict(_state))


def _persist():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(asdict(_state), indent=2))


def load_from_disk():
    """Load persisted state on startup."""
    global _state
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            _state = EcoClawState(**data)
        except Exception:
            pass  # Fall back to defaults
