# GB10 Validated Hardware & Software Report

**Every claim in this doc was tested on our actual GB10 device.** Nothing is speculated or taken from external sources. If it's listed here, we ran the command and saw the output. This is the ground truth for what we can and can't do on this hardware.

Last validated: 2026-03-17

## System

| Field | Value |
|-|-|
| Hostname | HP-01 |
| OS | Ubuntu 24.04.4 LTS (Noble Numbat) |
| Kernel | 6.17.0-1008-nvidia aarch64 |
| Product | NVIDIA GB10 (HP ZGX Nano) |
| Architecture | Blackwell |
| Driver | 580.126.09 |
| CUDA | 13.0 |
| GPU UUID | GPU-e8574d59-a46c-d820-e2b6-a55e3b030f89 |

## CPU

| Field | Value |
|-|-|
| Architecture | aarch64 (ARM v9.2) |
| Total cores | 20 (big.LITTLE) |
| Big cores | 10x Cortex-X925 (up to 3900 MHz) |
| Little cores | 10x Cortex-A725 |
| Threads per core | 1 |
| Min freq | 1378 MHz |
| Max freq | 3900 MHz |

## Memory

| Field | Value |
|-|-|
| Total | 119 GiB reported by OS (128GB physical LPDDR5X) |
| Type | Unified CPU+GPU (no discrete VRAM) |
| GPU memory reporting | **Not working** — nvidia-smi shows `[N/A]` for total/used/free |
| System memory | Visible via `/proc/meminfo` and `free -h` |

## GPU

| Field | Value |
|-|-|
| Name | NVIDIA GB10 |
| CUDA cores | 6144 (48 SMs) |
| Architecture ID | 10 (Blackwell) |
| SM clock (idle) | 2385 MHz |
| SM clock (max) | 3003 MHz |
| Video clock | 2073 MHz |
| PCIe gen | 1 (NVLink C2C, reported as PCIe) |
| PCIe width | 1 |
| Persistence mode | On |
| Compute mode | Default |

## NVML metrics — what works and what doesn't

Tested via pynvml and nvidia-smi.

### Working

| Metric | API | Notes |
|-|-|-|
| Power draw | `nvmlDeviceGetPowerUsage` | Real-time watts, ~11W idle, responsive to load |
| Total energy | `nvmlDeviceGetTotalEnergyConsumption` | Cumulative mJ counter — diff before/after for per-request energy |
| Temperature | `nvmlDeviceGetTemperature` | GPU temp in Celsius |
| SM clock | `nvmlDeviceGetClockInfo(0)` | Current SM frequency |
| Video clock | `nvmlDeviceGetClockInfo(3)` | Current video engine frequency |
| Max SM clock | `nvmlDeviceGetMaxClockInfo(0)` | 3003 MHz |
| Perf state | `nvmlDeviceGetPerformanceState` | Returns 0 (P0) |
| GPU utilization | `nvidia-smi --query-gpu=utilization.gpu` | Percentage, works |
| GPU name | `nvmlDeviceGetName` | "NVIDIA GB10" |
| UUID | `nvmlDeviceGetUUID` | Works |
| Core count | `nvmlDeviceGetNumGpuCores` | 6144 |
| Architecture | `nvmlDeviceGetArchitecture` | 10 |

### Not supported (returns error or N/A)

| Metric | API | Notes |
|-|-|-|
| Memory clock | `nvmlDeviceGetClockInfo(2)` | NVMLError_NotSupported |
| Max memory clock | `nvmlDeviceGetMaxClockInfo(2)` | NVMLError_NotSupported |
| Memory info | `nvmlDeviceGetMemoryInfo` | No discrete VRAM — unified memory |
| Power limit | `nvmlDeviceGetPowerManagementLimit` | Desktop SKU, not exposed |
| Default power limit | `nvmlDeviceGetPowerManagementDefaultLimit` | Not exposed |
| Enforced power limit | `nvmlDeviceGetEnforcedPowerLimit` | Not exposed |
| Fan speed | `nvmlDeviceGetFanSpeed` | Not exposed |
| ECC mode | `nvmlDeviceGetEccMode` | Not exposed |
| Serial number | `nvmlDeviceGetSerial` | Returns N/A |
| Memory utilization | `nvidia-smi --query-gpu=utilization.memory` | Returns 0% always |
| DCGM metrics | `dcgmi dmon` | "Module not loaded" error — DCGM discovery works but monitoring does not |

## Memory reporting

GPU-specific memory (total/used/free) is not available via nvidia-smi or NVML due to unified memory architecture. However, there are two working alternatives:

### Per-process GPU memory (works)

`nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv` reports per-process GPU memory usage. Example output with vLLM running Qwen 0.5B:

```
pid, process_name, used_gpu_memory [MiB]
37388, VLLM::EngineCore, 109832 MiB
```

This is the only nvidia-smi memory query that works on GB10. It reports how much unified memory each GPU process has allocated.

### System memory via /proc/meminfo (works)

Since memory is unified, `/proc/meminfo` and `free -h` reflect total system memory including GPU allocations:

```
MemTotal:       125443120 kB  (~119 GiB)
```

