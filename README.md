# EcoClaw

Every time you ask an AI a question, it burns energy. EcoClaw tells you exactly how much.

It runs on an NVIDIA GB10 and measures the actual joules consumed by each response using GPU hardware counters. It calculates the CO₂ footprint using live grid data from the Electricity Maps API and prints a receipt at the bottom of every answer. A background carbon router watches grid conditions and throttles the GPU when the grid is dirty, restoring full speed when it cleans up.

Built at GTC 2026 "Hack for Impact" (Eco Impact track).

## What you see

```
─────────────────────────────
⚡ Energy: 1.42 J · 0.39 mWh · 18.4 tok/J
🌱 Grid: 180 gCO₂/kWh · 0.07 mgCO₂ this response · green mode · Nemotron Nano
📊 Session: 8.31 J total · 5 requests
─────────────────────────────
```

The energy number comes from NVML hardware counters on the GPU, not an estimate. The CO₂ number combines measured energy with the real-time carbon intensity of the California power grid (US-CAL-CISO zone). The session line tracks cumulative energy across the conversation.

## Architecture

```
User
 │
 ▼
OpenClaw (WebChat UI + agent gateway)
 │
 ▼
Energy Proxy ◄── NVML (per-request energy measurement)
 │
 ▼
vLLM (local inference)
 │
 ▼
GB10 GPU ◄── nvidia-smi freq cap (carbon router)

Carbon Router ◄── Electricity Maps API (live grid carbon intensity)
 └──► caps GPU clock frequency when carbon is high, uncaps when it drops
```

The energy proxy sits between [OpenClaw](https://github.com/openclaw/openclaw) and vLLM. It snapshots the GPU energy counter before and after each request, computes the delta, and injects the receipt into the response stream. OpenClaw is unmodified; we only provide config files (`config/openclaw/`).

The carbon router polls grid carbon intensity every 10 minutes. When carbon crosses 300 gCO₂/kWh, it caps GPU clock frequency to 300-1000 MHz via `nvidia-smi -lgc`. When the grid cleans up, it runs `nvidia-smi -rgc` to restore full speed. A 20 gCO₂/kWh hysteresis band prevents flapping. State changes push a notification into the active WebChat session via OpenClaw's `chat.inject` API.

## Model

We run Nemotron Nano 30B-A3B (FP8, 3B active params) on the GB10. It's a MoE hybrid Mamba-Transformer from NVIDIA that hits ~72 tok/s with native Blackwell FP8 kernels.

Carbon response works by adjusting GPU clock frequency rather than switching models. This gives instant transitions with no downtime, and keeps the system simple (one model loaded, one vLLM process).

## Running it

You need an NVIDIA GB10 (or another Blackwell GPU with NVML energy counter support), Python 3.10+, vLLM 0.17+, and [OpenClaw](https://github.com/openclaw/openclaw).

```bash
# 1. Start vLLM
vllm serve nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8 \
  --port 8000 --max-model-len 32768

# 2. Start EcoClaw (proxy on :8001 + carbon router)
PYTHONPATH=src python -m ecoclaw.main

# 3. Point OpenClaw at the proxy, not vLLM directly
# Set baseUrl to http://localhost:8001 in ~/.openclaw/openclaw.json

# 4. Open the chat UI
open http://localhost:18789
```

Get a free Electricity Maps API key at https://api-portal.electricitymaps.com/ and put it in `~/.config/electricity_maps/api_key`. Without one, the carbon router falls back to a default value.

Full setup: [docs/setup.md](docs/setup.md)

## More detail

- [Design overview](docs/design/index.md)
- [Energy proxy](docs/design/energy-proxy.md) (NVML measurement, receipt injection)
- [Carbon router](docs/design/carbon-router.md) (threshold logic, freq cap)
- [OpenClaw integration](docs/design/openclaw.md) (provider config, workspace files)

## Team

**Neuralwatt** builds infrastructure for energy-efficient AI inference. Our main product uses Q-learning to optimize GPU power states via NVML.

## License

MIT
