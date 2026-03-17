# EcoClaw Setup Guide

**Note:** gpuctl syncs the repo to `~/dev/hackathon` on GB10 (not `~/git/hackathon`).

How to get the full EcoClaw stack running on a fresh GB10. Written as we go — fill in each section when the component is validated.

## Prerequisites

- GB10 accessible via `gpuctl` (see `CLAUDE.md` for instance name)
- Instance prepared via `gpuctl prepare gb10-hackathon -m Qwen/Qwen2.5-0.5B-Instruct` (baseline)

## Additional installs (beyond gpuctl prepare)

These were installed manually on top of the base prepare — document so they can be reproduced:

```bash
# CUDA 12 compat runtime — required by vLLM's native extensions
sudo apt install cuda-cudart-12-8

# Python headers — required by torch.inductor JIT at vLLM startup
sudo apt install python3-dev

# pynvml — NVML Python bindings for energy measurement
# Install into nvml-env (separate from ml venv to avoid conflicts)
python3 -m venv ~/nvml-env
~/nvml-env/bin/pip install pynvml

# Also install into ml venv for the EcoClaw proxy
source ~/.profile && ml
pip install pynvml fastapi uvicorn httpx pyyaml

# Node.js v22 — required for OpenClaw (already on GB10 at v22.22.1)
# If missing: curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash && sudo apt install nodejs
node --version   # verify ≥22

# pnpm — Node package manager for OpenClaw
npm install -g pnpm
pnpm --version   # verify installed
```

**What gpuctl prepare already installs:** vLLM 0.17.1, PyTorch 2.10, DCGM 3.3.9, Rust, uv, ripgrep, fd, jq, yq, nvtop

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

**Nano (FP8 — default/green-mode model, validated):**
```bash
screen -dmS vllm bash -lc 'source ~/.profile && ml && \
  VLLM_USE_FLASHINFER_MOE_FP8=1 \
  vllm serve nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8 \
    --trust-remote-code \
    --max-model-len 32768 \
    --reasoning-parser nano_v3 \
    --reasoning-parser-plugin ~/.cache/huggingface/hub/models--nvidia--NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4/snapshots/ce1b118ae66ec705d02c241525192832eb045fd3/nano_v3_reasoning_parser.py \
  2>&1 | tee /tmp/vllm-nano.log'
```

**Super 120B (NVFP4+MARLIN — performance-mode model, TBD):**
```bash
# Final config pending Super 120B validation — see docs/reference/vllm.md
screen -dmS vllm bash -lc 'source ~/.profile && ml && \
  VLLM_USE_FLASHINFER_MOE_FP4=0 VLLM_NVFP4_GEMM_BACKEND=marlin \
  vllm serve nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 \
    --trust-remote-code \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.75 \
    --reasoning-parser super_v3 \
  2>&1 | tee /tmp/vllm-super.log'
```

Note: carbon router handles model switching automatically. Manually start whichever model you want initially; the router will switch as needed after the first poll interval.

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
cd ~/dev/hackathon
PYTHONPATH=src python -m ecoclaw.main
```

The proxy log output goes to stdout. Run in a screen session for persistence:
```bash
screen -dmS proxy bash -lc 'source ~/.profile && ml && cd ~/dev/hackathon && PYTHONPATH=src python -m ecoclaw.main 2>&1 | tee /tmp/proxy.log'
```

---

## 4. OpenClaw

**Install (one-time, validated):**
```bash
# Node.js v22.22.1 and pnpm 10.32.1 already on GB10
cd ~/git/openclaw && pnpm install
pnpm ui:build   # required — without this, browser shows "Missing Control UI assets"
```

**Configure:**
```bash
mkdir -p ~/.openclaw/workspace
cp ~/dev/hackathon/config/openclaw/openclaw.json ~/.openclaw/openclaw.json
cp ~/dev/hackathon/config/openclaw-workspace/AGENTS.md ~/.openclaw/workspace/
cp ~/dev/hackathon/config/openclaw-workspace/SOUL.md ~/.openclaw/workspace/
```

**Start gateway (validated):**
```bash
screen -dmS openclaw bash -lc 'cd ~/git/openclaw && VLLM_API_KEY=none npx openclaw gateway --port 18789 --verbose 2>&1 | tee /tmp/openclaw.log'
```

WebChat accessible at `http://10.1.96.152:18789` from laptop on same network.

**Important:** Do NOT run `openclaw onboard` — it's interactive and overwrites config.

---

## 5. Full startup sequence

Once everything is installed, start components in this order:

```bash
# 1. Start vLLM with Nano FP8
screen -dmS vllm bash -lc 'source ~/.profile && ml && VLLM_USE_FLASHINFER_MOE_FP8=1 vllm serve nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8 --trust-remote-code --max-model-len 32768 --reasoning-parser nano_v3 --reasoning-parser-plugin ~/.cache/huggingface/hub/models--nvidia--NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4/snapshots/ce1b118ae66ec705d02c241525192832eb045fd3/nano_v3_reasoning_parser.py 2>&1 | tee /tmp/vllm-nano.log'

# 2. Wait for vLLM to be ready (~2-5 min with warm cache)
watch -n5 'curl -s http://localhost:8000/v1/models'

# 3. Start EcoClaw proxy + carbon router
screen -dmS proxy bash -lc 'source ~/.profile && ml && cd ~/dev/hackathon && PYTHONPATH=src python -m ecoclaw.main 2>&1 | tee /tmp/proxy.log'

# 4. Start OpenClaw gateway
screen -dmS openclaw bash -lc 'cd ~/git/openclaw && VLLM_API_KEY=none npx openclaw gateway --port 18789 --verbose 2>&1 | tee /tmp/openclaw.log'

# 5. Start SSH tunnel for browser access (run on your local machine)
ssh -N -L 18789:localhost:18789 nvidia@10.1.96.152 &
# Then open: http://localhost:18789
# Gateway token: check ~/.openclaw/openclaw.json → gateway.auth.token

# 6. Verify
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
