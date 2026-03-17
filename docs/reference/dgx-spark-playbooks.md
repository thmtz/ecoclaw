# NVIDIA DGX Spark Playbooks

Repo: https://github.com/NVIDIA/dgx-spark-playbooks

40+ step-by-step playbooks for AI/ML workloads on NVIDIA DGX Spark (Blackwell). Each includes prerequisites, instructions, troubleshooting, and sample code. Apache 2.0 licensed.

## Relevant to EcoClaw

| Playbook | Path | Relevance |
|-|-|-|
| vLLM | `nvidia/vllm/` | Optimized vLLM inference serving on GB10 |
| Nemotron | `nvidia/nemotron/` | Nemotron model deployment (llama.cpp) |
| NemoClaw | `nvidia/nemoclaw/` | NemoClaw install and setup on DGX Spark |
| NVFP4 Quantization | `nvidia/nvfp4-quantization/` | NVFP4 model quantization on Blackwell |

## Not in scope

- No power/energy management playbooks
- No OpenClaw (only NemoClaw)

## Other notable playbooks

SGLang, TRT-LLM, Speculative Decoding, RAG, NeMo, multi-agent chatbots, FLUX fine-tuning, ComfyUI.
