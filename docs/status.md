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
| Nemotron Super 120B NVFP4+MARLIN | ✅ Serving | `:8000`, `--gpu-memory-utilization 0.75`, no reasoning parser yet |
| Nemotron Nano 30B FP8 | ✅ Ready (not loaded) | Fallback model, CUDA cache warm |
| Energy proxy | ✅ Running | `:8001`, model-ID rewriting, Content-Length fix applied |
| Carbon router | ✅ Running | Thread in proxy, Electricity Maps live (52 gCO₂/kWh) |
| OpenClaw gateway | ✅ Running | `:18789`, Nemotron Super 120B as default, points at `:8001` |
| SSH tunnel | ✅ Active | `localhost:18789` → GB10, PID 72104 |
| WebChat end-to-end | ⏳ Fixing | vLLM returns 400 on OpenClaw requests (unsupported `store` field) — python-dev fixing |

---

## What's Done

- ✅ All design docs + reference docs validated on real hardware
- ✅ Source code: proxy, carbon router, state, NVML wrapper
- ✅ OpenClaw workspace files deployed (AGENTS.md, SOUL.md)
- ✅ Nano FP8 and Super 120B NVFP4+MARLIN both validated
- ✅ Carbon router bugs fixed (FP8 for nano, gpu_mem_util 0.75 for super, per-model env+parser)
- ✅ Proxy Content-Length fix (strips content-length/transfer-encoding on modified requests)
- ✅ Proxy model-ID rewriting (handles carbon router model switches transparently)
- ✅ Electricity Maps API key deployed, carbon router reading live data
- ✅ OpenClaw reconfigured → proxy `:8001`, Nemotron models
- ✅ SSH tunnel + WebUI HTTPS fix
- ✅ NemoClaw decision: use raw OpenClaw
- ✅ Reasoning parser paths validated (Super: `super_v3`, Nano FP8: `nano_v3`, paths confirmed)

---

## Open Items

| # | Item | Owner | Priority |
|-|-|-|-|
| 1 | Proxy: strip unsupported fields (`store` etc.) that cause vLLM 400s | python-dev ⏳ | **CRITICAL** |
| 2 | WebChat end-to-end test (blocked on #1) | team lead | **CRITICAL** |
| 3 | Restart Super 120B with `--reasoning-parser super_v3` | vllm-expert | High |
| 4 | Carbon router model switch demo (trigger + observe Nano switch) | team lead | High |
| 5 | setup.md: add SSH tunnel step | doc agent | Medium |
| 6 | Verify streaming tok/J calculation works end-to-end | python-dev | Medium |
| 7 | Demo run-through + timing | team lead | High |
| 8 | Demo script review/finalize | team lead | Medium |

---

## Known Issues

- **vLLM 400 on OpenClaw requests**: OpenClaw sends `store: true` (and possibly other OpenAI-specific fields) that vLLM rejects. Fix: proxy strips unknown fields before forwarding. python-dev working on this.
- **Super 120B no reasoning parser**: Current vLLM instance started without `--reasoning-parser super_v3`. Thinking traces will be absent until restart. Non-blocking for basic chat demo.
- **tok/J shows 0 in non-streaming mode**: token count not extracted correctly for non-streaming. OpenClaw uses streaming so may not matter in practice — needs verification.

---

## Active Agents

| Agent | Status | Task |
|-|-|-|
| python-dev | ⏳ Running | Strip unsupported fields from proxy request body |
| openclaw-expert | ⏳ Running | Diagnose WebChat failure, coordinate with python-dev |

---

## Useful Commands

```bash
# Check vLLM
gpuctl exec gb10-hackathon "tail -5 /tmp/vllm-super-075.log"
gpuctl exec gb10-hackathon "curl -s http://localhost:8000/v1/models"

# Check proxy
gpuctl exec gb10-hackathon "tail -10 /tmp/ecoclaw-proxy.log"
gpuctl exec gb10-hackathon "curl -s http://localhost:8001/v1/models"

# Check OpenClaw
gpuctl exec gb10-hackathon "tail -10 /tmp/openclaw-gateway.log"

# SSH tunnel (run locally if tunnel died)
ssh -N -L 18789:localhost:18789 nvidia@10.1.96.152 &

# Restart proxy
gpuctl exec gb10-hackathon "pkill -9 -f 'ecoclaw'; sleep 2; screen -dmS proxy bash -lc 'source ~/.profile && ml && cd ~/dev/hackathon && PYTHONPATH=src python -m ecoclaw.main 2>&1 | tee /tmp/ecoclaw-proxy.log'"

# Restart OpenClaw
gpuctl exec gb10-hackathon "screen -S openclaw -X quit; screen -S openclaw -dm bash -c 'cd ~/git/openclaw && VLLM_API_KEY=none npx openclaw gateway --port 18789 --bind lan --force --verbose 2>&1 | tee /tmp/openclaw-gateway.log'"

# Restart Super 120B WITH reasoning parser (do after end-to-end test passes)
gpuctl exec gb10-hackathon "screen -S vllm -X quit; sleep 2; screen -dmS vllm bash -lc 'source ~/.profile && ml && VLLM_USE_FLASHINFER_MOE_FP4=0 VLLM_NVFP4_GEMM_BACKEND=marlin vllm serve nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 --trust-remote-code --max-model-len 4096 --gpu-memory-utilization 0.75 --reasoning-parser super_v3 --reasoning-parser-plugin ~/.cache/huggingface/hub/models--nvidia--NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4/snapshots/167959da964ab08b30211f71e68f6670eaa87966/super_v3_reasoning_parser.py 2>&1 | tee /tmp/vllm-super.log'"
```

---

## Key Config

| Item | Value |
|-|-|
| Clean grid model | `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` |
| Dirty grid model | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8` |
| Carbon threshold | 300 gCO₂/kWh (current: 52 — clean) |
| Electricity Maps API key | `~/.config/electricity_maps/api_key` |
| OpenClaw auth token | `439368c7ef3a54d50317db8d985c5b2829ab2e494ec24e26` |
| WebChat URL | `http://localhost:18789` (via SSH tunnel) |
