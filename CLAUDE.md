# Hackathon - GB10

## Instance

- **gpuctl name:** `gb10-hackathon`
- **Hardware:** NVIDIA GB10 (Grace Blackwell), aarch64, 128GB unified memory
- **SSH user:** `nvidia` (not root)

## Remote access

Use `gpuctl` for all remote operations — not raw SSH.

```bash
gpuctl exec gb10-hackathon "<cmd>"
gpuctl ssh gb10-hackathon
gpuctl sync gb10-hackathon ~/git/hackathon
```

The instance was set up with `gpuctl prepare gb10-hackathon -m Qwen/Qwen2.5-0.5B-Instruct`. To re-prepare or change model, run prepare again with the new model name.

## Details

- **[Current status](docs/status.md) — start here for active session context**
- [README](README.md) — hackathon context, our angle, hardware specs
- [Brainstorm](docs/reference/brainstorm.md) — capabilities, ideas, open questions
- [Setup guide](docs/setup.md) — install, configure, and start everything (**keep this current**: any new install step, config file, API key, or env var needed to run the stack must be documented here)
- [Design](docs/design/index.md) — HLD, components, demo flow
  - [Energy proxy](docs/design/energy-proxy.md)
  - [Carbon router](docs/design/carbon-router.md)
  - [OpenClaw integration](docs/design/openclaw.md)

### Reference docs (validated findings, not design)

- [GB10 validated hardware](docs/reference/gb10-validated.md) — confirmed specs, NVML support matrix, what works/doesn't
- [GB10 setup & environment](docs/reference/gb10-setup.md) — connection details, installed software, gotchas
- [Electricity Maps API](docs/reference/electricity-maps.md) — carbon intensity API, endpoints, mock fallback
- [vLLM](docs/reference/vllm.md) — serving models, startup time, memory, gotchas
- [OpenClaw](docs/reference/openclaw.md) — integration guide, footer injection, vLLM provider config
- [DGX Spark Playbooks](docs/reference/dgx-spark-playbooks.md) — NVIDIA official playbooks for vLLM, Nemotron, NemoClaw, NVFP4 on GB10


<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:b9766037 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
