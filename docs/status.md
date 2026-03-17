# EcoClaw — Current Status

**Hackathon day: March 17, 2026** · NVIDIA GTC 2026 "Hack for Impact" · San Jose

**Repo:** `~/dev/hackathon` | **GB10:** `gb10-hackathon` (10.1.96.152)

---

## MVP Status: ✅ ACHIEVED

WebChat works end-to-end. User sends message → Nemotron Nano responds → energy receipt appears. Carbon stub lets us control grid intensity on demand for the video demo.

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
    │ strips unsupported fields, clamps max_completion_tokens
    │ injects energy receipt (>=10 tokens threshold)
    ▼
vLLM (:8000)  ←  Nemotron Nano 30B FP8, 32K context
    │
    ▼
GB10 GPU

Carbon router (thread in proxy)  ◄── Electricity Maps API / mock file
    └──► polls every 10s, chat.inject notification before model switch
```

---

## Component Status

| Component | Status | Notes |
|-|-|-|
| Nemotron Nano 30B FP8 | ✅ Serving | `:8000`, `--max-model-len 32768`, reasoning parser active |
| Energy proxy | ✅ Running | `:8001`, all fixes applied |
| Carbon router | ✅ Running | Mock carbon at 401 gCO₂/kWh · green mode |
| OpenClaw gateway | ✅ Running | `:18789`, Nano FP8 default, clean workspace files |
| SSH tunnel | ✅ Active | `localhost:18789` → GB10 |
| WebChat | ✅ Working | Energy receipt confirmed in browser |
| Carbon-based model switching | ⚠️ NOT VALIDATED | chat.inject + vLLM restart unverified end-to-end |

---

## What's Implemented

**Core stack:**
- ✅ vLLM Nano FP8 serving (32K context, native sm_121 FP8 kernels)
- ✅ Energy proxy: NVML delta measurement, SSE receipt injection
- ✅ Receipt format: `⚡ Energy: X J · Y mWh · Z tok/J` + `🌱 Grid: gCO₂/kWh · mode · model`
- ✅ Carbon router: live Electricity Maps API, mock carbon override, chat.inject notification
- ✅ Demo endpoints: `POST /demo/carbon/{value}` + `POST /demo/poll`

**Proxy hardening:**
- ✅ Strip unsupported OpenAI fields (store, tools, tool_choice, metadata, reasoning_effort)
- ✅ Clamp max_completion_tokens
- ✅ Strip content-length on modified requests
- ✅ Model-ID rewriting
- ✅ Only inject receipt for responses ≥10 tokens (suppresses pre-call duplicates)
- ✅ Smart unit scaling: µJ/mJ/J, µWh/mWh/Wh at 2 decimal places
- ✅ 1-decimal tok/J display

**OpenClaw:**
- ✅ Workspace files cleaned (no template leakage)
- ✅ native/nativeSkills disabled

---

## Open Items (Beads)

| Bead | Priority | Description |
|-|-|-|
| hackathon-9x1.1 | P1 | Record demo video |
| hackathon-9x1.2 | P1 | Trigger carbon switch on camera |
| hackathon-9x1.3 | P1 | Submit video |
| hackathon-pxn.1 | P1 | Verify double-receipt fix in WebChat |
| hackathon-dly | **P1** | Carbon switching validation (epic) — NOT YET VALIDATED |
| hackathon-pxn.2 | P2 | FR: CO2 grams calculation in receipt |

---

## Demo Control

```bash
# Set mock carbon (401 = dirty grid = green mode = stays on Nano)
curl -X POST http://localhost:8001/demo/carbon/401
curl -X POST http://localhost:8001/demo/poll

# Trigger model switch (50 = clean grid = would switch to Super)
curl -X POST http://localhost:8001/demo/carbon/50
curl -X POST http://localhost:8001/demo/poll
```

## Useful Commands

```bash
# Check all components
gpuctl exec gb10-hackathon "curl -s http://localhost:8000/v1/models | python3 -c 'import sys,json;d=json.load(sys.stdin);print(\"vLLM:\",d[\"data\"][0][\"id\"][:40])'"
gpuctl exec gb10-hackathon "tail -5 /tmp/ecoclaw-proxy.log"

# SSH tunnel (restart if dead)
ssh -N -L 18789:localhost:18789 nvidia@10.1.96.152 &

# Restart proxy
gpuctl exec gb10-hackathon "fuser -k 8001/tcp 2>/dev/null; sleep 2; screen -dmS proxy bash -lc 'source ~/.profile && ml && cd ~/dev/hackathon && PYTHONPATH=src python -m ecoclaw.main 2>&1 | tee /tmp/ecoclaw-proxy.log'"

# Test receipt directly (non-streaming)
gpuctl exec gb10-hackathon "curl -s http://localhost:8001/v1/chat/completions -H 'Content-Type: application/json' -d '{\"model\":\"nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":30,\"stream\":false}' | python3 -c 'import sys,json;print(json.load(sys.stdin)[\"choices\"][0][\"message\"][\"content\"])'"
```

## Key Config

| Item | Value |
|-|-|
| Nano FP8 model | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8` |
| Super 120B model | `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` |
| Carbon threshold | 300 gCO₂/kWh |
| Mock carbon file | `~/.ecoclaw/mock_carbon` |
| OpenClaw auth token | `439368c7ef3a54d50317db8d985c5b2829ab2e494ec24e26` |
| WebChat URL | `http://localhost:18789` (via SSH tunnel) |
