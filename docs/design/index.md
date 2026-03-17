# EcoClaw — High-Level Design

> **Name is tentative.**

An AI assistant that is aware of its own environmental impact and adapts its behavior to minimize it.

**Pitch:** Local LLM inference on GB10, powered by Nemotron, that shows you the real energy cost of every response and adjusts which model it uses based on live grid carbon intensity.

**Track:** Eco Impact | **Bonus target:** Best Use of OpenClaw | **Build window:** 6 hours

---

## Architecture

```
User
 │
 ▼
OpenClaw (WebChat UI + agent gateway)
 │  native vLLM provider
 ▼
Energy Proxy  ◄──── NVML (totalEnergyConsumption)
 │  wraps /v1/chat/completions, injects energy metadata
 ▼
vLLM (:8000)
 │  serves one Nemotron model at a time
 ▼
GB10 GPU (Nemotron Nano 30B FP8 or Super 120B NVFP4+MARLIN)

Carbon Router  ◄──── Electricity Maps API (US-CAL-CISO)
 │  polls grid carbon intensity, reads config thresholds
 └──► triggers model switch when thresholds crossed
```

---

## Components

### OpenClaw
Personal AI assistant gateway (Node.js, MIT). Provides the WebChat UI and connects to vLLM via its native vLLM provider. An **energy skill** teaches the agent to include the energy receipt in every response. Configuration via `~/.openclaw/openclaw.json`.

See: [../reference/vllm.md](../reference/vllm.md) for provider setup.

### vLLM
Serves one Nemotron model at a time on `:8000`. OpenAI-compatible API. Model switches require a restart (~2-5 min with warm cache). This is acceptable for hackathon — carbon routing is coarse-grained (switches happen at threshold crossings, not per-request).

### Nemotron models
| Model | Active params | Memory | tok/s (est) | Role |
|-|-|-|-|-|
| Nano 30B-A3B | 3B | ~15–60GB (FP8, native sm_121) | ~72 | High-carbon / green mode — **primary** |
| Super 120B-A12B | 12B | ~60–103GB (NVFP4+MARLIN) | ~15-17 | Low-carbon / performance mode — carbon router |

Both are MoE hybrid Mamba-Transformer. Cannot run simultaneously.

**Quantization:** Nano uses **FP8** — native sm_121 support on Blackwell, no workaround needed. Super uses **NVFP4 + MARLIN backend**: CUTLASS-based NVFP4 kernels cap at sm_120 (PyTorch 2.10 limitation), so we set `VLLM_USE_FLASHINFER_MOE_FP4=0 VLLM_NVFP4_GEMM_BACKEND=marlin`. MARLIN is a software fallback that runs on any SM — slightly slower than native hardware kernels but produces correct output. NVFP4+MARLIN remains the fallback path for Super if FP8 weights are unavailable.

See: [../reference/vllm.md](../reference/vllm.md).

### Energy proxy
Thin Python middleware between OpenClaw and vLLM. Snapshots `nvmlDeviceGetTotalEnergyConsumption` before and after each inference call. The delta is the exact energy consumed — no polling or averaging needed. Injects energy metadata (mJ, mWh, tok/J) into the response so the OpenClaw skill can surface it.

See [energy-proxy.md](energy-proxy.md).

### Carbon router
Polls Electricity Maps API (`GET /v3/carbon-intensity/latest?zone=US-CAL-CISO`) on a slow interval (e.g. every 10 min). Compares current carbon intensity against thresholds defined in a config file. When a threshold is crossed, triggers a model switch (restart vLLM with the appropriate model). Also surfaces current carbon + active mode in the OpenClaw UI via the energy skill.

Config is a simple YAML file: when `carbonIntensity > X`, use model Y. Hysteresis band prevents flapping. See [carbon-router.md](carbon-router.md) and [../reference/electricity-maps.md](../reference/electricity-maps.md). Fallback to mock data if no internet.

