# EcoClaw — Current Status

**Hackathon day: March 17, 2026** · NVIDIA GTC 2026 "Hack for Impact" · San Jose

**Repo:** `~/dev/hackathon` | **GB10:** `gb10-hackathon` (10.1.96.152)

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
    │ strips unsupported fields (store, tools, tool_choice, etc.)
    │ clamps max_completion_tokens to 2048
    ▼
vLLM (:8000)
    │
    ▼
GB10 GPU (Nemotron Nano 30B FP8)

Carbon router (thread in proxy)  ◄── Electricity Maps API (US-CAL-CISO)
    └──► polls every 10 min, switches vLLM model when carbon crosses threshold
```

---

## MVP Scope

Energy receipt visible in WebChat for every response. That's the demo. Carbon routing is P2 — it's implemented and works, but not the focus of the judging demo.

---

## Component Status

| Component | Status | Notes |
|-|-|-|
| Nemotron Nano 30B FP8 | ⏳ Loading | vllm-expert switching from Super 120B; CUDA cache warm |
| Nemotron Super 120B NVFP4+MARLIN | 🔄 Swapping out | Being replaced by Nano FP8 as primary |
| Energy proxy | ✅ Running | `:8001`, all OpenAI compat fixes applied |
| Carbon router | ✅ Running | Implemented, P2 for demo |
| OpenClaw gateway | ✅ Running | `:18789`, reconfigured for Nano FP8, AGENTS.md trimmed |
| SSH tunnel | ✅ Active | `localhost:18789` → GB10 |
| WebChat | ⏳ Pending | Waiting on Nano FP8 to finish loading |

---

## What's Done

- ✅ vLLM Super 120B validated (NVFP4+MARLIN, 8.5 min startup, 200 OK inference)
- ✅ Energy proxy: NVML measurement, SSE receipt injection, model-ID rewriting
- ✅ Proxy: Content-Length fix, field stripping (store/tools/tool_choice/metadata/reasoning_effort), max_completion_tokens clamp
- ✅ Carbon router: live Electricity Maps data, FP8/NVFP4 per-model env + reasoning parsers
- ✅ OpenClaw: reconfigured → `:8001`, Nano FP8 as default, AGENTS.md trimmed
- ✅ Reasoning parser paths confirmed (Super: `super_v3`, Nano FP8: `nano_v3`)
- ✅ setup.md: GB10 paths fixed, SSH tunnel step added, Super 120B flags corrected
- ✅ demo-script.md: complete, recovery commands fixed

---

## Open Items

| # | Item | Owner | Priority |
|-|-|-|-|
| 1 | Nano FP8 finishes loading | vllm-expert ⏳ | **CRITICAL** |
| 2 | WebChat end-to-end test | You | After #1 |
| 3 | Demo run-through + timing | You | Final step |

---

## Known Issues / Resolved

| Issue | Status | Fix |
|-|-|-|
| vLLM 400: `store` field | ✅ Fixed | Proxy strips `store`, `metadata`, `reasoning_effort` |
| vLLM 400: `tool_choice: auto` | ✅ Fixed | Proxy strips `tools`, `tool_choice` |
| vLLM 400: `max_completion_tokens` too large | ✅ Fixed | Proxy clamps to 2048 |
| Proxy Content-Length mismatch | ✅ Fixed | Strip `content-length` header on modified requests |
| Carbon router startup model switch bug | ✅ Fixed | First poll deferred |
| AGENTS.md too long (>2000 tokens) | ✅ Fixed | Trimmed to <300 tokens |
| Super 120B missing reasoning parser | ✅ Fixed | `--reasoning-parser super_v3` in launch command |

---

## Useful Commands

```bash
# Check status of all components
gpuctl exec gb10-hackathon "curl -s http://localhost:8000/v1/models | python3 -c 'import sys,json;d=json.load(sys.stdin);print(\"vLLM:\",d[\"data\"][0][\"id\"][:40])' && curl -s http://localhost:8001/v1/models | python3 -c 'import sys,json;d=json.load(sys.stdin);print(\"proxy:\",d[\"data\"][0][\"id\"][:40])'"

# Check proxy log
gpuctl exec gb10-hackathon "tail -10 /tmp/ecoclaw-proxy.log"

# Check OpenClaw log
gpuctl exec gb10-hackathon "tail -10 /tmp/openclaw-gateway.log"

# SSH tunnel (restart if dead)
ssh -N -L 18789:localhost:18789 nvidia@10.1.96.152 &

# Restart proxy
gpuctl exec gb10-hackathon "fuser -k 8001/tcp 2>/dev/null; sleep 2; screen -dmS proxy bash -lc 'source ~/.profile && ml && cd ~/dev/hackathon && PYTHONPATH=src python -m ecoclaw.main 2>&1 | tee /tmp/ecoclaw-proxy.log'"

# Restart OpenClaw
gpuctl exec gb10-hackathon "screen -S openclaw -X quit; sleep 1; screen -S openclaw -dm bash -c 'cd ~/git/openclaw && VLLM_API_KEY=none npx openclaw gateway --port 18789 --bind lan --force --verbose 2>&1 | tee /tmp/openclaw-gateway.log'"

# Start Nano FP8
gpuctl exec gb10-hackathon "screen -S vllm -X quit; sleep 2; screen -dmS vllm bash -lc 'source ~/.profile && ml && vllm serve nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8 --trust-remote-code --max-model-len 4096 --gpu-memory-utilization 0.75 --reasoning-parser nano_v3 2>&1 | tee /tmp/vllm-nano.log'"
```

---

## Key Config

| Item | Value |
|-|-|
| Primary model | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8` (Nano FP8) |
| Fallback model | `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` (Super, carbon router) |
| Carbon threshold | 300 gCO₂/kWh |
| Electricity Maps API key | `~/.config/electricity_maps/api_key` |
| OpenClaw auth token | `439368c7ef3a54d50317db8d985c5b2829ab2e494ec24e26` |
| WebChat URL | `http://localhost:18789` (via SSH tunnel) |
