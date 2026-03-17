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

- [GB10 setup & environment](docs/gb10-setup.md) — full install details, power telemetry, gotchas
