# OpenClaw Reference

Version: 2026.3.14. Repo cloned on GB10 at `~/git/openclaw`.

## Injecting a footer into every response

**Answer: use `AGENTS.md` in the workspace, not a skill.**

Skills are loaded *on demand* — the agent reads a SKILL.md when it decides the skill is relevant. There is no guarantee a skill triggers on every response. Skills cannot unconditionally inject content.

The reliable mechanism is **workspace bootstrap files**, which are injected into the system prompt on *every* agent turn:

- `AGENTS.md` — procedural instructions, standard operating procedures
- `SOUL.md` — persona and tone
- `TOOLS.md` — tool usage instructions

By adding an instruction to `AGENTS.md` like "Always end every response with an energy receipt", the agent will follow it unconditionally. This is the simplest path.

Alternatively, a **Plugin** (TypeScript/JS runtime code) can intercept every response at the transport layer before it reaches the user — this is more reliable than prompt instructions but requires writing plugin code.

### Recommended approach for MVP

Put the instruction in `AGENTS.md`:

```markdown
## Energy Receipt

Always append the following block at the end of every response, using the
values returned by the energy proxy:

---
⚡ Energy: {mJ} mJ · {mWh} mWh · {tok_per_j} tok/J
🌱 Grid: {carbon} gCO₂/kWh · {mode} · {model}
---
```

The energy proxy injects these values as extra fields in the API response,
which an OpenClaw skill or AGENTS.md instruction can reference.

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

- How does the energy proxy inject per-response metadata that AGENTS.md can reference? The proxy returns standard OpenAI response format — we need a mechanism to surface energy fields to the agent.
- Does pointing OpenClaw at the energy proxy (`http://localhost:8001/v1`) work transparently, or does the vLLM provider hardcode `localhost:8000`? Check `baseUrl` override.
