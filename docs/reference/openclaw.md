# OpenClaw Reference

Version: 2026.3.14. Repo cloned on GB10 at `~/git/openclaw`.

## Injecting a footer into every response

**TL;DR: The energy proxy is the only truly deterministic option. AGENTS.md is the simplest. A Plugin `before_prompt_build` hook is the middle ground.**

### What doesn't work: SKILL.md

Skills are loaded *on demand* — the agent reads a SKILL.md when it decides the skill is relevant to the current request. There is no mechanism to load a skill unconditionally for every response. **Do not rely on SKILL.md for unconditional footer injection.**

### Option A: Energy proxy (deterministic — recommended)

The proxy sits between OpenClaw and vLLM. It can append the footer text directly to the last streaming chunk before OpenClaw ever sees it. This is **100% deterministic** — no LLM compliance required, no plugin code.

```
OpenClaw → energy proxy (:8001) → vLLM (:8000)
                ↑
         appends footer to final chunk
         using real NVML delta
```

Point OpenClaw's `baseUrl` at the proxy port instead of vLLM directly. The proxy handles the NVML delta and formats the footer before returning the response.

### Option B: AGENTS.md instruction (probabilistic — simplest)

`AGENTS.md` (and `SOUL.md`) are injected into the system prompt on every turn. An instruction here tells the LLM to append the footer.

```markdown
## Energy Receipt

Always append the following block at the end of every response, using the
values returned by the energy proxy:

---
⚡ Energy: {mJ} mJ · {mWh} mWh · {tok_per_j} tok/J
🌱 Grid: {carbon} gCO₂/kWh · {mode} · {model}
---
```

**Limitation:** The LLM may forget, truncate, or skip it — especially on long responses. Useful as a belt-and-suspenders fallback, not as the primary mechanism.

### Option C: Plugin `before_prompt_build` hook (reliable, requires TypeScript)

A plugin can register a `before_prompt_build` hook via `api.on(...)` that fires before every LLM call. It can inject into the system prompt via `appendSystemContext`:

```typescript
export default function register(api) {
  api.on("before_prompt_build", (event, ctx) => {
    return {
      appendSystemContext: "Always end your response with the energy receipt block."
    };
  });
}
```

More reliable than AGENTS.md alone (enforced every turn via plugin code), but still probabilistic — the LLM generates the actual footer text. Requires plugin development.

**Note:** Can be disabled by operators: `plugins.entries.<id>.hooks.allowPromptInjection: false`

### Hook limitations

No hook can post-process or modify the **outgoing response text**. Key events:

| Event | When | Modifies response? |
|-|-|-|
| `before_prompt_build` | Before LLM call | System prompt only |
| `message:sent` | After response sent | No (fires after send) |
| `message:received` | Inbound message | No |

There is no `message:before_send` or response transformer hook. The response text itself can only be modified at the proxy layer.

### Recommended MVP approach

| Layer | Role | Reliability |
|-|-|-|
| Energy proxy | Appends real footer with NVML data | Deterministic |
| AGENTS.md | Fallback instruction to LLM | Probabilistic |

Point OpenClaw at the energy proxy port. Proxy appends the footer. Optionally add an AGENTS.md instruction so the LLM knows the format context.

## Connecting OpenClaw to vLLM (validated)

