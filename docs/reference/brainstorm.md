# Hackathon Brainstorm

## What we have

- **GB10 (HP ZGX Nano)** — 128GB unified LPDDR5X (119Gi usable), 48 SM Blackwell GPU (6144 CUDA cores), 140W TDP, 3.6TB NVMe
- **NVML power telemetry** — `power.draw` and `totalEnergyConsumption` (cumulative mJ counter) confirmed working. Memory reporting broken (unified mem). Power cap not exposed. No tegrastats. See [validated hardware report](reference/gb10-validated.md).
- **vLLM 0.17.1** serving on `:8000`, PyTorch 2.10, CUDA 13.0
- **OpenClaw 2026.3.14** cloned at `~/git/openclaw` — personal AI assistant gateway with native vLLM provider, skill/plugin system, WebChat UI. See [vLLM provider docs](https://docs.openclaw.ai/providers/vllm).
- **NemoClaw** (NVIDIA) — enterprise security/privacy layer on top of OpenClaw, routes inference through local NVIDIA hardware. Announced at GTC 2026. [GitHub](https://github.com/NVIDIA/NemoClaw).
- **Neuralwatt inference API** — hosted API with per-request energy metrics (mWh/req, tok/J). Fair game as external service (closed-source agent cannot be used directly).

## Models (Nemotron only)

| Model | Params (active) | Quant | Memory | tok/s (est) | Status |
|-|-|-|-|-|-|
| Nemotron-3 Nano 30B-A3B | 30B (3B) | NVFP4 | ~15GB | ~72 | downloading |
| Nemotron-3 Super 120B-A12B | 120B (12B) | NVFP4 | ~103GB | ~15-17 | downloading |

Both are MoE (Mixture of Experts) with hybrid Mamba-Transformer architecture. Strategy: Nemotron-only. Two models gives us a small/large pair for profiling and routing experiments.

## Idea bank

### 1. Energy receipts per conversation turn
Instrument each inference call with NVML energy snapshots (diff `totalEnergyConsumption` before/after). Show per-response cost in the chat UI: mJ, mWh, tok/J. "Every AI conversation has a hidden energy cost — we made it visible."

**Why it works:** Simple to build, visually compelling, directly hits Eco Impact. Nobody has a user-facing per-query energy display in a chat app today. Existing tools (CodeCarbon, CarbonTracker, Zeus/ML.ENERGY, TokenPowerBench) are all batch/research tools — none are real-time, user-facing, or integrated into a chat UX.

### 2. Model intelligence vs energy efficiency profiling
Run Nano and Super on identical prompts. Measure and visualize the tradeoff: Super is smarter but costs X mJ more per response. Show quality-per-joule, not just raw quality.

**Why it works:** Concrete, data-driven. Judges can see actual numbers. Could produce a "Nemotron efficiency leaderboard" as a demo artifact.

### 3. Energy-aware model routing
Switch between Nano and Super based on:
- Task complexity (simple Q&A → Nano, reasoning/code → Super)
- User-set energy budget ("I want answers under 50mJ each")
- Real-time carbon intensity of the local grid (WattTime API, Electricity Maps)

The deep research doc calls this the "GreenClaw Eco-Router" — route to the most energy-efficient path per task. Could also route between local GB10 and Neuralwatt cloud API based on which is more efficient for a given query.

**Why it works:** Ambitious, tells a great story. But needs careful scoping for 6 hours.

### 4. Live power dashboard
Real-time GPU power draw visualization while the assistant is thinking. Shows the "heartbeat" of inference — idle baseline → spike during prefill → sustained draw during decode → return to idle. Could be a sidebar in the OpenClaw WebChat UI or a standalone web page.

**Why it works:** Visually dramatic. Makes the invisible visible. Pairs well with energy receipts.

### 5. Energy receipt comparison (local vs cloud)
Run the same prompt through local GB10 inference AND through the Neuralwatt hosted API. Show side-by-side energy costs. The pitch: "Here's what your question costs on a desktop GPU vs in the cloud."

**Why it works:** Directly relevant to Neuralwatt's business. Shows the value of edge inference for energy efficiency.

### 6. Cumulative session energy tracking
Track total energy consumed across an entire conversation session. Show running totals, averages, and equivalences ("This conversation used as much energy as charging your phone for 30 seconds"). Reset per session.

**Why it works:** Narrative device. Makes cumulative cost tangible. Easy to build on top of per-turn receipts.

### 7. OpenClaw energy skill
Create an OpenClaw skill that the agent can invoke to report its own energy consumption. The agent becomes self-aware of its energy cost and can comment on it, suggest more efficient approaches, or warn when a task will be expensive.

**Why it works:** Targets the "Best Use of OpenClaw" bonus prize directly. Natural integration point via skill system.

### 8. Quantization as an energy dimension
Model quantization (FP16 → FP8 → NVFP4 → INT4) is another knob that trades quality for efficiency. We could profile the same model at different quantization levels and show energy:performance tradeoffs. Combined with model size and clock frequency, this gives three independent dimensions to explore. Just an idea — may be too many variables for a 6-hour hackathon, but worth noting as future work or stretch goal.

### 9. Carbon-intensity-aware inference envelope
Use [Electricity Maps](https://www.electricitymaps.com/) free tier to fetch real-time carbon intensity for the local grid (San Jose / CAISO). Use this as a routing/throttling layer that adapts how OpenClaw serves requests:

- **Low carbon intensity (clean grid):** Use Super 120B at full clocks. Max quality, higher energy ok.
- **High carbon intensity (dirty grid):** Downshift to Nano 30B, or apply conservative frequency/power caps. Trade quality for carbon efficiency.
- **User-configurable envelope:** Let the user set their own carbon sensitivity — "always green", "balanced", "performance first". The system adapts model selection and power profile accordingly.
- **UI indication:** OpenClaw shows which model/mode is active and why. "Currently using Nemotron Nano (grid carbon: 420 gCO2/kWh — efficiency mode)."

This makes the routing *reactive to the real world* — not just a static benchmark but a living system that responds to grid conditions. Compelling Eco Impact story.

**Validated control levers:**
- **Model switching** — Nano vs Super (confirmed both downloading)
- **GPU clock capping** — `sudo nvidia-smi -lgc 300,1500` works! Confirmed. Range: 300–3003 MHz. This directly controls power draw without switching models.
- **Power limit** — not supported on this SKU. Can't use `-pl`.

So the envelope has two real knobs: model selection and clock frequency. Both are validated.

**Electricity Maps API (validated):**
- Endpoint: `GET https://api.electricitymaps.com/v3/carbon-intensity/latest?zone=US-CAL-CISO`
- Auth: `auth-token: <token>` header. Free tier requires signup at `app.electricitymaps.com`.
- Returns: `{"zone":"US-CAL-CISO","carbonIntensity":123,...}` — gCO2eq/kWh
- Near real-time, hourly default (configurable to 5min)
- Also has `/history` (last 24h) and `/forecast` endpoints
- Alternative: WattTime (covers CAISO, free tier for basic signal, requires signup)
- co2signal.com is dead (522 error)

**Mock fallback (if no internet at hackathon):**
California (CAISO) realistic gCO2/kWh ranges following the duck curve:
- Midday solar: 80–150 (clean)
- Afternoon: 200–300
- Evening peak (gas ramp): 350–450 (dirty)
- Overnight: 250–350

**Remaining open questions for this idea:**
- What's the actual tok/s and tok/J impact of clock capping? Need to benchmark (e.g. 1500 MHz vs 3003 MHz).
- Free tier rate limits — unknown, need to test once we have an API key.



These are ideas from the AI-generated architecture doc. Some are overengineered for a 6-hour hackathon but contain useful kernels:

- **OpenTelemetry integration** — OpenClaw has a `diagnostics-otel` plugin that exports `openclaw.tokens` and `openclaw.run.duration_ms` metrics. Could correlate token counts with energy measurements for precise tok/J calculation.
- **NemoClaw sandboxing** — Deploy via NemoClaw to demonstrate secure agent execution. Targets the OpenClaw bonus prize and looks polished for judges.
- **Eco-routing with Neuralwatt API as decision signal** — Use the Neuralwatt API's tok/J metrics as a routing signal to choose between local and cloud inference paths.
- **Complexity estimation pre-routing** — Have the agent estimate prompt complexity before deciding which model to use. The doc suggests a "complexity evaluator" tool.
- **Carbon intensity integration** — Query real-time grid carbon data to factor into routing decisions. Nice story but may not be feasible if no internet access at the event.

## Constraints

- Everything we build must be open source
- NW agent is closed source — cannot use directly. NW inference API is fine.
- At least part of the solution must use the GB10 for local inference
- 6-hour build window — scope ruthlessly
- Must work as a live demo (not just slides/screenshots)

## Reference docs (take with a grain of salt)

AI-generated research dumps — useful as rough idea sources but likely contain hallucinations and unverified claims. Don't treat as ground truth; validate anything before building on it.

- [Deep research report (ChatGPT)](deep-research-report-chatgpt.md) — NVML quirks, OpenClaw overview, model perf numbers, competitive landscape
- [Architecture plan (ChatGPT)](Hackathon%20AI%20Energy%20Optimization%20Plan.md) — verbose design doc, "GreenClaw Eco-Router" concept, phased implementation plan

**Known hallucinations from these docs:**
- Claims tegrastats works on GB10 — **it does not** (not installed, not available)
- Claims NVML power reporting is unreliable/shows 5W static — **incorrect**, power.draw works fine on our device
- Claims DCGM monitoring works — **it does not** (discovery only, dmon fails)
- Overestimates complexity of energy measurement — the `totalEnergyConsumption` counter is trivially easy to use

## Open questions

- Does NemoClaw add anything we need, or is raw OpenClaw + vLLM sufficient?
- Can we get carbon intensity data for the San Jose grid in real time? (WattTime API, Electricity Maps)
- What's the judging criteria weighting? Demo polish vs technical depth vs impact story?
- Is there internet access at the hackathon for external APIs (Neuralwatt, carbon data)?
- How does OpenClaw's skill system handle injecting structured metadata (energy stats) into chat responses?
- Can we serve both Nano and Super simultaneously on the GB10, or do we need to swap? (Super uses ~103GB of 119GB available — probably can't run both)
- What's the actual tok/s for Super on our specific device? Need to benchmark once downloaded.
