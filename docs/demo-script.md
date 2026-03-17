# EcoClaw — Demo Script

Live demo guide for NVIDIA GTC 2026 "Hack for Impact" judging (Eco Impact track).

**Demo surface:** OpenClaw WebChat UI at `http://10.1.96.152:18789` from a laptop browser.

---

## Pitch (60 seconds)

> Every AI response costs energy. GPT-4 uses roughly 10x the electricity of a Google search, but users never see that cost — it's invisible. We think that's a problem, because you can't optimize what you can't measure.
>
> EcoClaw is an AI assistant that knows exactly how much energy each response consumed. It reads a hardware energy counter on the GB10's Blackwell GPU — before and after every inference call — and prints a receipt showing millijoules, milliwatt-hours, and tokens per joule. No estimation, no modeling — real measured energy from NVML.
>
> But measurement alone isn't enough. EcoClaw also acts on it. It pulls live carbon intensity from the California grid via Electricity Maps. When the grid is dirty — lots of gas peakers online — it automatically switches to Nemotron Nano, a 3B-active-parameter model that's 4x more energy efficient. When the grid is clean, it switches back to Nemotron Super 120B for full capability. The model adapts to the carbon state of the world in real time.
>
> Everything runs locally on this GB10. Open source. No cloud dependency. Energy-aware AI inference you can hold in your hands.

---

## Demo flow (5 minutes)

### Step 1 — First impression (30 sec)

**Do:** Open the browser tab with OpenClaw already loaded. The chat should be empty or have a greeting.

**Type:** `What is the carbon footprint of training GPT-4?`

**Say:** "Let's start with a simple question. Watch the bottom of the response."

**Judge sees:** A well-formed answer from Nemotron Super 120B, followed by the energy receipt:

```
─────────────────────────────
⚡ Energy: 42 mJ · 0.0117 mWh · 1,840 tok/J
🌱 Grid: 180 gCO₂/kWh (clean) · performance mode · Nemotron Super 120B
─────────────────────────────
```

**Say:** "42 millijoules. That's the actual energy this response consumed on the GPU, measured by the hardware — not estimated, not sampled. And you can see the grid right now is relatively clean at 180 grams CO₂ per kilowatt-hour, so we're running the full 120-billion-parameter model."

### Step 2 — Show efficiency varies with complexity (1 min)

**Type:** `Hi`

**Judge sees:** Short response with a much lower energy number (e.g. 8 mJ) and a higher tok/J ratio.

**Say:** "Simple responses are cheap. 8 millijoules — barely measurable. The tok/J metric tells you how efficiently the GPU converted energy into useful output."

**Type:** `Write a 500-word essay on the environmental impact of cryptocurrency mining`

**Judge sees:** Longer response, higher energy (e.g. 180–250 mJ), lower tok/J.

**Say:** "Longer, harder responses cost more. This is the kind of transparency that lets developers and users make informed decisions about how they use AI."

### Step 3 — Trigger the carbon router (2 min) [wow moment]

**Do:** Before the demo, prepare the ability to simulate a carbon spike. Options:
- Set `fallback_carbon: 400` in config and temporarily kill API access, OR
- Use a mock endpoint that returns high carbon, OR
- Manually bump the threshold in the config to trigger a switch

**Say:** "Now let's see what happens when the grid gets dirty. California's carbon intensity just spiked — imagine a heat wave, everyone running AC, gas plants ramping up."

**Judge sees:** A notification appears in the chat:

> Switching to Nemotron Nano — grid carbon is 420 gCO₂/kWh (high). Back in ~2 min.

**Say:** "The system detected the carbon spike and is switching to Nemotron Nano — a 3-billion active parameter model that's roughly 4x more efficient per token. The tradeoff is capability, but for most conversational tasks, Nano is perfectly good."

**Do:** Wait for vLLM to restart (~2 min). Fill the time with talking points (see below). If judges are engaged, answer questions. If not, explain the architecture.

**Type (once Nano is ready):** `Explain how solar panels work`

**Judge sees:** Good answer from Nano with a much lower energy receipt:

```
─────────────────────────────
⚡ Energy: 12 mJ · 0.0033 mWh · 7,200 tok/J
🌱 Grid: 420 gCO₂/kWh (high carbon) · green mode · Nemotron Nano 30B
─────────────────────────────
```

**Say:** "12 millijoules versus 42 for a similar-length response. 7,200 tokens per joule versus 1,800. Same hardware, same quality answer for this question — but a quarter of the energy, exactly when it matters most."

### Step 4 — The big picture (30 sec)

**Say:** "Scale this up. A data center running thousands of GPUs, switching model tiers based on grid carbon — that's meaningful emissions reduction with zero loss of availability. The user always gets a response; the system just picks the most responsible way to generate it. And because we're measuring real energy at the hardware level, not estimating from TDP or model size, the numbers are trustworthy."

### Step 5 — Close (30 sec)

