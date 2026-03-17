# EcoClaw — Session Handoff

## What we're building

**EcoClaw** — an AI assistant that makes the energy cost of every conversation visible and adapts its behavior to real-time grid carbon intensity.

Built for the **NVIDIA GTC 2026 "Hack for Impact"** hackathon (March 17, 2026, San Jose). Target track: **Eco Impact**. Bonus prize: **Best Use of OpenClaw**.

**One-line pitch:** Local LLM inference on a GB10 desktop AI computer, powered by Nemotron, that shows you the real energy cost of every response and switches to a more efficient model when the California grid is running dirty.

**Repo:** `~/git/hackathon`

Start with `CLAUDE.md` — it links every doc.

---

## Hardware

**GB10 instance:** `gb10-hackathon` (HP ZGX Nano, 10.1.96.152)

```bash
gpuctl exec gb10-hackathon "<cmd>"
gpuctl sync gb10-hackathon ~/git/hackathon
```

- 128GB unified memory (119GiB usable), aarch64, CUDA 13.0 sm_121
- CUDA 13 / PyTorch 2.10 — sm_121 support gap (see below)
- SSH user: `nvidia`, passwordless sudo

---

## Architecture

```
Browser (laptop) ──► OpenClaw gateway (:18789)
                              │ vLLM provider, baseUrl=:8001
                              ▼
                      Energy proxy (:8001)       ◄── NVML (totalEnergyConsumption)
                              │ injects energy receipt into every SSE response
                              ▼
                         vLLM (:8000)
                              │
                              ▼
                    GB10 GPU (Nemotron model)

Carbon router (thread in proxy process)  ◄── Electricity Maps API (US-CAL-CISO)
     └──► polls every 10 min, switches vLLM model when carbon crosses threshold
```

---

## Component status

### vLLM — mostly validated

| Model | Quant | Status | Command |
|-|-|-|-|
| Nemotron-3-Nano-30B FP8 | FP8 | ✅ Validated | See `docs/reference/vllm.md` |
| Nemotron-3-Nano-30B NVFP4 | NVFP4+MARLIN | ✅ Validated | See `docs/reference/vllm.md` |
| Nemotron-3-Super-120B NVFP4 | NVFP4+MARLIN | ⏳ Testing | Started, not yet confirmed |

**Critical finding:** PyTorch 2.10 supports CUDA up to sm_120; GB10 is sm_121. NVFP4 CUTLASS kernels fail silently (NaN logits, empty responses). Fix: `VLLM_USE_FLASHINFER_MOE_FP4=0 VLLM_NVFP4_GEMM_BACKEND=marlin`. FP8 works natively without workaround.

**Preferred Nano model: FP8** (native kernels, no workaround). NVFP4+MARLIN also works if needed.

Both models downloaded at `~/.cache/huggingface/hub/`. FP8 Nano also downloaded.

### Energy proxy — written, not yet deployed cleanly

Python FastAPI service at `src/ecoclaw/`. Deployed to GB10 at `~/git/hackathon/` via `gpuctl sync`.

Key files:
- `src/ecoclaw/proxy.py` — FastAPI proxy, NVML measurement, SSE footer injection
- `src/ecoclaw/carbon_router.py` — Electricity Maps polling, model switching, hysteresis
- `src/ecoclaw/state.py` — shared in-memory + persisted state
- `src/ecoclaw/nvml.py` — NVML wrapper
- `src/ecoclaw/main.py` — entrypoint (proxy + router as threads)

**Bug fixed:** carbon router previously switched models immediately on startup. Fixed — first poll deferred, no switch until second poll.

**Deploy-agent ran an earlier version** (with the startup bug) and it killed vLLM by switching to Super 120B. That's why vLLM may be in an unexpected state on GB10. Sync the repo and restart proxy cleanly.

Dependencies installed in ml venv: `fastapi uvicorn httpx pyyaml pynvml`.

### OpenClaw — partially set up

- Repo: `~/git/openclaw` on GB10, Node v22.22.1, pnpm installed, `pnpm ui:build` done
- Workspace files deployed: `~/.openclaw/workspace/AGENTS.md`, `SOUL.md`
- Config deployed: `~/.openclaw/openclaw.json` (currently pointing at `:8000` direct, needs update to `:8001` proxy)
- Gateway starts successfully via screen session — **not confirmed working end-to-end with Nemotron**
- WebChat at `http://10.1.96.152:18789`

