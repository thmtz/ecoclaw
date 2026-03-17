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

- [README](README.md) — hackathon context, our angle, hardware specs
- [Brainstorm](docs/reference/brainstorm.md) — capabilities, ideas, open questions
- [Setup guide](docs/setup.md) — install, configure, and start everything
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
