"""Energy proxy — sits between OpenClaw and vLLM.

Measures NVML energy per request and injects an energy receipt
into every response (streaming and non-streaming).
"""
import json
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from . import state as st
from .nvml import measure, energy_mj

VLLM_BASE = "http://localhost:8000"
PROXY_PORT = 8001

app = FastAPI(title="EcoClaw Energy Proxy")


def _format_receipt(delta_mj: float, tokens: int) -> str:
    tok_per_j = (tokens / (delta_mj / 1000)) if delta_mj > 0 else 0
    s = st.get()
    return (
        f"\n\n─────────────────────────────\n"
        f"⚡ Energy: {delta_mj:.0f} mJ · {delta_mj/3600:.4f} mWh · {tok_per_j:.0f} tok/J\n"
        f"🌱 Grid: {s.carbon_gco2:.0f} gCO₂/kWh · {s.mode} · {s.model_short}\n"
        f"─────────────────────────────"
    )


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy(request: Request, path: str):
    url = f"{VLLM_BASE}/{path}"
    body = await request.body()

    # Non-chat endpoints: pass through unchanged
    is_chat = path in ("v1/chat/completions", "v1/completions")
    if not is_chat:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.request(
                method=request.method,
                url=url,
                headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
                content=body,
            )
        return Response(content=r.content, status_code=r.status_code,
                        media_type=r.headers.get("content-type"))

    # Parse request to check streaming
    try:
        req_json = json.loads(body)
    except Exception:
        req_json = {}
    streaming = req_json.get("stream", False)

    if streaming:
        # Ask vLLM to include usage stats in the final streaming chunk
        req_json.setdefault("stream_options", {})["include_usage"] = True
        body = json.dumps(req_json).encode()
        return await _stream_proxy(request, url, body)
    else:
        return await _nonstream_proxy(request, url, body)


async def _nonstream_proxy(request: Request, url: str, body: bytes) -> Response:
    energy = {}
    try:
        with measure() as energy:
            async with httpx.AsyncClient(timeout=300) as client:
                r = await client.request(
                    method=request.method,
                    url=url,
                    headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
                    content=body,
                )
            resp = r.json()
    except httpx.ConnectError:
        return Response(
            content=json.dumps({"error": {"message": "vLLM backend unavailable", "type": "proxy_error"}}),
            status_code=502, media_type="application/json",
        )

    total_tokens = resp.get("usage", {}).get("completion_tokens", 0)
    receipt = _format_receipt(energy.get("energy_mj", 0), total_tokens)

    # Append receipt to message content
    choices = resp.get("choices", [])
    if choices:
        msg = choices[0].get("message", {})
        msg["content"] = (msg.get("content") or "") + receipt
        choices[0]["message"] = msg

    return Response(
        content=json.dumps(resp),
        status_code=r.status_code,
        media_type="application/json",
    )


async def _stream_proxy(request: Request, url: str, body: bytes) -> StreamingResponse:
    # Pre-flight check: fail fast if vLLM is unreachable
    try:
        async with httpx.AsyncClient(timeout=5) as probe:
            await probe.get(f"{VLLM_BASE}/health")
    except (httpx.ConnectError, httpx.TimeoutException):
        return Response(
            content=json.dumps({"error": {"message": "vLLM backend unavailable", "type": "proxy_error"}}),
            status_code=502, media_type="application/json",
        )

    async def generate():
        total_tokens = 0
        energy_before = energy_mj()
        receipt_injected = False

        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                method=request.method,
                url=url,
                headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
                content=body,
            ) as r:
                async for line in r.aiter_lines():
                    if not line:
                        yield "\n"
                        continue

                    if line == "data: [DONE]":
                        if not receipt_injected:
                            delta_mj = max(0.0, energy_mj() - energy_before)
                            receipt = _format_receipt(delta_mj, total_tokens)
                            footer_chunk = json.dumps({
                                "choices": [{"delta": {"content": receipt}, "index": 0}]
                            })
                            yield f"data: {footer_chunk}\n\n"
                            receipt_injected = True
                        yield "data: [DONE]\n\n"
                        break

                    if line.startswith("data: "):
                        try:
                            chunk = json.loads(line[6:])
                            # Use real usage from final chunk if available
                            usage = chunk.get("usage")
                            if usage and usage.get("completion_tokens"):
                                total_tokens = usage["completion_tokens"]
                            elif not usage:
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                if delta.get("content"):
                                    total_tokens += 1
                        except Exception:
                            pass
                    yield f"{line}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    st.load_from_disk()
    uvicorn.run(app, host="0.0.0.0", port=PROXY_PORT)
