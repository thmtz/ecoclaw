# Energy Proxy — Sub-Design

Part of [EcoClaw design](design.md).

## Purpose

A thin middleware process between OpenClaw and vLLM that:
1. Measures the exact energy consumed per inference request via NVML
2. Appends a formatted energy receipt to every response before OpenClaw sees it

## Why a proxy (not a plugin or skill)

OpenClaw has no hook to post-process outgoing response text. `message:sent` fires after the send and is read-only. The only way to deterministically inject content into every response is either:
- **Proxy layer** — intercept and modify the stream before it reaches OpenClaw
- **LLM instruction** (AGENTS.md) — probabilistic, LLM can forget or truncate

The proxy is the only deterministic option. See [reference/openclaw.md](reference/openclaw.md).

## Placement

```
OpenClaw ──► energy proxy (:8001) ──► vLLM (:8000)
                    │
                    ├── snapshot NVML before forwarding
                    ├── forward request to vLLM
                    ├── collect response stream
                    ├── snapshot NVML after final token
                    └── append energy receipt to stream
```

OpenClaw is configured with `baseUrl: "http://localhost:8001/v1"` — it treats the proxy as the LLM endpoint. The proxy is transparent to OpenClaw.

## Energy measurement

```python
energy_before = nvmlDeviceGetTotalEnergyConsumption(handle)  # mJ
# ... forward request and collect response ...
energy_after = nvmlDeviceGetTotalEnergyConsumption(handle)   # mJ
delta_mj = energy_after - energy_before
delta_mwh = delta_mj / 3600
tok_per_j = total_tokens / (delta_mj / 1000)
```

No polling or averaging needed — the hardware counter integrates automatically. See [reference/gb10-validated.md](reference/gb10-validated.md).

## Receipt format (appended to stream)

```
\n─────────────────────────────
⚡ Energy: {delta_mj} mJ · {delta_mwh:.4f} mWh · {tok_per_j:.0f} tok/J
🌱 Grid: {carbon} gCO₂/kWh · {mode} · {model}
─────────────────────────────
```

The proxy reads current carbon intensity and active model from the carbon router's state (shared in-process or via a small IPC file).

## Open questions (delegate to openclaw-expert)

- **Streaming passthrough**: OpenClaw proxies SSE streams from vLLM to the WebChat UI. If the proxy appends an extra chunk after the `[DONE]` event, does OpenClaw pass it through cleanly? Or does it need to be injected into the last real content chunk before `[DONE]`?
- **Stream format**: Does the proxy need to append as a proper SSE `data:` chunk, or can it inject into the final content delta?

## Implementation approach (TBD)

Two options — to be decided once streaming question is answered:

**Option A: FastAPI + httpx streaming proxy (~80 LOC)**
Standalone Python process. Full control over stream manipulation. Easy to reason about. Requires managing a second process.

**Option B: vLLM middleware / OpenClaw plugin**
More integrated but more complex. Probably overkill for hackathon.

**Likely: Option A.** Simple, fast to build, easy to debug.

## Carbon router state access

The proxy needs to know the current carbon intensity and active mode to populate the receipt. Options:
- Shared state file (carbon router writes, proxy reads)
- In-process (run carbon router as a thread in the same Python process as the proxy)
- HTTP call to carbon router endpoint

For MVP: same Python process, shared in-memory state.
