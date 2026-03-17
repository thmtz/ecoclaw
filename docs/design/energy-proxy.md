# Energy Proxy — Sub-Design

Part of [EcoClaw design](index.md).

## Purpose

A thin middleware process between OpenClaw and vLLM that:
1. Measures the exact energy consumed per inference request via NVML
2. Appends a formatted energy receipt to every response before OpenClaw sees it

## Why a proxy (not a plugin or skill)

OpenClaw has no hook to post-process outgoing response text. `message:sent` fires after the send and is read-only. The only way to deterministically inject content into every response is either:
- **Proxy layer** — intercept and modify the stream before it reaches OpenClaw
- **LLM instruction** (AGENTS.md) — probabilistic, LLM can forget or truncate

The proxy is the only deterministic option. See [../reference/openclaw.md](../reference/openclaw.md).

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

No polling or averaging needed — the hardware counter integrates automatically. See [reference/gb10-validated.md](../reference/gb10-validated.md).

## Receipt format (appended to stream)

```
\n─────────────────────────────
⚡ Energy: {delta_mj} mJ · {delta_mwh:.4f} mWh · {tok_per_j:.0f} tok/J
🌱 Grid: {carbon} gCO₂/kWh · {mode} · {model}
─────────────────────────────
```

The proxy reads current carbon intensity and active model from the carbon router's state (shared in-process or via a small IPC file).

## Streaming injection strategy (resolved)

**Answer: Inject the footer into the last content chunk before `[DONE]`. Appending after `[DONE]` will NOT work.**

### Why post-`[DONE]` injection fails

OpenClaw does **not** transparently proxy SSE streams from the LLM provider. The streaming pipeline is:

1. OpenClaw's `streamSimple` (from `@mariozechner/pi-ai`) sends the request to vLLM and receives `text_delta` events internally.
2. The pi-embedded-runner processes these deltas and emits internal `AgentEvent`s with `stream: "assistant"` and `data: { delta, text }`.
3. The gateway's `openai-http.ts` listens for these agent events and **reconstructs its own SSE stream** via `writeAssistantContentChunk()` — it does not relay vLLM's raw SSE chunks.
4. When a lifecycle `phase: "end"` event fires, the gateway writes `data: [DONE]\n\n` and calls `res.end()`.

The `[DONE]` is written by OpenClaw's gateway, not forwarded from vLLM. Anything the proxy appends after vLLM's `[DONE]` never reaches the gateway's SSE output — OpenClaw has already consumed the stream and closed it.

### Correct approach: inject into the SSE stream before `[DONE]`

The energy proxy intercepts the SSE stream from vLLM. It must:

1. **Buffer the stream** and watch for `data: [DONE]`.
2. **Before** forwarding `[DONE]` to OpenClaw, emit an extra `data:` chunk containing the energy receipt as a content delta:
   ```
   data: {"choices":[{"index":0,"delta":{"content":"\n─────────────────────────────\n⚡ Energy: 42 mJ · 0.012 mWh · 1,840 tok/J\n🌱 Grid: 180 gCO₂/kWh (clean) · Nemotron Super 120B\n─────────────────────────────"},"finish_reason":null}]}
   ```
3. Then forward the `data: [DONE]` event.

OpenClaw's `streamSimple` will process this extra chunk as a normal `text_delta`, which flows through the agent event system and into the gateway's reconstructed SSE stream. The footer appears as the last part of the assistant's response text.

### Does OpenClaw filter or transform SSE chunks?

No content filtering. The `streamSimple` function processes each SSE chunk as a `text_delta` and passes the text through. The gateway reconstructs chunks from the `delta` field of agent events. The text content itself is not filtered, truncated, or transformed. Unicode (⚡, 🌱), box-drawing characters (─), and newlines all pass through cleanly.

### Non-streaming requests

For `stream: false` requests, OpenClaw calls vLLM without streaming and reads the full response JSON. The proxy can simply append the footer to the `choices[0].message.content` field in the response body before returning it to OpenClaw.

## Implementation approach

Streaming question is resolved — **Option A is confirmed**:

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