### NVML
`nvmlDeviceGetTotalEnergyConsumption` returns a hardware-integrated mJ counter. Diff before/after = exact energy for that request. Confirmed working on GB10. Power limit and memory reporting not available. See: [../reference/gb10-validated.md](../reference/gb10-validated.md).

### GPU clock control (optional)
`sudo nvidia-smi -lgc <min>,<max>` can cap SM frequency (range 300–3003 MHz). Validated on device. This gives a second energy lever beyond model selection — the carbon router could also apply a clock cap in green mode. TBD whether we include this in MVP.

---

## Energy receipt format

Appended to every OpenClaw response:

```
─────────────────────────────
⚡ Energy: 42 mJ · 0.012 mWh · 1,840 tok/J
🌱 Grid: 180 gCO₂/kWh (clean) · Nemotron Super 120B
─────────────────────────────
```

---

## Carbon routing config (MVP)

Simple config file (JSON or YAML). Example:

```yaml
thresholds:
  - carbon_gt: 300   # gCO2/kWh
    model: nano
    label: "green mode"
  - carbon_lte: 300
    model: super
    label: "performance mode"
poll_interval_seconds: 600
fallback_carbon: 250   # used if API unavailable
```

---

## What we are NOT building

- Per-request routing based on query complexity
- Custom chat UI (OpenClaw provides this)
- Simultaneous dual-model serving
- Any use of the Neuralwatt closed-source agent

---

## Stretch goals

If MVP is done early, in rough priority order:

**Energy-performance frontier profiling**
Sweep Nano and Super across different settings and measure tok/s vs mJ/token. Dimensions to vary: GPU clock cap (`nvidia-smi -lgc`), quantization level (NVFP4 vs FP8 vs BF16 if available), model size (Nano vs Super). Plot the Pareto frontier — quality/speed/energy tradeoffs made concrete with real numbers from our hardware. Good demo artifact and strong technical story for judges.

**Live power dashboard**
Real-time GPU power draw chart while the assistant is thinking. Shows the inference "heartbeat" — idle baseline → prefill spike → sustained decode → return to idle. Could be a sidebar panel in OpenClaw's WebChat or a standalone web page polling an SSE endpoint on the energy proxy.

**Cumulative session energy**
Track total energy consumed across an entire conversation. Running total in the UI with equivalences ("this session used as much energy as charging your phone for 45 seconds"). Resets per session.

**Side-by-side model comparison**
Run the same prompt through Nano and Super (sequentially), show both responses with their energy receipts. Makes the quality-vs-efficiency tradeoff tangible and interactive.

**NemoClaw integration**
Install NemoClaw on top of OpenClaw for enterprise-grade sandboxing and security. Targets the "Best Use of OpenClaw" bonus prize angle, makes the demo look more polished.

**Containerization**
Package the EcoClaw Python service (proxy + carbon router) as a Docker container with a `docker-compose.yml` for one-command deployment. vLLM and OpenClaw have their own packaging; this is just the EcoClaw layer. Makes the project easy to deploy on any GB10, and strengthens the open-source story for the hackathon submission.

---

## Open questions

- **Energy proxy streaming**: Resolved — footer must be injected as an extra content delta chunk **before** `[DONE]`, not after. OpenClaw reconstructs its own SSE stream from internal agent events; it does not passthrough raw SSE. Post-`[DONE]` chunks are never seen. See [energy-proxy.md](energy-proxy.md).
- **NVFP4 on GB10**: Resolved — MARLIN backend works. Final launch config (max-model-len, reasoning-parser flag) being finalized by vllm-expert. FP8 being evaluated as potential faster alternative.
- **Model switching UX**: Resolved — carbon router sends a system message before triggering the vLLM restart: "Switching to Nemotron Nano — high carbon on grid. Back in ~2 min."
- **Footer injection**: Resolved — proxy appends formatted footer directly to stream. AGENTS.md as belt-and-suspenders fallback. No plugin needed.
- **GPU clock capping**: Cut from MVP. Carbon router uses model selection only. Clock cap is a stretch goal.
