"""NVML energy measurement for GB10."""
import warnings
import contextlib

warnings.filterwarnings("ignore", category=FutureWarning)

try:
    import pynvml

    pynvml.nvmlInit()
    _handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    _available = True
except Exception:
    _available = False
    _handle = None


def energy_mj() -> float:
    """Return current cumulative energy counter in mJ."""
    if not _available:
        return 0.0
    return pynvml.nvmlDeviceGetTotalEnergyConsumption(_handle)


def power_w() -> float:
    """Return current GPU power draw in watts."""
    if not _available:
        return 0.0
    return pynvml.nvmlDeviceGetPowerUsage(_handle) / 1000.0


@contextlib.contextmanager
def measure():
    """Context manager that yields an energy delta dict on exit."""
    before = energy_mj()
    result = {}
    yield result
    after = energy_mj()
    delta_mj = max(0.0, after - before)
    result["energy_mj"] = round(delta_mj, 1)
    result["energy_mwh"] = round(delta_mj / 3600, 6)
