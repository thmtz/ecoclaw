# Carbon Router — Sub-Design

Part of [EcoClaw design](index.md).

## Purpose

A background process that monitors real-time grid carbon intensity and switches the active Nemotron model when thresholds are crossed. Makes EcoClaw's inference adaptive to real-world environmental conditions.

## Data source

Electricity Maps API, CAISO zone (San Jose / California grid).

```
GET https://api.electricitymaps.com/v3/carbon-intensity/latest?zone=US-CAL-CISO
Header: auth-token: <token>
```

Returns `carbonIntensity` in gCO₂eq/kWh. Updates hourly. Free tier returns sandbox data (±30% randomization) — fine for demo.

API key: `~/.config/electricity_maps/api_key`

See [../reference/electricity-maps.md](../reference/electricity-maps.md). Mock fallback if API unavailable: use `fallback_carbon` from config (default 250 gCO₂/kWh).

## Config file

Simple YAML at a well-known path (e.g. `~/.ecoclaw/carbon-router.yaml`):

```yaml
thresholds:
  - carbon_gt: 300       # gCO2/kWh — above this, use green mode
    model: nano
    label: "green mode"
  - carbon_lte: 300      # at or below this, use performance mode
    model: super
    label: "performance mode"

poll_interval_seconds: 600   # 10 min — Electricity Maps updates hourly, no need to poll faster
fallback_carbon: 250         # used when API is unavailable
hysteresis: 20               # don't switch if within ±20 gCO2 of threshold (prevents flapping)
```

## Behavior

On startup: read config, fetch current carbon, determine initial model, start vLLM with that model.

Poll loop:
1. Fetch carbon intensity (with fallback on failure)
2. Compare to threshold + hysteresis band
3. If model should change: trigger switch sequence
4. Sleep `poll_interval_seconds`

## Model switch sequence

When a threshold crossing is detected:

1. **Notify user** — send a system message via OpenClaw's gateway API (or write to a shared IPC file the proxy reads and injects): `"Switching to Nemotron [Nano/Super] — grid carbon is [X] gCO₂/kWh ([mode]). Back in ~2 min."`
2. **Stop vLLM** — `screen -S vllm -X quit`
3. **Start vLLM** with the new model and the MARLIN env vars
4. **Wait for readiness** — poll `GET localhost:8000/v1/models` until it responds
5. **Update shared state** — write current model + carbon to a state file the energy proxy reads for the receipt

## Shared state

The carbon router maintains a small state file (e.g. `~/.ecoclaw/state.json`) read by the energy proxy to populate the receipt:

```json
{
  "carbon_gco2": 185,
  "mode": "performance mode",
  "model": "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4",
  "model_short": "Nemotron Super 120B",
  "updated_at": "2026-03-17T14:30:00Z"
}
```

## Open question: notifying OpenClaw

How does the carbon router send a system message to the active OpenClaw chat session? Options:

- **OpenClaw gateway API** — OpenClaw exposes a REST/WebSocket gateway at `:18789`. May support injecting a system message. openclaw-expert to investigate.
- **Proxy injection** — the energy proxy detects model change (via state file diff) and injects the notification into the next response stream. Simple but delayed until the next user message.
- **For MVP**: proxy injection is acceptable — user will see the notice on their next response.

## Startup model determination

On first start, router reads state file. If no state file, fetches current carbon and picks model accordingly. If API unavailable, defaults to Nano (conservative — uses less energy).

## Running

Runs as a Python background process alongside the energy proxy. For MVP: same Python process, shared in-memory state with the proxy. The proxy imports the router's state directly.

```bash
# Start everything
python ecoclaw.py  # starts proxy on :8001 + carbon router thread
```
