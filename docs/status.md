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
    │ demo endpoints: POST /demo/carbon/{value}, POST /demo/poll
    ▼
vLLM (:8000)
    │
    ▼
GB10 GPU (Nemotron Nano 30B FP8)

Carbon router (thread in proxy)  ◄── Electricity Maps API (US-CAL-CISO)
    │ polls every 10 min, switches vLLM model when carbon crosses threshold
    │ notifies active OpenClaw session via chat.inject before model switch
    └──► mock override: ~/.ecoclaw/mock_carbon
```

---

## MVP Status: ACHIEVED

Energy receipt confirmed visible in WebChat for every response. End-to-end working.

Carbon routing is implemented and functional — P2 for demo, will use demo endpoints for the model-switch moment.

---

## Component Status

| Component | Status | Notes |
|-|-|-|
| Nemotron Nano 30B FP8 | ✅ Running | `:8000`, primary model |
| Energy proxy | ✅ Running | `:8001`, all fixes deployed, demo endpoints live |
| Carbon router | ✅ Running | Live Electricity Maps data, chat.inject notification, mock file support |
| OpenClaw gateway | ✅ Running | `:18789`, Nano FP8 default, workspace files fixed |
| SSH tunnel | ✅ Active | `localhost:18789` → GB10 |
| WebChat | ✅ Working | End-to-end confirmed, energy receipt appearing |

---

## What's Done

- ✅ vLLM Nano 30B FP8 running (native sm_121, no MARLIN needed)
- ✅ Energy proxy: NVML measurement, SSE receipt injection, model-ID rewriting
- ✅ Proxy: Content-Length fix, field stripping (store/tools/tool_choice/metadata/reasoning_effort), max_completion_tokens clamp, unit normalization
- ✅ Proxy demo endpoints: `POST /demo/carbon/{value}`, `POST /demo/poll`
- ✅ Carbon router: live Electricity Maps data, FP8/NVFP4 per-model env + reasoning parsers, mock file support (`~/.ecoclaw/mock_carbon`), chat.inject notification before model switch
- ✅ OpenClaw workspace files fixed: IDENTITY.md, USER.md, BOOTSTRAP.md, TOOLS.md all replaced with static content
- ✅ WebChat end-to-end test: energy receipt confirmed working
- ✅ setup.md, demo-script.md, design docs up to date

---

## Open Items

| # | Item | Priority |
|-|-|-|
| 1 | tok/J showing 1 (bug) | High — fix before recording |
| 2 | "startup" mode label clears after first poll | Low — cosmetic, disappears on its own |
| 3 | Record demo video | Final step |

---

## Known Issues / Resolved

| Issue | Status | Fix |
|-|-|-|
| vLLM 400: `store` field | ✅ Fixed | Proxy strips `store`, `metadata`, `reasoning_effort` |
| vLLM 400: `tool_choice: auto` | ✅ Fixed | Proxy strips `tools`, `tool_choice` |
| vLLM 400: `max_completion_tokens` too large | ✅ Fixed | Proxy clamps to 2048 |
| Proxy Content-Length mismatch | ✅ Fixed | Strip `content-length` header on modified requests |
| Unit normalization in receipt | ✅ Fixed | Proxy normalizes mJ/mWh/tok/J before injection |
| Carbon router startup model switch bug | ✅ Fixed | First poll deferred |
| OpenClaw workspace files (dynamic agent content) | ✅ Fixed | IDENTITY/USER/BOOTSTRAP/TOOLS.md replaced with static content |
| tok/J showing 1 | 🐛 Open | Unit or rounding bug in proxy receipt calculation |
| "startup" mode label in receipt | ⚠️ Known | Clears after first carbon router poll (~10 min) |

---

## Useful Commands

```bash
# Check status of all components
gpuctl exec gb10-hackathon "curl -s http://localhost:8000/v1/models | python3 -c 'import sys,json;d=json.load(sys.stdin);print(\"vLLM:\",d[\"data\"][0][\"id\"][:40])' && curl -s http://localhost:8001/v1/models | python3 -c 'import sys,json;d=json.load(sys.stdin);print(\"proxy:\",d[\"data\"][0][\"id\"][:40])'"

# Check proxy log
gpuctl exec gb10-hackathon "tail -20 /tmp/ecoclaw-proxy.log"

# Check OpenClaw log
gpuctl exec gb10-hackathon "tail -10 /tmp/openclaw-gateway.log"

# SSH tunnel (restart if dead)
ssh -N -L 18789:localhost:18789 nvidia@10.1.96.152 &

# Trigger carbon spike for demo (sets mock carbon to 420 gCO₂/kWh and polls immediately)
gpuctl exec gb10-hackathon "curl -s -X POST http://localhost:8001/demo/carbon/420 && curl -s -X POST http://localhost:8001/demo/poll"

# Clear mock carbon (return to live API)
gpuctl exec gb10-hackathon "rm -f ~/.ecoclaw/mock_carbon && curl -s -X POST http://localhost:8001/demo/poll"

# Restart proxy
gpuctl exec gb10-hackathon "fuser -k 8001/tcp 2>/dev/null; sleep 2; screen -dmS proxy bash -lc 'source ~/.profile && ml && cd ~/dev/hackathon && PYTHONPATH=src python -m ecoclaw.main 2>&1 | tee /tmp/ecoclaw-proxy.log'"

# Restart OpenClaw
gpuctl exec gb10-hackathon "screen -S openclaw -X quit; sleep 1; screen -S openclaw -dm bash -c 'cd ~/git/openclaw && VLLM_API_KEY=none npx openclaw gateway --port 18789 --bind lan --force --verbose 2>&1 | tee /tmp/openclaw-gateway.log'"

# Restart Nano FP8
gpuctl exec gb10-hackathon "screen -S vllm -X quit; sleep 2; screen -dmS vllm bash -lc 'source ~/.profile && ml && vllm serve nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8 --trust-remote-code --max-model-len 4096 --gpu-memory-utilization 0.75 --reasoning-parser nano_v3 2>&1 | tee /tmp/vllm-nano.log'"
```

---

## Key Config

| Item | Value |
|-|-|
| Primary model | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8` (Nano FP8) |
| Fallback model | `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` (Super, carbon router) |
| Carbon threshold | 300 gCO₂/kWh |
| Mock carbon file | `~/.ecoclaw/mock_carbon` (write a number to override live API) |
| Electricity Maps API key | `~/.config/electricity_maps/api_key` |
| OpenClaw auth token | `439368c7ef3a54d50317db8d985c5b2829ab2e494ec24e26` |
| WebChat URL | `http://localhost:18789` (via SSH tunnel) |
