# EcoClaw

**An AI assistant that shows you the real energy cost of every response — and adapts to the carbon intensity of your electric grid.**

EcoClaw instruments local LLM inference with per-response energy receipts, making the hidden environmental cost of AI conversations visible. When the grid is dirty, it automatically switches to a smaller, more efficient model. When the grid is clean, it uses the larger, more capable one.

Built for the NVIDIA GTC 2026 "Hack for Impact" hackathon (Eco Impact track), running entirely on a single GB10 workstation.

## How it works

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
GB10 GPU (Nemotron Nano 30B or Super 120B)

Carbon Router ◄── Electricity Maps API (live grid carbon intensity)
 └──► switches models when carbon thresholds are crossed
```

**Every response includes an energy receipt:**

```
─────────────────────────────
⚡ Energy: 1.42 J · 0.39 mWh · 18.4 tok/J
🌱 Grid: 180 gCO₂/kWh · 0.07 mgCO₂ this response · green mode · Nemotron Nano
─────────────────────────────
```

## Key features

- **Per-response energy measurement** — NVML hardware counters measure exact millijoules consumed per inference call. No estimation, no averaging.
- **Live carbon-aware model switching** — Polls the Electricity Maps API for real-time grid carbon intensity. When carbon is high, switches to the efficient Nemotron Nano 30B (3B active params). When carbon is low, switches to the more capable Nemotron Super 120B (12B active params).
- **CO₂ per response** — Combines measured energy with live grid intensity to show actual grams of CO₂ attributable to each answer.
- **Demo control endpoints** — `POST /demo/carbon/{value}` and `POST /demo/poll` let you simulate any grid state for live demos.

## Models

| Model | Active params | Quantization | Role |
|-|-|-|-|
| Nemotron Nano 30B-A3B | 3B | FP8 (native Blackwell) | Green mode — high carbon grid |
| Nemotron Super 120B-A12B | 12B | NVFP4 + MARLIN | Performance mode — clean grid |

Both are MoE hybrid Mamba-Transformer architectures from NVIDIA.

## Running it

### Prerequisites

- NVIDIA GB10 (or any Blackwell GPU with NVML support)
- Python 3.10+
- vLLM 0.17+
- [OpenClaw](https://github.com/openclaw/openclaw) installed and configured
- Electricity Maps API key (free tier works) at `~/.config/electricity_maps/api_key`

### Quick start

```bash
# 1. Start vLLM with Nemotron Nano
vllm serve nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8 \
  --port 8000 --max-model-len 32768

# 2. Start the EcoClaw energy proxy + carbon router
PYTHONPATH=src python -m ecoclaw.main

# 3. Point OpenClaw at the proxy (port 8001, not vLLM directly)
# In ~/.openclaw/openclaw.json, set vLLM provider baseUrl to http://localhost:8001

# 4. Open WebChat
open http://localhost:18789
```

See [docs/setup.md](docs/setup.md) for detailed installation and configuration.

## Architecture details

- [Design overview](docs/design/index.md) — full architecture, component descriptions, config format
- [Energy proxy](docs/design/energy-proxy.md) — how NVML measurement and receipt injection work
- [Carbon router](docs/design/carbon-router.md) — threshold-based model switching logic
- [OpenClaw integration](docs/design/openclaw.md) — provider config, workspace setup

## Tech stack

| Component | Technology |
|-|-|
| LLM serving | vLLM 0.17 on GB10 |
| Models | Nemotron Nano 30B FP8, Nemotron Super 120B NVFP4 |
| Energy measurement | NVML (`nvmlDeviceGetTotalEnergyConsumption`) |
| Carbon data | Electricity Maps API (US-CAL-CISO zone) |
| Chat UI + gateway | OpenClaw |
| Proxy + router | Python (FastAPI/uvicorn) |

## Team

**Neuralwatt** — AI infrastructure startup focused on energy-efficient inference. Our core product uses Q-learning to optimize GPU power states via NVML, maximizing tokens-per-joule for LLM workloads.

## License

MIT
