# EcoClaw — Demo Script (Video Submission)

## Pre-demo setup (not on camera)
```bash
# Reset to clean state
curl -X POST http://localhost:8001/demo/carbon/401  # dirty grid = green mode
curl -X POST http://localhost:8001/demo/poll
# Verify: http://localhost:18789 loads, model shows "Nemotron Nano 30B"
```

## Recording flow

1. **Show WebChat** — `http://localhost:18789`, chat loaded, Nano FP8 active

2. **First message:** `What is the carbon footprint of training GPT-4?`
   - Point out energy receipt: `⚡ Energy · 🌱 Grid · gCO₂/kWh · CO₂ this response`
   - Say: "Real hardware measurement from the Blackwell GPU — not estimated."

3. **Short vs long:** Type `Hi` → show low energy. Then `Explain photosynthesis in detail` → show higher energy, different tok/J.

4. **Carbon trigger** (run in terminal, off-camera or narrate):
   ```bash
   curl -X POST http://localhost:8001/demo/carbon/50
   curl -X POST http://localhost:8001/demo/poll
   ```
   - Notification appears in chat: "switching models / throttling GPU"
   - Say: "Grid went clean — system adapts in real time."

5. **Close:** "Local inference. Real energy data. Carbon-aware. Runs on one GB10."

## Fallback (if model switch fails)
Skip step 4. Show steps 1–3 only — energy receipt is the core demo.

## Key numbers to highlight
- Energy per response: ~20–300 J depending on length
- Grid intensity: live from Electricity Maps (or mock)
- CO₂ per response: mgCO₂ range — tangible, human-scale
