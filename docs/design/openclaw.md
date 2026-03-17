# OpenClaw Integration — Sub-Design

Part of [EcoClaw design](index.md).

## Purpose

OpenClaw provides the WebChat UI and agent gateway. EcoClaw configures it to talk to the energy proxy (not vLLM directly) and deploys workspace files that give the agent context about energy receipts.

## Architecture

```
Browser (laptop) ──► OpenClaw gateway (:18789)
                              │  vLLM provider, baseUrl=:8001
                              ▼
                      Energy proxy (:8001)
                              │
                              ▼
                         vLLM (:8000)
```

OpenClaw is unaware of the energy proxy — it just treats `:8001` as its LLM endpoint.

## Config

`~/.openclaw/openclaw.json` (template at `config/openclaw/openclaw.json`):

Key fields:
- `models.providers.vllm.baseUrl` — points at proxy port `:8001`, not vLLM `:8000`
- `models.providers.vllm.models` — explicit model list required (auto-discovery not sufficient)
- `agents.defaults.model.primary` — `vllm/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8` (Nano is default)
- `agents.defaults.memorySearch.enabled: false` — no embedding provider on GB10
- `gateway.mode: "local"` — required or gateway refuses to start

**Gotcha:** Do NOT run `openclaw onboard` — it's interactive and overwrites config. Deploy config files manually.

## Workspace files

Deployed to `~/.openclaw/workspace/` (templates at `config/openclaw-workspace/`):

**`AGENTS.md`** — injected into system prompt every turn. Tells the agent:
- It's running on GB10 with local Nemotron inference
- The energy receipt format (for reference — proxy appends the real data)
- To be direct and concise (receipts are more impactful with focused answers)

**`SOUL.md`** — persona: clear, direct, technically precise. Not preachy.

## Energy receipt injection

The proxy appends the formatted receipt to every response. OpenClaw passes it through unmodified — no plugin needed.

For the footer to appear the right way, the proxy injects it as a content delta chunk immediately before `data: [DONE]` in the SSE stream. OpenClaw's `streamSimple` processes it as a normal text_delta and it renders in the WebChat UI.

See [energy-proxy.md](energy-proxy.md) for implementation details.

## Model switching notification

When the carbon router triggers a model switch, it needs to notify the user. Two approaches:

**MVP (implemented):** Carbon router writes a status note to the shared state file. Energy proxy includes it in the next response footer.

**Better (stretch):** Carbon router calls `chat.inject` via WebSocket to push an immediate assistant message into the active session. Requires WebSocket client with `operator.admin` auth. See `docs/reference/openclaw.md` for the full schema.

## Starting OpenClaw

```bash
# Build WebChat UI (one-time, required for browser access)
cd ~/git/openclaw && pnpm ui:build

# Deploy config
cp ~/git/hackathon/config/openclaw/openclaw.json ~/.openclaw/openclaw.json
mkdir -p ~/.openclaw/workspace
cp ~/git/hackathon/config/openclaw-workspace/AGENTS.md ~/.openclaw/workspace/
cp ~/git/hackathon/config/openclaw-workspace/SOUL.md ~/.openclaw/workspace/

# Start gateway
screen -dmS openclaw bash -lc 'cd ~/git/openclaw && VLLM_API_KEY=none npx openclaw gateway --port 18789 --verbose 2>&1 | tee /tmp/openclaw.log'
```

WebChat accessible at `http://10.1.96.152:18789` (GB10's LAN IP).

## Validated gotchas

- `VLLM_API_KEY=none` env var required — OpenClaw checks for it even though local vLLM has no auth
- `pnpm ui:build` required — without it, browser shows "Missing Control UI assets"
- Gateway auto-generates `gateway.auth.token` on first start and writes it to openclaw.json
- `gateway.mode: "local"` must be set — gateway refuses to start without it
- Model IDs prefixed with `vllm/` in `agents.defaults.model.primary`

See `docs/reference/openclaw.md` for full reference.
