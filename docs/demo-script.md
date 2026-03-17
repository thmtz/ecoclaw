# EcoClaw Demo

## Opening (read to camera, ~30s)

Every time you ask an AI a question, it burns energy. But you never see the cost.

EcoClaw fixes that. It runs a 30-billion-parameter Nemotron model locally on this GB10, and every response comes with a receipt showing the exact joules consumed, measured by a hardware counter on the chip itself. Not an estimate. It also calculates the CO₂ footprint using live data from the California power grid.

When the grid gets dirty, EcoClaw automatically throttles the GPU to cut energy use. When the grid cleans up, it restores full speed. The switch is instant, and the user sees the difference in real time.

Let me show you.

---

## Before recording
```bash
lsof -i :18789 | grep ssh || ssh -N -L 18789:localhost:18789 nvidia@10.1.96.152 &
gpuctl exec gb10-hackathon "rm -f ~/.ecoclaw/mock_carbon"
curl -X POST http://localhost:8001/demo/poll
```
Open http://localhost:18789, token: `439368c7ef3a54d50317db8d985c5b2829ab2e494ec24e26`

## Part 1 — Energy receipt (live grid)
- WebChat: `What is the carbon footprint of training GPT-4?` → point out receipt
- WebChat: `Hi` → show low energy
- WebChat: `Explain photosynthesis` → show higher energy

## Part 2 — Carbon spike → GPU throttle
```bash
curl -X POST http://localhost:8001/demo/carbon/450
curl -X POST http://localhost:8001/demo/poll
```
- WebChat: `How do solar panels work?` → receipt shows `throttled @ 1000 MHz`, ~3 tok/J

## Part 3 — Restore (optional)
```bash
curl -X POST http://localhost:8001/demo/carbon/50
curl -X POST http://localhost:8001/demo/poll
```
- WebChat: `What's 2+2?` → receipt shows `full speed @ 2398 MHz`

## Key numbers
- Full speed: ~40-60 J, ~1.3 tok/J, 2398 MHz
- Throttled: ~7-15 J, ~3 tok/J, 988 MHz → **54% energy savings**