Native vLLM provider — no custom plugin needed. **Explicit config required** (auto-discovery alone doesn't work — the `models` array with `id` and `name` is mandatory).

Validated `~/.openclaw/openclaw.json`:
```json
{
  "models": {
    "providers": {
      "vllm": {
        "baseUrl": "http://127.0.0.1:8000/v1",
        "apiKey": "none",
        "api": "openai-completions",
        "models": [
          {
            "id": "Qwen/Qwen2.5-0.5B-Instruct",
            "name": "Qwen 2.5 0.5B"
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "vllm/Qwen/Qwen2.5-0.5B-Instruct"
      },
      "memorySearch": {
        "enabled": false
      }
    }
  },
  "gateway": {
    "mode": "local",
    "http": {
      "endpoints": {
        "chatCompletions": {
          "enabled": true
        }
      }
    }
  }
}
```

**Config gotchas discovered:**
- `models` array is required — config validation rejects the provider without it
- Each model entry needs both `id` and `name` fields
- `gateway.mode` must be set to `"local"` — gateway refuses to start without it
- `memorySearch.enabled: false` — no embedding provider available on GB10
- Gateway auto-generates `gateway.auth.token` on first start and writes it back to the config file
- Model IDs are prefixed with `vllm/` when referenced in `agents.defaults.model.primary`

When switching to the energy proxy, change `baseUrl` to `"http://127.0.0.1:8001/v1"`.

Config template (without auto-generated fields) is tracked at `hackathon/config/openclaw/openclaw.json`.

## Skill system

Skills are `SKILL.md` files in:
1. `<workspace>/skills/` (highest precedence)
2. `~/.openclaw/skills/`
3. Bundled skills

Each skill has YAML frontmatter with `name` and `description`. The agent reads the skill body only when it decides the skill is relevant — **not on every turn**. Use for tool integrations, workflows, domain knowledge. Not suitable for unconditional behavior.

## Workspace bootstrap files

Injected into the system prompt on every turn (keep concise — they consume tokens):
- `AGENTS.md` — instructions and SOPs
- `SOUL.md` — persona
- `TOOLS.md` — tool guidance
- `MEMORY.md` — persistent memory (grows over time, watch size)
- `USER.md`, `IDENTITY.md`, `HEARTBEAT.md`

## Starting OpenClaw (validated)

```bash
# Prerequisites (already satisfied on GB10)
# Node.js v22.22.1, pnpm 10.32.1

# Install (already have repo at ~/git/openclaw)
cd ~/git/openclaw && pnpm install

# Build WebChat UI (required for browser access)
pnpm ui:build

# Start gateway in screen session
screen -S openclaw -dm bash -c 'cd ~/git/openclaw && VLLM_API_KEY=none npx openclaw gateway --port 18789 --verbose 2>&1 | tee /tmp/openclaw-gateway.log'

# WebChat UI: http://localhost:18789
# Gateway auth token: check ~/.openclaw/openclaw.json → gateway.auth.token
```

**Startup notes:**
- Do NOT use `openclaw onboard` — it's interactive and overwrites config. Deploy config files manually.
- `VLLM_API_KEY=none` is required as env var (OpenClaw checks for it even though local vLLM has no auth)
- Gateway auto-generates auth token on first start if not present
- WebChat UI requires `pnpm ui:build` — without it, the gateway serves the API but the browser UI shows "Missing Control UI assets"
- Gateway logs to `/tmp/openclaw/openclaw-<date>.log` and stdout

**Workspace files deployed to GB10:**
- `~/.openclaw/workspace/AGENTS.md` — EcoClaw persona, energy receipt context
- `~/.openclaw/workspace/SOUL.md` — one-line persona
- Templates tracked at `hackathon/config/openclaw/`

## Streaming architecture (important for energy proxy)

OpenClaw does **not** transparently proxy SSE streams from the LLM provider. The pipeline:

1. `streamSimple` (from `@mariozechner/pi-ai`) sends request to provider, receives `text_delta` events.
2. Pi-embedded-runner emits internal `AgentEvent`s (`stream: "assistant"`, `data: { delta, text }`).
3. Gateway's `openai-http.ts` subscribes to agent events and **reconstructs its own SSE stream** via `writeAssistantContentChunk()`.
4. On lifecycle `phase: "end"`, gateway writes `data: [DONE]\n\n` and closes the response.

Key files:
- `src/gateway/openai-http.ts` — SSE reconstruction, `writeDone`, `writeAssistantContentChunk`
- `src/gateway/http-common.ts` — `setSseHeaders`, `writeDone`
- `src/agents/pi-embedded-subscribe.ts` — text_delta handling, agent event emission
- `src/agents/agent-command.ts` — ACP text_delta → emitAgentEvent
- `src/agents/pi-embedded-runner/openai-stream-wrappers.ts` — payload patching (no content filtering)

**Implications for energy proxy:** Content from SSE chunks passes through unfiltered. The proxy must inject the footer as an extra content delta chunk **before** `[DONE]`, not after. See [energy proxy design](../design/energy-proxy.md).

## Gateway `chat.inject` — push messages into active sessions

The gateway exposes a `chat.inject` WebSocket RPC method that appends an assistant message into an active session and broadcasts it to all connected WebChat clients immediately.

**Schema:**
```json
{
  "type": "req",
  "id": "unique-id",
  "method": "chat.inject",
  "params": {
    "sessionKey": "main",
    "message": "⚠️ Switching to Nemotron Nano — grid carbon is high. Back in ~2 min.",
    "label": "EcoClaw"
  }
}
```

**Details:**
- Requires `operator.admin` scope (in the `ADMIN_SCOPE` group in `method-scopes.ts`)
- WebSocket-only — no HTTP endpoint. Caller must connect via WS and complete the `connect` handshake with admin auth first.
- Appends to the session transcript via `SessionManager.appendMessage()` (preserves parentId chain)
- Broadcasts a `chat` event with `state: "final"` to all connected clients — WebChat renders it immediately
- The message is tagged as `model: "gateway-injected"`, `provider: "openclaw"` so it's distinguishable from real LLM output
- Optional `label` field adds a prefix like `[EcoClaw]\n\n` to the message text

**Key source files:**
- `src/gateway/server-methods/chat.ts:1504` — `chat.inject` handler
- `src/gateway/server-methods/chat-transcript-inject.ts` — `appendInjectedAssistantMessageToTranscript`
- `src/gateway/protocol/schema/logs-chat.ts:57` — `ChatInjectParamsSchema`

**For carbon router use:** The carbon router can open a WebSocket connection to the gateway (localhost:18789), authenticate, and call `chat.inject` to notify the user of model switches. This avoids waiting until the next user message.

**Simpler MVP fallback:** If WS auth is too complex for hackathon, the carbon router can write a status file that the energy proxy reads and includes in the next response footer (e.g., "⚠️ Model switch in progress..."). Less immediate but zero integration complexity.

## Open questions for EcoClaw

- Does pointing OpenClaw at the energy proxy (`http://localhost:8001/v1`) work transparently? Almost certainly yes — vLLM provider uses the configured `baseUrl`. Set `baseUrl` in explicit config to override the default `localhost:8000`.
- AGENTS.md cannot reference dynamic proxy data — it's static text loaded at session start. The proxy must append the formatted footer (with actual NVML numbers) directly to the response stream.