**Say:** "Everything you saw runs on this single GB10. Open source — the proxy is 80 lines of Python, the carbon router is another 100. The energy measurement is one NVML call. This isn't a research prototype — it's a pattern any inference provider could adopt today."

---

## Talking points (for Q&A)

### How do you measure energy?

`nvmlDeviceGetTotalEnergyConsumption` returns a monotonically increasing millijoule counter integrated by the GPU hardware. We snapshot before and after each inference request. The delta is exact energy consumed — not estimated from power draw × time, not averaged across the system. This is the same counter DCGM and nvidia-smi use internally.

### Why not CodeCarbon / MLCo2 / other estimation tools?

Those tools estimate energy from CPU/GPU utilization percentages and TDP ratings. They don't measure actual energy. On a shared system or with variable workloads, estimates can be off by 2-5x. NVML gives us the real number from hardware.

### Why local inference instead of cloud API?

Three reasons: (1) we can access NVML — cloud APIs don't expose per-request energy, (2) the hackathon requires running on the GB10, (3) local inference means the full stack is auditable and reproducible.

### Why two models instead of one?

Nemotron Nano (3B active params via MoE) is roughly 4x faster and 4x more energy-efficient per token than Super (12B active). For many tasks the quality difference is negligible. Carbon-aware routing exploits this: use the big model when the grid is clean (energy is low-carbon anyway), use the small model when the grid is dirty (minimize carbon per response).

### Can they run simultaneously?

No. Both models at NVFP4 quantization require significant memory. The GB10 has 128GB unified memory shared between CPU and GPU. We run one at a time and switch via vLLM restart (~2 min with warm Hugging Face cache).

### What about the 2-minute switch time?

It's a hackathon — we're demonstrating the concept, not optimizing cold-start latency. In production you'd use speculative decoding, model sharding across multiple GPUs, or pre-loaded model slots to make switches near-instant. The routing logic itself is the contribution.

### What's the NVFP4/MARLIN thing?

GB10 is sm_121 (Blackwell). The default CUTLASS-based FP4 kernels in vLLM cap at sm_120 due to a PyTorch limitation. We use the MARLIN backend — a software fallback that works on any SM. Slightly slower than native hardware kernels but produces correct output. Set via `VLLM_NVFP4_GEMM_BACKEND=marlin`.

### How does Neuralwatt relate to this?

Neuralwatt is our company — we build production GPU energy optimization tools. EcoClaw is a from-scratch open-source demo that shows the concept applied to inference. It doesn't use any Neuralwatt proprietary code. Think of it as our thesis statement: AI should know its own energy cost.

---

## What could go wrong

| Failure | Symptom | Recovery |
|-|-|-|
| vLLM OOM or crash | OpenClaw shows connection error | SSH in (`gpuctl ssh gb10-hackathon`), restart vLLM manually with the working launch command. ~2 min. |
| vLLM slow to start after model switch | Chat hangs during carbon router switch | Talk through the architecture diagram while waiting. If >3 min, check logs: `gpuctl exec gb10-hackathon "screen -S vllm -X hardcopy /tmp/vllm.log && cat /tmp/vllm.log"` |
| Energy proxy crash | Responses come through without receipts | Restart: `gpuctl exec gb10-hackathon "cd ~/dev/hackathon && PYTHONPATH=src python -m ecoclaw.main &"`. OpenClaw still works — it just hits vLLM directly without energy data. |
| Electricity Maps API down | Carbon router uses fallback value | This is by design. Mention it: "We use a configurable fallback when the API is unavailable — for the demo we can also simulate carbon spikes." |
| Carbon router doesn't trigger switch | No model change visible | Manually trigger: edit config to lower threshold, or use the mock endpoint. Have the command ready in a terminal tab. |
| OpenClaw UI unresponsive | Blank page or WebSocket errors | Refresh browser. If that fails: `gpuctl exec gb10-hackathon "screen -S openclaw -X quit && cd ~/git/openclaw && node dist/index.js &"` |
| Network to GB10 down | Can't reach `10.1.96.152` | Check wifi. The GB10 is on the local event network. Have a hotspot as backup. Worst case: show the architecture slides and recorded demo video (pre-record a 2-min walkthrough as insurance). |
| NVML counter returns 0 / stale value | Receipt shows 0 mJ | Known edge case if GPU was recently reset. Run a warmup query before the demo to prime the counter. |

### Pre-demo checklist

- [ ] vLLM running and serving (test: `curl http://10.1.96.152:8000/v1/models`)
- [ ] Energy proxy running on :8001
- [ ] OpenClaw UI loads at `http://10.1.96.152:18789`
- [ ] Send a test message and verify energy receipt appears
- [ ] Carbon router running and has current grid data
- [ ] Model switch mechanism tested (trigger and recover at least once)
- [ ] Fallback/mock carbon spike ready in a terminal tab
- [ ] Browser bookmarked, font size readable from 6 feet away
- [ ] Pre-record backup video on phone, just in case
