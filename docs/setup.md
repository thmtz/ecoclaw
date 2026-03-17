# EcoClaw Setup Guide

How to get the full EcoClaw stack running on a fresh GB10. Written as we go — fill in each section when the component is validated.

## Prerequisites

- GB10 accessible via `gpuctl` (see `CLAUDE.md` for instance name)
- Python 3.12 in `~/.venvs/ml` (activate: `source ~/.profile && ml`)
- Node.js ≥22 and pnpm (see below)
- HuggingFace models downloaded (see Models section)

---

## 1. Models

Download via HuggingFace CLI (run from `~/.venvs/ml`):

```bash
# Nano — primary model (FP8, native sm_121 support)
huggingface-cli download nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8

# Super — secondary model (NVFP4+MARLIN, used in low-carbon mode)
huggingface-cli download nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4
```

Both are cached at `~/.cache/huggingface/hub/`.

---

## 2. vLLM

**Nano (FP8 — default model):**
```bash
# TBD — vllm-expert to fill in final validated command
```

**Super 120B (NVFP4+MARLIN — high-performance mode):**
```bash
# TBD — vllm-expert to fill in final validated command
```

See `docs/reference/vllm.md` for full flag reference and troubleshooting.

---

## 3. EcoClaw Python package (proxy + carbon router)

```bash
# Install dependencies into the ml venv
source ~/.profile && ml
pip install fastapi uvicorn httpx pyyaml pynvml

# Set Electricity Maps API key
mkdir -p ~/.config/electricity_maps
echo "UpuAetadx7a7TBYyMByj" > ~/.config/electricity_maps/api_key

# Run (starts proxy on :8001 + carbon router thread)
cd ~/git/hackathon/src
python -m ecoclaw.main
```

The proxy log output goes to stdout. Run in a screen session for persistence:
```bash
screen -dmS proxy bash -lc 'source ~/.profile && ml && cd ~/git/hackathon/src && python -m ecoclaw.main 2>&1 | tee /tmp/proxy.log'
```

---

## 4. OpenClaw

**Install (one-time):**
```bash
# TBD — openclaw-expert to fill in after GB10 validation
# Requires Node.js ≥22 and pnpm
```

**Configure:**
```bash
cp ~/git/hackathon/config/openclaw.json ~/.openclaw/openclaw.json
mkdir -p ~/.openclaw/workspace
cp ~/git/hackathon/config/openclaw-workspace/AGENTS.md ~/.openclaw/workspace/
cp ~/git/hackathon/config/openclaw-workspace/SOUL.md ~/.openclaw/workspace/
```

**Start gateway:**
```bash
# TBD — openclaw-expert to fill in validated start command
# Gateway runs on :18789, WebChat accessible at http://10.1.96.152:18789
```

---

## 5. Full startup sequence

Once everything is installed, start components in this order:

```bash
# 1. Start vLLM (Nano by default)
screen -dmS vllm bash -lc '...'   # TBD

# 2. Start EcoClaw proxy + carbon router
screen -dmS proxy bash -lc 'source ~/.profile && ml && cd ~/git/hackathon/src && python -m ecoclaw.main 2>&1 | tee /tmp/proxy.log'

# 3. Start OpenClaw gateway
screen -dmS openclaw bash -lc '...'   # TBD

# 4. Verify
curl http://localhost:8000/v1/models   # vLLM
curl http://localhost:8001/v1/models   # proxy (should match vLLM)
curl http://10.1.96.152:18789          # OpenClaw WebChat
```

---

## 6. Carbon router config

Default config at `~/.ecoclaw/carbon-router.yaml` (created automatically on first run):

```yaml
thresholds:
  - carbon_gt: 300
    model: nano
    label: "green mode"
  - carbon_lte: 300
    model: super
    label: "performance mode"
poll_interval_seconds: 600
fallback_carbon: 250
hysteresis: 20
```

Electricity Maps API key: `~/.config/electricity_maps/api_key`

---

## Troubleshooting

- **vLLM returns empty content** — NVFP4 on GB10 requires `VLLM_USE_FLASHINFER_MOE_FP4=0 VLLM_NVFP4_GEMM_BACKEND=marlin`. FP8 models work without this.
- **pynvml not found** — install into the ml venv: `pip install pynvml`
- **OpenClaw can't find model** — ensure `VLLM_API_KEY` is set and proxy is running on `:8001`
- See `docs/reference/gb10-validated.md` for full NVML support matrix
