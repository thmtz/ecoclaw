# EcoClaw — Current Status

**Hackathon day: March 17, 2026** · NVIDIA GTC 2026 "Hack for Impact" · San Jose

**Repo:** `~/dev/hackathon` | **GB10:** `gb10-hackathon` (10.1.96.152) | **GitHub:** https://github.com/thmtz/ecoclaw

---

## MVP Status: ✅ ACHIEVED

WebChat works end-to-end. User sends message → Nemotron Nano responds → energy receipt appears with per-response energy, CO₂, and session totals. Carbon router adjusts GPU frequency based on grid carbon intensity.

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
    │ tracks cumulative session energy
    ▼
vLLM (:8000)  ←  Nemotron Nano 30B FP8, 32K context
    │
    ▼
GB10 GPU  ◄── nvidia-smi freq cap (carbon router)

Carbon router (thread in proxy)  ◄── Electricity Maps API / mock file
    └──► caps/uncaps GPU frequency when carbon thresholds crossed
    └──► chat.inject notification to WebChat on state change
```

---

## Component Status

| Component | Status | Notes |
|-|-|-|
| Nemotron Nano 30B FP8 | ✅ Serving | `:8000`, `--max-model-len 32768`, reasoning parser active |
| Energy proxy | ✅ Running | `:8001`, all fixes applied, session tracking |
| Carbon router | ✅ Running | Freq cap mode (not model switching) |
| OpenClaw gateway | ✅ Running | `:18789`, Nano FP8 default, clean workspace files |
| SSH tunnel | ✅ Active | `localhost:18789` → GB10 |
| WebChat | ✅ Working | Energy receipt + session totals confirmed in browser |
| chat.inject notifications | ✅ Fixed | Sync websocket-client, reads token from config |
| GPU freq cap (carbon) | ✅ Validated | Dirty grid → cap 300-1000 MHz, clean grid → uncap |

---

## What's Implemented

**Core stack:**
- ✅ vLLM Nano FP8 serving (32K context, native sm_121 FP8 kernels)
- ✅ Energy proxy: NVML delta measurement, SSE receipt injection
- ✅ Receipt format: energy + power + tok/J + CO₂ per response + session totals
- ✅ Carbon router: Electricity Maps API, mock carbon override, GPU freq cap
- ✅ Demo endpoints: `POST /demo/carbon/{value}` + `POST /demo/poll`
- ✅ Session tracking: `GET /session` + `POST /session/reset`

**Proxy hardening:**
- ✅ Strip unsupported OpenAI fields (store, tools, tool_choice, metadata, reasoning_effort)
- ✅ Clamp max_completion_tokens
- ✅ Strip content-length on modified requests
- ✅ Model-ID rewriting
- ✅ Receipt suppression: ≥10 token threshold + per-IP cooldown (10s)
- ✅ Smart unit scaling: µJ/mJ/J, µWh/mWh/Wh at 2 decimal places

**Carbon response (freq cap, not model switching):**
- ✅ Dirty grid (>300 gCO₂/kWh): `nvidia-smi -lgc 300,1000` (cap frequency)
- ✅ Clean grid (≤300 gCO₂/kWh): `nvidia-smi -rgc` (full frequency)
- ✅ chat.inject notification to WebChat on state change
- ✅ Hysteresis band (20 gCO₂/kWh) prevents flapping

**Decisions:**
- ❌ Dual-model port swap: Not feasible (Nano uses 110 of 119 GiB). Closed.
- ❌ Model switching via vLLM restart: Replaced by freq cap (instant, no downtime).

---

## Open Items (Beads)

| Bead | Priority | Description |
|-|-|-|
| hackathon-dly.4 | P1 | Validate freq-cap carbon switch end-to-end on device |
| hackathon-9x1.1 | P1 | Record demo video |
| hackathon-9x1.2 | P1 | Trigger carbon switch on camera |
| hackathon-9x1.3 | P1 | Submit video |
| hackathon-dly.2 | P2 | Validate Super 120B stable with 8192 context |
| hackathon-dly.3 | P3 | Full Nano→Super carbon switch demo end-to-end |

---

## Demo Control

```bash
# Set mock carbon (401 = dirty grid = green mode = freq cap active)
curl -X POST http://localhost:8001/demo/carbon/401
curl -X POST http://localhost:8001/demo/poll

# Trigger freq uncap (50 = clean grid = performance mode = full frequency)
curl -X POST http://localhost:8001/demo/carbon/50
curl -X POST http://localhost:8001/demo/poll

# Check session energy totals
curl http://localhost:8001/session

# Reset session
curl -X POST http://localhost:8001/session/reset
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
| Carbon threshold | 300 gCO₂/kWh (hysteresis ±20) |
| Freq cap (dirty grid) | 300-1000 MHz |
| Mock carbon file | `~/.ecoclaw/mock_carbon` |
| OpenClaw auth token | Auto-generated on first start, see `~/.openclaw/openclaw.json` |
| WebChat URL | `http://localhost:18789` (via SSH tunnel) |
