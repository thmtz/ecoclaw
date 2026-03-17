# Hack for Impact: The Open Source AI Challenge

**NVIDIA GTC 2026 Hackathon — San Jose, March 17, 2026 (11am–6pm PT)**

[Event page](https://luma.com/gtc-hack-for-impact)

## Event

6-hour in-person hackathon at GTC 2026. Three tracks: **Human Impact**, **Eco Impact**, **Culture Impact**. Prizes are physical GB10 workstations (one per track winner, sponsored by Dell/HP/Lenovo). Bonus prize for **Best Use of OpenClaw** (details revealed at event start).

Hardware provided: GB10 systems (Dell Pro Max, HP ZGX Nano, Lenovo ThinkStation PGX) running open models (Nemotron, Cosmos). All entries eligible for Developer Showcase.

## Our angle

**Team:** Neuralwatt — AI infrastructure startup. Our core product is a userspace agent that uses Q-learning to optimize GPU power states via NVML, maximizing tokens-per-joule for LLM inference. We offer a hosted inference API with real-time energy observability metrics (mWh/request, tok/J, normalized Wh/req).

**Target track:** Eco Impact

**Idea:** Energy-aware AI assistant — instrument local LLM inference on GB10 with per-response energy receipts, making the hidden energy cost of AI conversations visible to users. Built on OpenClaw + local vLLM + NVML power telemetry.

## Constraints

- **Everything we build must be open source.** The Neuralwatt agent and tooling are closed source and cannot be used directly. The Neuralwatt hosted inference API (which returns energy metrics per request) is fair game as an external service.
- **Local inference on the GB10 is required.** At least part of the solution must run models locally on the GB10 hardware — that's the whole point of the hackathon.

## Hardware

We have a pre-provisioned GB10 accessible via `gpuctl`:

- **SoC:** NVIDIA GB10 Grace Blackwell (TSMC 3nm, 2.5D packaging)
- **GPU:** 48 SMs, ~RTX 5070 class Blackwell die
- **CPU:** MediaTek 20-core ARM v9.2 (big/little)
- **Memory:** 128GB unified LPDDR5X (~273–301 GB/s)
- **Interconnect:** NVLink C2C at 600 GB/s between CPU and GPU dies
- **TDP:** 140W SoC
- **OS:** DGX Base OS (Ubuntu-based), CUDA 13.0, Driver 580.x
- **Software:** vLLM 0.17.1, PyTorch 2.10, DCGM 3.3.9, pynvml

See [docs/gb10-setup.md](docs/gb10-setup.md) for full environment details.

## Key references

- [GB10 setup & environment](docs/reference/gb10-setup.md) — install details, power telemetry, gotchas
- [Research notes (ChatGPT)](docs/deep-research-report-chatgpt.md) — NVML support, OpenClaw, models, competitive landscape
- [Architecture plan](docs/Hackathon%20AI%20Energy%20Optimization%20Plan.md) — detailed design doc
