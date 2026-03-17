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
    │ strips unsupported fields (store, tools, tool_choice, etc.)
    │ clamps max_completion_tokens to 2048
    ▼
vLLM (:8000)
    │
    ▼
GB10 GPU (Nemotron Super 120B)

Carbon router (thread in proxy)  ◄── Electricity Maps API (US-CAL-CISO)
    └──► polls every 10 min, switches vLLM model when carbon crosses threshold
```

---

## Component Status

| Component | Status | Notes |
|-|-|-|
| Nemotron Super 120B NVFP4+MARLIN | ✅ Serving | `:8000`, `--max-model-len 4096`, no reasoning parser yet |
| Nemotron Nano 30B FP8 | ✅ Ready (not loaded) | Fallback model, CUDA cache warm |
| Energy proxy | ✅ Running | `:8001`, all OpenAI compat fixes applied |
| Carbon router | ✅ Running | 52 gCO₂/kWh live from Electricity Maps |
| OpenClaw gateway | ✅ Running | `:18789`, Nemotron Super as default, points at `:8001` |
| SSH tunnel | ✅ Active | `localhost:18789` → GB10 |
| WebChat | ⏳ Fixing | AGENTS.md too long (>2000 tokens) — openclaw-expert trimming now |

---

## What's Done

- ✅ vLLM Super 120B validated (NVFP4+MARLIN, 8.5 min startup, 200 OK inference)
- ✅ Energy proxy: NVML measurement, SSE receipt injection, model-ID rewriting
- ✅ Proxy: Content-Length fix, field stripping (store/tools/tool_choice/metadata/reasoning_effort), max_completion_tokens clamp
- ✅ Carbon router: live Electricity Maps data, FP8/NVFP4 per-model env + reasoning parsers
- ✅ OpenClaw: reconfigured → `:8001`, Nemotron models, SSH tunnel
- ✅ Reasoning parser paths confirmed (Super: `super_v3`, Nano FP8: `nano_v3`)
- ✅ setup.md: GB10 paths fixed, SSH tunnel step added, Super 120B flags corrected
- ✅ demo-script.md: complete, recovery commands fixed

---

## Open Items

| # | Item | Owner | Priority |
|-|-|-|-|
| 1 | Trim AGENTS.md to <300 tokens | openclaw-expert ⏳ | **CRITICAL** |
| 2 | WebChat end-to-end test | You | After #1 |
| 3 | Restart Super 120B with `--reasoning-parser super_v3` | vllm-expert | High — after #2 |
| 4 | Carbon router model switch demo | team lead | High — after #2 |
| 5 | Demo run-through + timing | You | Final step |

---

## Known Issues / Resolved

| Issue | Status | Fix |
|-|-|-|
| vLLM 400: `store` field | ✅ Fixed | Proxy strips `store`, `metadata`, `reasoning_effort` |
| vLLM 400: `tool_choice: auto` | ✅ Fixed | Proxy strips `tools`, `tool_choice` |
| vLLM 400: `max_completion_tokens` too large | ✅ Fixed | Proxy clamps to 2048 |
| Proxy Content-Length mismatch | ✅ Fixed | Strip `content-length` header on modified requests |
| Carbon router startup model switch bug | ✅ Fixed | First poll deferred |
| AGENTS.md too long (>2000 tokens) | ⏳ In progress | openclaw-expert trimming to <300 tokens |
| Super 120B missing reasoning parser | ⏳ Pending | Restart after WebChat confirmed working |

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

# Restart Super 120B WITH reasoning parser (run after WebChat confirmed)
gpuctl exec gb10-hackathon "screen -S vllm -X quit; sleep 2; screen -dmS vllm bash -lc 'source ~/.profile && ml && VLLM_USE_FLASHINFER_MOE_FP4=0 VLLM_NVFP4_GEMM_BACKEND=marlin vllm serve nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 --trust-remote-code --max-model-len 4096 --gpu-memory-utilization 0.75 --reasoning-parser super_v3 --reasoning-parser-plugin ~/.cache/huggingface/hub/models--nvidia--NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4/snapshots/167959da964ab08b30211f71e68f6670eaa87966/super_v3_reasoning_parser.py 2>&1 | tee /tmp/vllm-super.log'"
```

---

## Key Config

| Item | Value |
|-|-|
| Clean grid model | `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` |
| Dirty grid model | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8` |
| Carbon threshold | 300 gCO₂/kWh (current: 52 — very clean) |
| Electricity Maps API key | `~/.config/electricity_maps/api_key` |
| OpenClaw auth token | `439368c7ef3a54d50317db8d985c5b2829ab2e494ec24e26` |
| WebChat URL | `http://localhost:18789` (via SSH tunnel) |
