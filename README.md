# EcoClaw

Every time you ask an AI a question, it burns energy. EcoClaw tells you exactly how much.

It's a chat assistant running on an NVIDIA GB10 that measures the actual joules consumed by each response using hardware counters, calculates the CO₂ footprint from live grid data, and prints a receipt at the bottom of every answer. When the grid gets dirty, it throttles the GPU to save energy. When the grid is clean, it runs at full speed.

Built at GTC 2026 "Hack for Impact" (Eco Impact track).

## What you see

Every response ends with a receipt like this:

```
─────────────────────────────
⚡ Energy: 1.42 J · 0.39 mWh · 18.4 tok/J
🌱 Grid: 180 gCO₂/kWh · 0.07 mgCO₂ this response · green mode · Nemotron Nano
─────────────────────────────
```

The energy number comes from NVML hardware counters on the GPU (not an estimate). The CO₂ number comes from the Electricity Maps API, which reports the real-time carbon intensity of the California power grid.

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
GB10 GPU (Nemotron Nano 30B)

Carbon Router ◄── Electricity Maps API (live grid carbon intensity)
 └──► adjusts GPU frequency when carbon thresholds are crossed
```

The energy proxy sits between [OpenClaw](https://github.com/openclaw/openclaw) and vLLM. It snapshots the GPU energy counter before and after each request, computes the delta, and injects the receipt into the response stream before OpenClaw ever sees it. OpenClaw itself is unmodified; we only provide config files (`config/openclaw/`).

The carbon router polls the Electricity Maps API every 10 minutes. When grid carbon crosses a threshold (default 300 gCO₂/kWh), it caps the GPU clock frequency to reduce energy use. When the grid cleans up, it removes the cap.

## Models

| Model | Active params | Quantization | Role |
|-|-|-|-|
| Nemotron Nano 30B-A3B | 3B | FP8 (native Blackwell) | Primary model, always loaded |
| Nemotron Super 120B-A12B | 12B | NVFP4 + MARLIN | Alternative for dual-model setups |

Both are MoE hybrid Mamba-Transformer architectures from NVIDIA. The Nano runs at ~72 tok/s on GB10; the Super runs at ~15-17 tok/s but produces higher quality output.

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

Optional: get a free Electricity Maps API key at https://api-portal.electricitymaps.com/ and put it in `~/.config/electricity_maps/api_key`. Without it, the carbon router uses a fallback value.

Full setup instructions: [docs/setup.md](docs/setup.md)

## How it works, in detail

- [Design overview](docs/design/index.md)
- [Energy proxy](docs/design/energy-proxy.md) (NVML measurement + receipt injection)
- [Carbon router](docs/design/carbon-router.md) (threshold logic, model switching)
- [OpenClaw integration](docs/design/openclaw.md) (provider config, workspace files)

## Team

**Neuralwatt** builds infrastructure for energy-efficient AI inference. Our main product uses Q-learning to optimize GPU power states via NVML.

## License

MIT
