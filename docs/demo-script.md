# EcoClaw — Demo Script

**Goal:** Show energy receipt on every response, then trigger GPU throttle via carbon spike.

---

## Pre-demo (run before recording, not on camera)

```bash
# 1. Ensure SSH tunnel is live
lsof -i :18789 | grep ssh || ssh -N -L 18789:localhost:18789 nvidia@10.1.96.152 &

# 2. Verify stack is up
gpuctl exec gb10-hackathon "curl -s http://localhost:8000/v1/models | python3 -c 'import sys,json;print(json.load(sys.stdin)[\"data\"][0][\"id\"][:40])'"
gpuctl exec gb10-hackathon "curl -s http://localhost:8001/v1/models | head -c 80"

# 3. Show REAL grid data first (no mock)
gpuctl exec gb10-hackathon "rm -f ~/.ecoclaw/mock_carbon"
curl -X POST http://localhost:8001/demo/poll   # picks up live Electricity Maps data

# 4. Open http://localhost:18789 in browser, connect with token:
#    439368c7ef3a54d50317db8d985c5b2829ab2e494ec24e26
#    Start a fresh session
```

---

## Recording flow

### Part 1 — Show real grid data + energy receipt (~2 min)

**Terminal (visible):**
```bash
# Show live carbon intensity
gpuctl exec gb10-hackathon "cat ~/.ecoclaw/state.json | python3 -c 'import sys,json;d=json.load(sys.stdin);print(f\"Grid: {d[\"carbon_gco2\"]} gCO2/kWh | Mode: {d[\"mode\"]} | {d[\"model_short\"]}\")'"
```

**In WebChat — type these messages:**

1. `What is the carbon footprint of training GPT-4?`
   - Point out receipt: real J, mWh, CO₂ per response, live grid gCO₂/kWh
   - Say: *"Real hardware measurement from the Blackwell GPU — not estimated."*

2. `Hi`
   - Note lower energy for short response (~7-10 J)

3. `Explain photosynthesis in detail`
   - Note higher energy for longer response (~40-60 J), lower tok/J
   - Say: *"Energy scales with response complexity. You can see exactly what each answer costs."*

---

### Part 2 — Inject carbon spike, trigger GPU throttle (~1 min)

**Terminal (on camera or narrated):**
```bash
# Inject fake dirty-grid carbon — above 300 gCO₂/kWh threshold
curl -X POST http://localhost:8001/demo/carbon/450

# Trigger immediate carbon check
curl -X POST http://localhost:8001/demo/poll
```

- Notification appears in WebChat: *"⚡ Grid carbon: 450 gCO₂/kWh — switching to green mode. Throttling GPU to save energy."*

**In WebChat — type:**

4. `How do solar panels work?`
   - Receipt now shows: `throttled @ 1000 MHz` · ~7-15 J · ~3 tok/J
   - Compare to earlier: same model, ~54% less energy
   - Say: *"Same model, same quality — but the GPU is throttled to match grid conditions. 54% energy reduction, instantly."*

---

### Part 3 — Restore (optional, shows full cycle)

**Terminal:**
```bash
# Clean grid → restore full speed
curl -X POST http://localhost:8001/demo/carbon/50
curl -X POST http://localhost:8001/demo/poll
```

- Notification: *"Restoring full GPU performance."*

5. `What's 2 + 2?`
   - Receipt shows: `full speed @ 2398 MHz` · higher J, lower tok/J
   - Full cycle demonstrated

---

### Close
*"Local inference. Real energy measurement from NVML. Carbon-aware GPU throttle — no cloud, no estimation. Runs on one GB10."*

---

## Key numbers to highlight
- Real grid: ~64 gCO₂/kWh (California ISO, live)
- Mock dirty grid: 450 gCO₂/kWh (simulated spike)
- Throttled: ~7-15 J per response, ~3 tok/J, 988 MHz
- Full speed: ~40-60 J per response, ~1.3 tok/J, 2398 MHz
- Savings: **~54% energy reduction** when throttled

## Emergency fallback
If WebChat fails — demo via curl directly:
```bash
gpuctl exec gb10-hackathon "curl -s http://localhost:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{\"model\":\"nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8\",\"messages\":[{\"role\":\"user\",\"content\":\"Explain photosynthesis\"}],\"max_tokens\":80,\"stream\":false}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)[\"choices\"][0][\"message\"][\"content\"])'"
```
