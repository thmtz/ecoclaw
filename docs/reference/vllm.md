# vLLM Reference

Notes on running vLLM on the GB10. All findings validated on device.

## Environment

```bash
source ~/.profile && ml   # activates ~/.venvs/ml
vllm serve <model>
```

vLLM 0.17.1, PyTorch 2.10.0+cu130, Python 3.12.

## Serving a model

```bash
# Start in a screen session
screen -dmS vllm bash -lc 'source ~/.profile && ml && vllm serve <model> --trust-remote-code --max-model-len 4096 2>&1 | tee /tmp/vllm.log'

# Check logs
screen -S vllm -X hardcopy /tmp/vllm.log && tail -20 /tmp/vllm.log

# Test
curl -s http://localhost:8000/v1/models
curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "<model-id>", "messages": [{"role": "user", "content": "hello"}]}'
```

## Startup time

Startup takes 3-5+ minutes for large models due to:
1. Loading safetensors shards from disk
2. torch.inductor JIT compilation (first run only — cached after)
3. CUDA graph capture (piecewise + full decode)

**CUDA graph cache** is stored at `~/.cache/vllm/torch_compile_cache/`. After the first run, subsequent startups are faster (skip recompilation). Still takes ~1-2 min for weight loading.

**Warning:** "Capturing CUDA graphs (decode, FULL)" is the slow phase. Each step takes progressively longer as batch sizes grow. 35 steps, up to ~130s per step at the large end. Total first-run startup for Nano 30B: ~30-45 min. Subsequent runs: significantly faster (graphs are cached).

**`--enforce-eager` — DO NOT USE with NVFP4 MoE models:**
Disables BOTH torch.inductor AND CUDA graphs (`-cc.mode=NONE -cc.cudagraph_mode=NONE`). Tested on GB10 with Nemotron-3 Nano NVFP4:
- Startup fast (~2.5 min) but inference returns empty responses (tokens counted, content blank)
- Root cause: NVFP4 MoE CUTLASS kernels are not CUDA-graph-safe (vllm issue #35566); disabling graphs causes silent failures
- Performance: ~8x throughput regression on Blackwell hardware (140 → 17 tok/s) even when it works

**Surgical alternatives (finer-grained control):**
- `-cc.mode=0` — disables torch.inductor JIT only; CUDA graphs still captured. Faster startup, no throughput loss.
- `-cc.cudagraph_mode=NONE` — disables CUDA graphs only; torch.inductor still compiles.

**Bottom line:** The full CUDA graph startup (~30-45 min first run, faster after cache) is required for correct NVFP4 MoE inference. The cache persists at `~/.cache/vllm/torch_compile_cache/` — subsequent startups are significantly faster.

## Nemotron-3 Nano — NVFP4 backend compatibility

**The NVFP4 quantized model has kernel compatibility issues on GB10 (sm_121).** All known NVFP4 GEMM backends fail or produce NaN on this hardware:

| Backend | Result |
|-|-|
| `FLASHINFER_CUTLASS` (default) | Autotuner skips failing tactics; surviving tactics produce NaN logits → empty content |
| `VLLM_CUTLASS` | `RuntimeError: Error Internal` at engine init |
| `MARLIN` | **Works** — produces real output, correct inference |

**Root cause:** PyTorch 2.10 supports CUDA capability up to sm_120; GB10 is sm_121. CUTLASS GEMM kernels for NVFP4 fail to initialize. NaN logits cause sampler to pick tokens that decode to empty strings.

**Diagnosis markers:**
- `ValueError: Out of range float values are not JSON compliant: nan` in server logs when requesting logprobs
- Completion tokens > 0 but `content: ""` in every response (streaming and non-streaming)
- `Skipping tactic ... Failed to initialize cutlass TMA WS grouped gemm` in autotuner logs

### Env vars for backend selection

```bash
# Use MARLIN for both linear and MoE (avoids CUTLASS entirely)
VLLM_USE_FLASHINFER_MOE_FP4=0 VLLM_NVFP4_GEMM_BACKEND=marlin

# Use vLLM CUTLASS (not FlashInfer) — currently crashes on sm_121
VLLM_USE_FLASHINFER_MOE_FP4=0 VLLM_NVFP4_GEMM_BACKEND=cutlass
```

### Working launch command (validated on GB10)

```bash
screen -dmS vllm bash -lc 'source ~/.profile && ml && \
  VLLM_USE_FLASHINFER_MOE_FP4=0 VLLM_NVFP4_GEMM_BACKEND=marlin \
  vllm serve nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4 \
    --trust-remote-code \
    --max-model-len 32768 \
    --reasoning-parser nano_v3 \
    --reasoning-parser-plugin ~/.cache/huggingface/hub/models--nvidia--NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4/snapshots/ce1b118ae66ec705d02c241525192832eb045fd3/nano_v3_reasoning_parser.py \
  2>&1 | tee /tmp/vllm-nano.log'
```

**Chat API with thinking enabled (default):**
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4",
       "messages": [{"role": "user", "content": "..."}],
       "max_tokens": 10000}'
```
Returns: `reasoning` field = thinking trace, `content` field = final answer.

**Chat API with thinking disabled (faster):**
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4",
       "messages": [{"role": "user", "content": "..."}],
       "max_tokens": 256,
       "chat_template_kwargs": {"enable_thinking": false}}'
```

**Important:** Use `max_tokens >= 1000` in reasoning mode — the thinking trace alone can consume hundreds of tokens before the final answer appears.

### Nemotron models — required flags

Both Nemotron models require `--trust-remote-code` due to custom model code in the repo.

## Model memory usage (per-process, validated)

`nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv` reports actual allocation.

| Model | Observed GPU memory |
|-|-|
| Qwen/Qwen2.5-0.5B-Instruct | ~110 GiB (preallocates ~90% of unified memory by default) |
| Nemotron-3 Nano 30B NVFP4 | TBD |
| Nemotron-3 Super 120B NVFP4 | TBD |

**Note:** vLLM preallocates ~90% of available memory for KV cache by default. On GB10 with 119 GiB unified memory this is ~107 GiB regardless of model size. Use `--gpu-memory-utilization` to tune.

## Switching models

Two options:
1. Kill the screen session, start a new one with the new model: `screen -S vllm -X quit`
2. vLLM does not support hot-swapping models in a single server instance

Switchover takes 2-5 minutes (weight load + CUDA graph capture, faster after first run due to cache).

## OpenAI-compatible API

vLLM exposes a full OpenAI-compatible API at `http://localhost:8000/v1`:
- `GET /v1/models` — list loaded models
- `POST /v1/chat/completions` — chat inference
- `POST /v1/completions` — completion inference

The model ID in requests must match the HuggingFace repo ID (e.g. `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4`).

## OpenClaw integration

OpenClaw has a native vLLM provider. Set `VLLM_API_KEY=anything` (no auth needed locally) and it auto-discovers models from `/v1/models`. See `docs/reference/openclaw.md` (TBD).

## Gotchas

- `--trust-remote-code` required for Nemotron models
- `ImportError: libcudart.so.12` — fix: `sudo apt install cuda-cudart-12-8`
- `fatal error: Python.h` — fix: `sudo apt install python3-dev`
- Memory fields in `nvidia-smi` show `[N/A]` — normal for unified memory, use `--query-compute-apps` instead
- First startup significantly slower than subsequent due to JIT compilation
