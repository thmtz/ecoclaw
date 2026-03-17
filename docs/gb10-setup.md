# GB10 Setup & Environment

## Connection details

| Field | Value |
|-|-|
| Host | HP-01.local (10.1.96.152) |
| SSH user | `nvidia` (key-based auth, passwordless sudo) |
| SSH config alias | `ssh gb10` |
| gpuctl name | `gb10-hackathon` |
| Driver | 580.126.09 |
| CUDA | 13.0 |

## Installed software

Installed via `gpuctl prepare -m Qwen/Qwen2.5-0.5B-Instruct`:

- **vLLM 0.17.1** — venv at `~/.venvs/ml`, activate with `source ~/.profile && ml`
- **PyTorch 2.10.0+cu130**
- **DCGM 3.3.9**
- Rust 1.94, uv 0.10.11, ripgrep, fd, jq, yq, nvtop

Additional manual installs:

- **pynvml** — venv at `~/nvml-env`
- **cuda-cudart-12-8** (apt) — CUDA 12 compat runtime for vllm's native extensions
- **python3-dev** (apt) — needed by torch.inductor JIT at vllm startup

## Serving a model

```bash
# Start in background screen
gpuctl exec gb10-hackathon "screen -dmS vllm bash -lc 'source ~/.profile && ml && vllm serve <model>'"

# Test
gpuctl exec gb10-hackathon "curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{\"model\": \"<model>\", \"messages\": [{\"role\": \"user\", \"content\": \"hello\"}]}'"

# Check logs
gpuctl exec gb10-hackathon "screen -S vllm -X hardcopy /tmp/vllm.log && tail -20 /tmp/vllm.log"
```

## Power telemetry

| Metric | Works | Notes |
|-|-|-|
| `power.draw` | Yes | Real-time wattage via NVML |
| `totalEnergyConsumption` | Yes | Cumulative mJ counter — snapshot before/after workload |
| Power cap/limit | No | Desktop SKU, not exposed |
| GPU clock, temp, util, perf state | Yes | |
| Memory reporting | No | Unified 128GB shared CPU+GPU, nvidia-smi shows N/A |

Access via pynvml:
```bash
gpuctl exec gb10-hackathon "~/nvml-env/bin/python3 -c \"
import pynvml as nv
nv.nvmlInit()
h = nv.nvmlDeviceGetHandleByIndex(0)
print('Power:', nv.nvmlDeviceGetPowerUsage(h)/1000, 'W')
print('Energy:', nv.nvmlDeviceGetTotalEnergyConsumption(h), 'mJ')
nv.nvmlShutdown()
\""
```

## Gotchas

- **CUDA 13 only** — GB10 ships no CUDA 12 runtime. `cuda-cudart-12-8` apt package is required for vllm. Without it: `ImportError: libcudart.so.12: cannot open shared object file`.
- **python3-dev required** — torch.inductor JIT-compiles CUDA utils at vllm startup. Without `Python.h`: `fatal error: Python.h: No such file or directory`.
- **nvidia user, not root** — all gpuctl commands route through `--ssh-user nvidia`. Passwordless sudo is configured.
- **No memory reporting** — `nvidia-smi` memory fields show `[N/A]` or `Not Supported`. The GPU has access to the full 128GB unified memory.
