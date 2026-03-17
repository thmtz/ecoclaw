"""Energy proxy — sits between OpenClaw and vLLM.

Measures NVML energy per request and injects an energy receipt
into every response (streaming and non-streaming).
"""
import json
import logging
import threading
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from pathlib import Path

from . import state as st
from .nvml import measure, energy_mj

log = logging.getLogger(__name__)

VLLM_BASE = "http://localhost:8000"
PROXY_PORT = 8001
MOCK_FILE = Path.home() / ".ecoclaw" / "mock_carbon"

# Set by main.py so /demo/poll can signal the carbon router thread
demo_poll_event: threading.Event | None = None

app = FastAPI(title="EcoClaw Energy Proxy")


@app.post("/demo/carbon/{value}")
async def demo_set_carbon(value: float):
    """Write a mock carbon value to ~/.ecoclaw/mock_carbon for demo control."""
    MOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    MOCK_FILE.write_text(str(value))
    st.update(carbon_gco2=value)
    log.info("Demo: set mock carbon to %s gCO2/kWh", value)
    return {"mock_carbon": value}


@app.post("/demo/poll")
async def demo_poll():
    """Trigger an immediate carbon router poll (don't wait for the timer)."""
    if demo_poll_event is not None:
        demo_poll_event.set()
        return {"status": "poll triggered"}
    return {"status": "no poll event registered"}


def _fmt_energy(mj: float) -> str:
    if mj >= 1000:
        return f"{mj/1000:.2f} J"
    elif mj >= 1:
        return f"{mj:.0f} mJ"
    else:
        return f"{mj*1000:.0f} µJ"


def _fmt_power(mj: float) -> str:
    mwh = mj / 3600
    if mwh >= 1000:
        return f"{mwh/1000:.4f} Wh"
    elif mwh >= 0.01:
        return f"{mwh:.4f} mWh"
    else:
        return f"{mwh*1000:.2f} µWh"


def _format_receipt(delta_mj: float, tokens: int) -> str:
    tok_per_j = (tokens / (delta_mj / 1000)) if delta_mj > 0 else 0
    s = st.get()
    return (
        f"\n\n─────────────────────────────\n"
        f"⚡ Energy: {_fmt_energy(delta_mj)} · {_fmt_power(delta_mj)} · {tok_per_j:.0f} tok/J\n"
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
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.request(
                    method=request.method,
                    url=url,
                    headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
                    content=body,
                )
            return Response(content=r.content, status_code=r.status_code,
                            media_type=r.headers.get("content-type"))
        except httpx.ConnectError:
            return Response(
                content=json.dumps({"error": {"message": "vLLM backend unavailable", "type": "proxy_error"}}),
                status_code=502, media_type="application/json",
            )

    # Parse request to check streaming
    try:
        req_json = json.loads(body)
    except Exception:
        req_json = {}

    # Rewrite model ID to match currently-loaded model (handles carbon router switches)
    req_json["model"] = st.get().model

    # Strip fields vLLM doesn't support (sent by OpenClaw/OpenAI-compatible clients)
    # tool_choice="auto" requires --enable-auto-tool-choice and --tool-call-parser flags
    _VLLM_UNSUPPORTED = {"store", "metadata", "reasoning_effort", "tool_choice", "tools"}
    stripped = {f for f in _VLLM_UNSUPPORTED if req_json.pop(f, None) is not None}
    log.debug("Request keys from client: %s", sorted(req_json.keys()))
    if stripped:
        log.info("Stripped unsupported vLLM fields: %s", stripped)

    # Clamp token limits to vLLM's --max-model-len
    MAX_TOKENS = 2048
    for field in ("max_completion_tokens", "max_tokens"):
        if req_json.get(field, 0) > MAX_TOKENS:
            log.info("Clamping %s from %d to %d", field, req_json[field], MAX_TOKENS)
            req_json[field] = MAX_TOKENS

    body = json.dumps(req_json).encode()

    # Strip headers that must not be forwarded when body is modified
    _STRIP = {"host", "content-length", "transfer-encoding"}
    _fwd_headers = {k: v for k, v in request.headers.items() if k.lower() not in _STRIP}

    streaming = req_json.get("stream", False)

    if streaming:
        # Ask vLLM to include usage stats in the final streaming chunk
        req_json.setdefault("stream_options", {})["include_usage"] = True
        body = json.dumps(req_json).encode()
        return await _stream_proxy(request, url, body, _fwd_headers)
    else:
        return await _nonstream_proxy(request, url, body, _fwd_headers)


async def _nonstream_proxy(request: Request, url: str, body: bytes, headers: dict) -> Response:
    energy = {}
    try:
        with measure() as energy:
            async with httpx.AsyncClient(timeout=300) as client:
                r = await client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    content=body,
                )
            resp = r.json()
            if r.status_code >= 400:
                log.error("vLLM %d: %s", r.status_code, resp)
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


async def _stream_proxy(request: Request, url: str, body: bytes, headers: dict) -> StreamingResponse:
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
                headers=headers,
                content=body,
            ) as r:
                if r.status_code >= 400:
                    err_body = await r.aread()
                    log.error("vLLM stream %d: %s", r.status_code, err_body.decode())
                    yield f"data: {json.dumps({'error': {'message': err_body.decode(), 'type': 'vllm_error'}})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
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
                            if usage is not None:
                                ct = usage.get("completion_tokens")
                                if ct:
                                    total_tokens = ct
                            else:
                                # No usage key — count content tokens as fallback
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                if delta.get("content"):
                                    total_tokens += 1
                        except Exception:
                            pass
                    yield f"{line}\n\n"

        delta_mj = max(0.0, energy_mj() - energy_before)
        tok_per_j = (total_tokens / (delta_mj / 1000)) if delta_mj > 0 else 0
        log.info("stream done: tokens=%d, delta_mj=%.1f, tok_per_j=%.2f", total_tokens, delta_mj, tok_per_j)

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    st.load_from_disk()
    uvicorn.run(app, host="0.0.0.0", port=PROXY_PORT)
