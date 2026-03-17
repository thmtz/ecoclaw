# EcoClaw — Demo Script (Video Submission)

1. Open `http://localhost:18789` — OpenClaw WebChat loaded, Nemotron Nano FP8 active
2. Type: `What is the carbon footprint of training GPT-4?`
3. Point out energy receipt at bottom of response (mJ, mWh, tok/J, grid gCO₂/kWh)
4. Type: `Hi` — show low energy for short response
5. Type: `Write a 500-word essay on the environmental impact of cryptocurrency mining` — show higher energy, lower tok/J
6. Trigger carbon spike (set fallback_carbon: 400 or bump threshold) — show model-switch notification in chat
7. Type: `Explain how solar panels work` — show Nano receipt vs earlier, emphasize efficiency delta
8. Close: "Real hardware energy measurement. Carbon-aware model routing. Runs local on GB10."
