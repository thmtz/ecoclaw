# EcoClaw — Current Status

**Hackathon day: March 17, 2026** · NVIDIA GTC 2026 "Hack for Impact" · San Jose

**Repo:** `~/git/hackathon` | **GB10:** `gb10-hackathon` (10.1.96.152)

---

## Architecture

```
Browser (SSH tunnel → localhost:18789)
    │
    ▼
OpenClaw gateway (:18789)
    │ vLLM provider, baseUrl=:8001
    ▼
Energy proxy (:8001)  ◄── NVML energy measurement
    │ injects energy receipt into every SSE response
    ▼
vLLM (:8000)
    │
    ▼
GB10 GPU (Nemotron model)

Carbon router (thread in proxy)  ◄── Electricity Maps API (US-CAL-CISO)
    └──► polls every 10 min, switches vLLM model when carbon crosses threshold
```

---

## Component Status

| Component | Status | Notes |
|-|-|-|
| Nemotron Super 120B NVFP4+MARLIN | ⏳ Loading | `--gpu-memory-utilization 0.75`, screen session `vllm` |
| Nemotron Nano 30B FP8 | ✅ Validated | Fallback model, CUDA cache primed |
| Energy proxy | ⏳ Deploying | python-dev agent deploying now |
| OpenClaw gateway | ⏳ Reconfiguring | openclaw-expert agent updating config |
| Carbon router | ⏳ Not started | Starts with proxy (thread in main.py) |
| WebUI HTTPS fix | ⏳ In progress | SSH tunnel: `ssh -N -L 18789:localhost:18789 nvidia@10.1.96.152` |

---

## What's Done

- ✅ All design docs + reference docs validated on real hardware
- ✅ Source code written: proxy, carbon router, state, NVML wrapper
- ✅ OpenClaw workspace files deployed (AGENTS.md, SOUL.md)
- ✅ Nano FP8 and Nano NVFP4+MARLIN both validated
- ✅ Carbon router startup bug fixed
- ✅ NemoClaw decision: **use raw OpenClaw** (already working, NemoClaw unvalidated)

---

## Active Work (as of session start)

- **vllm-expert** — monitoring Super 120B load, will signal when ready
- **python-dev** — deploying proxy with model-ID rewrite fix
- **openclaw-expert** — updating openclaw.json (Nemotron models + :8001), SSH tunnel for WebUI

---

## Critical Path to Demo

1. ⏳ Super 120B finishes loading + passes inference test
2. ⏳ Proxy deployed at :8001, model-ID rewriting active
3. ⏳ OpenClaw reconfigured + restarted pointing at :8001
4. ⏳ SSH tunnel live → WebChat accessible at localhost:18789
5. ⬜ End-to-end test: send message → energy receipt appears in WebChat
6. ⬜ Carbon router polling Electricity Maps, model switch demo
7. ⬜ Demo run-through

---

## Key Config

| Item | Value |
|-|-|
| Clean grid model | `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` |
| Dirty grid model | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8` |
| Carbon threshold | 300 gCO₂/kWh |
| Electricity Maps API key | `~/.config/electricity_maps/api_key` (sandbox tier) |
| OpenClaw auth token | `~/.openclaw/openclaw.json` → `gateway.auth.token` |
| WebChat URL | `http://localhost:18789` (via SSH tunnel) |

---

## Useful Commands

```bash
# Check vLLM status
gpuctl exec gb10-hackathon "tail -20 /tmp/vllm-super-075.log"

# Check proxy status
gpuctl exec gb10-hackathon "tail -20 /tmp/ecoclaw-proxy.log"

# Check OpenClaw status
gpuctl exec gb10-hackathon "tail -20 /tmp/openclaw-gateway.log"

# Test vLLM directly
gpuctl exec gb10-hackathon "curl -s http://localhost:8000/v1/models"

# Test proxy
gpuctl exec gb10-hackathon "curl -s http://localhost:8001/v1/models"

# SSH tunnel for WebChat
ssh -N -L 18789:localhost:18789 nvidia@10.1.96.152

# Restart proxy
gpuctl exec gb10-hackathon "screen -S proxy -X quit; screen -dmS proxy bash -lc 'source ~/.profile && ml && cd ~/git/hackathon && python -m ecoclaw.main 2>&1 | tee /tmp/ecoclaw-proxy.log'"

# Restart OpenClaw
gpuctl exec gb10-hackathon "screen -S openclaw -X quit; screen -S openclaw -dm bash -c 'cd ~/git/openclaw && VLLM_API_KEY=none npx openclaw gateway --port 18789 --bind lan --force --verbose 2>&1 | tee /tmp/openclaw-gateway.log'"
```

---

## Key Docs

| Doc | What it contains |
|-|-|
| `CLAUDE.md` | Index of all docs |
| `docs/setup.md` | Install and startup guide |
| `docs/design/index.md` | Full HLD |
| `docs/design/energy-proxy.md` | Proxy architecture + SSE injection |
| `docs/design/carbon-router.md` | Carbon routing logic + config |
| `docs/design/openclaw.md` | OpenClaw integration details |
| `docs/reference/vllm.md` | vLLM working commands, NVFP4 backend matrix, gotchas |
| `docs/reference/openclaw.md` | Validated config, streaming architecture |
| `docs/reference/gb10-validated.md` | Hardware capabilities, NVML, sm_121 gap |
| `docs/reference/electricity-maps.md` | Carbon intensity API |