Config template in repo: `config/openclaw/openclaw.json` (updated, points at `:8001`)

**NemoClaw investigation in progress** — haven't decided yet whether to use NemoClaw (NVIDIA's OpenClaw layer for GB10/Nemotron) instead of raw OpenClaw. Playbook at https://github.com/NVIDIA/dgx-spark-playbooks/tree/main/nvidia/nemoclaw.

### Carbon router config

Not yet written to GB10. Router auto-creates `~/.ecoclaw/carbon-router.yaml` on first run with defaults (threshold 300 gCO₂/kWh, 10 min poll, hysteresis 20).

Electricity Maps API key: `~/.config/electricity_maps/api_key` (`UpuAetadx7a7TBYyMByj`, sandbox tier — ±30% randomized data, good enough for demo).

---

## What's done

- ✅ Full HLD and sub-design docs (energy proxy, carbon router, OpenClaw integration)
- ✅ All reference docs validated on real hardware (NVML, vLLM, OpenClaw, Electricity Maps)
- ✅ Source code written and reviewed (proxy, carbon router, state, NVML)
- ✅ OpenClaw config files (openclaw.json, AGENTS.md, SOUL.md)
- ✅ Setup guide (docs/setup.md) — most TBDs filled in
- ✅ Nano FP8 serving validated (model responds, reasoning parser works)
- ✅ OpenClaw gateway starts and serves WebChat UI
- ✅ Carbon router startup bug fixed

## What's open / next

**Critical path (must complete before end-to-end test):**
1. **Validate Super 120B NVFP4+MARLIN** — does it load? With what `--gpu-memory-utilization` and `--max-model-len`? Check vllm.md for in-progress findings.
2. **NemoClaw decision** — use NemoClaw or raw OpenClaw? Check the playbook, decide, and proceed accordingly.
3. **Deploy clean proxy** — `gpuctl sync gb10-hackathon ~/git/hackathon`, then start with fixed code.
4. **End-to-end test** — vLLM → proxy → OpenClaw → energy receipt in WebChat.

**After that:**
5. Update openclaw.json on GB10 to point at `:8001` (proxy), not `:8000`
6. Fill in Super 120B command in `docs/setup.md`
7. Write `chat.inject` WS client for real-time model switch notification (stretch)
8. Demo run-through + timing

**Active work items from previous session (now abandoned — pick up or redo):**
- Demo script: demo-writer agent was writing `docs/demo-script.md` — check if it finished
- Super 120B validation: vllm-expert was testing — check vllm.md for updates

---

## Key docs

| Doc | What it contains |
|-|-|
| `CLAUDE.md` | Index of all docs |
| `docs/setup.md` | Install and startup guide |
| `docs/design/index.md` | Full HLD |
| `docs/design/energy-proxy.md` | Proxy architecture + SSE injection strategy |
| `docs/design/carbon-router.md` | Carbon routing logic + config format |
| `docs/design/openclaw.md` | OpenClaw integration details |
| `docs/reference/vllm.md` | vLLM working commands, NVFP4 backend matrix, gotchas |
| `docs/reference/openclaw.md` | Validated config, streaming architecture, chat.inject |
| `docs/reference/gb10-validated.md` | Hardware capabilities, NVML support matrix, sm_121 gap |
| `docs/reference/electricity-maps.md` | API endpoint, response format, mock data ranges |

---

## Agent team to create

Spawn these on-demand as needed (not all upfront):

**vllm-expert** — owns all vLLM serving on GB10. Responsible for: validating Super 120B, documenting final serve commands, any model serving issues. Does NOT touch OpenClaw or Python code.

**openclaw-expert** — owns OpenClaw/NemoClaw setup. Responsible for: NemoClaw investigation, OpenClaw gateway configuration, AGENTS.md content, WebChat validation. Does NOT touch vLLM or Python code.

**python-dev** (new, wasn't in previous session) — owns the Python source in `src/ecoclaw/`. Responsible for: proxy bugs, carbon router logic, integration tests. Does NOT touch vLLM or OpenClaw config.

**Team lead (you)** — coordination, decisions, final integration test, demo prep. Direct GB10 GPU ops via Bash (not delegated). Signal teammates when their dependencies are ready (e.g. "vLLM is stable, proceed with OpenClaw test").

**Key coordination rule:** vllm-expert owns vLLM exclusively while testing. Other teammates must wait for a "vLLM ready" signal before running inference-dependent tests. Don't let multiple agents restart vLLM simultaneously.
