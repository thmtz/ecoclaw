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

## Connecting OpenClaw to vLLM

Native vLLM provider — no custom plugin needed.

```bash
export VLLM_API_KEY="anything"   # any value; no auth on local vLLM
```

Config in `~/.openclaw/openclaw.json`:
```json5
{
  agents: {
    defaults: {
      model: { primary: "vllm/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8" }
    }
  }
}
```

Auto-discovers models from `GET http://127.0.0.1:8000/v1/models`. Model IDs are prefixed with `vllm/`.

Explicit config (if auto-discovery doesn't work):
```json5
{
  models: {
    providers: {
      vllm: {
        baseUrl: "http://127.0.0.1:8000/v1",
        apiKey: "anything",
        api: "openai-completions",
        models: [{ id: "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8", ... }]
      }
    }
  }
}
```

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

## Starting OpenClaw

```bash
# Install (already have repo at ~/git/openclaw)
cd ~/git/openclaw && pnpm install

# Onboard (sets up gateway, workspace, model config)
openclaw onboard --install-daemon

# Start gateway manually
openclaw gateway --port 18789 --verbose

# Web UI available at http://localhost:18789
```

## Open questions for EcoClaw

- Does pointing OpenClaw at the energy proxy (`http://localhost:8001/v1`) work transparently? Almost certainly yes — vLLM provider uses the configured `baseUrl`. Set `baseUrl` in explicit config to override the default `localhost:8000`.
- AGENTS.md cannot reference dynamic proxy data — it's static text loaded at session start. The proxy must append the formatted footer (with actual NVML numbers) directly to the response stream.
