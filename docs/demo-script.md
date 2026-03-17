# EcoClaw Demo

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