### torch.cuda.mem_get_info (not tested yet)

PyTorch's `torch.cuda.mem_get_info()` may work — needs validation with a running CUDA context.

## GPU clock control

### Clock locking (works)

`nvidia-smi -lgc` successfully locks GPU clocks to a specified range. Requires sudo.

```bash
sudo nvidia-smi -lgc 300,3003   # full range (default)
sudo nvidia-smi -lgc 300,1500   # cap at 1500 MHz (half max)
sudo nvidia-smi -lgc 2500,3003  # lock to high clocks
sudo nvidia-smi -rgc             # reset to default
```

Clock range: 300 MHz (min) to 3003 MHz (max SM clock).

**This is a key lever for energy experiments** — we can cap GPU frequency to trade performance for power efficiency, then measure the tok/J impact.

### Supported clock queries (not working)

`nvidia-smi --query-supported-clocks` returns `[N/A]` — we can't enumerate discrete supported clock steps, but arbitrary values within the range do work with `-lgc`.

## Power control

### Power limit (not supported)

```
$ nvidia-smi -pl 100
Changing power management limit is not supported in current scope for GPU: 0000000F:01:00.0
```

Cannot set or read power limits. This is a desktop/SoC SKU limitation — power capping via NVML or nvidia-smi is not exposed.

### Power measurement (works — see NVML metrics above)

We can *measure* power but cannot *cap* it. The only way to control power consumption is indirectly via clock frequency locking.

## NVML utilization note

`nvmlDeviceGetUtilizationRates` returns an object but with empty/zero fields. `nvidia-smi --query-gpu=utilization.gpu` does return a percentage. Use nvidia-smi or poll power draw directly for load detection.

## Installed software

| Tool | Version | Location |
|-|-|-|
| vLLM | 0.17.1 | `~/.venvs/ml` (activate: `source ~/.profile && ml`) |
| PyTorch | 2.10.0+cu130 | in ml venv |
| pynvml | latest | `~/nvml-env` |
| DCGM | 3.3.9 | `/usr/bin/dcgmi` (discovery only, monitoring broken) |
| Rust | 1.94 | system |
| Node.js | TBD | needed for OpenClaw |
| OpenClaw | 2026.3.14 | `~/git/openclaw` (cloned, not yet set up) |

## Disk

| Field | Value |
|-|-|
| Device | /dev/nvme0n1p2 |
| Total | 3.6 TB |
| Used | 1.2 TB |
| Available | 2.3 TB |

## hwmon sensors

| hwmon | Name | Notes |
|-|-|-|
| hwmon0 | acpi_fan | Fan control |
| hwmon1 | acpitz | ACPI thermal zone (50.1°C observed) |
| hwmon2 | nvme | NVMe drive temp |
| hwmon3-6 | mlx5 | ConnectX-7 NIC (4 instances) |
| hwmon7 | mt7925_phy0 | WiFi radio |

## CUDA capability and PyTorch compatibility

GB10 is CUDA compute capability **sm_121**. PyTorch 2.10+cu130 (what's installed) caps at **sm_120**. This causes critical failures with certain quantization kernels:

- CUTLASS TMA WS grouped GEMM (used by NVFP4 MoE models) fails to initialize on sm_121:
  ```
  Failed to initialize cutlass TMA WS grouped gemm. Error: Error Internal
  ```
- The FlashInfer autotuner skips failing tactics but remaining tactics produce **NaN logits**
- Result: model generates tokens (completion_tokens > 0) but all decode to empty string `""`
- Confirmed by `ValueError: Out of range float values are not JSON compliant: nan` when requesting logprobs
- Affects BOTH normal mode and `--enforce-eager` — this is a kernel issue, not a graph capture issue
- PyTorch prints on startup: `Maximum cuda capability supported by this version of PyTorch is (12.0)`

**Practical impact:** NVFP4 quantized MoE models (Nemotron-3-Nano/Super NVFP4) do not work on this device with PyTorch 2.10+cu130. FP8 and BF16 quantized variants are being tested as alternatives — they use different kernels that may not hit this limitation.

## What's NOT available

- **tegrastats** — not found on this device despite ChatGPT's claims. Not in PATH, not in /usr/bin.
- **DCGM monitoring** — discovery works but `dcgmi dmon` fails with "module not loaded"
- **GPU memory reporting** — no way to query GPU-specific memory usage (unified architecture)
- **Power capping** — cannot set or read power limits
- **Memory clock info** — not exposed via NVML

## Energy measurement strategy

The cleanest path for per-inference energy measurement:

```python
import pynvml
pynvml.nvmlInit()
handle = pynvml.nvmlDeviceGetHandleByIndex(0)

# Before inference
e_before = pynvml.nvmlDeviceGetTotalEnergyConsumption(handle)  # mJ

# ... run inference ...

# After inference
e_after = pynvml.nvmlDeviceGetTotalEnergyConsumption(handle)  # mJ
energy_mj = e_after - e_before
energy_mwh = energy_mj / 3600
```

The hardware counter does the integration — no need for power sampling or averaging. This is the most accurate method available on this device.

See also: [GB10 setup & environment](gb10-setup.md) for connection details and gotchas.
