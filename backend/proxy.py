"""
AIHub Proxy · LLM 采集网关

在 AI 编程工具和 LLM API 之间做透明 HTTP 转发，旁路提取运营元数据
（model、tokens、latency、tool_calls），上报到 AIHub。

启动方式：
    python proxy.py                          # 独立进程，端口 8888
    python proxy.py --port 8889              # 自定义端口
    python proxy.py --aihub http://x:8712    # 自定义 AIHub 地址

Agent 侧接入：
    export ANTHROPIC_BASE_URL=http://localhost:8888
    export OPENAI_BASE_URL=http://localhost:8888

设计原则：
    - 原始请求/响应只在内存中处理，不落地
    - 只提取运营元数据，不存储 prompt 原文、代码内容
    - 流式响应逐块转发，不增加用户感知延迟
    - 旁路上报异步执行，代理 Crash 不影响 LLM 调用
"""
import os
import sys
import json
import time
import hashlib
import logging
import argparse
from typing import Optional

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import StreamingResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [proxy] %(message)s")
logger = logging.getLogger("aihub.proxy")

# ============================================================
# 配置
# ============================================================

AIHUB_URL = os.getenv("AIHUB_URL", "http://localhost:8712")
UPSTREAM_ANTHROPIC = os.getenv("UPSTREAM_ANTHROPIC", "https://api.anthropic.com")
UPSTREAM_OPENAI = os.getenv("UPSTREAM_OPENAI", "https://api.openai.com")

app = FastAPI(title="AIHub Proxy", version="0.1.0")

# ============================================================
# 元数据提取
# ============================================================

def _hash_prompt_system(request_body: dict) -> Optional[str]:
    """对 system prompt 取哈希，用于 prompt 版本追踪。"""
    system = request_body.get("system")
    if not system:
        # OpenAI 格式：messages[0] 可能是 system
        messages = request_body.get("messages", [])
        if messages and messages[0].get("role") == "system":
            system = messages[0].get("content", "")
    if system:
        if isinstance(system, list):  # Anthropic 支持数组格式
            system = json.dumps(system, sort_keys=True)
        return hashlib.md5(system.encode()).hexdigest()[:8]
    return None


def _extract_user_input(request_body: dict) -> Optional[str]:
    """从请求体中提取最后一条用户消息的原文。"""
    messages = request_body.get("messages", [])
    if not messages:
        return None
    # 找最后一条 role=user 的消息
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            # Anthropic 支持数组格式 content: [{type: "text", text: "..."}]
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                return " ".join(text_parts) if text_parts else str(content)
            return str(content) if content else None
    return None


def extract_anthropic_metadata(
    request_body: dict,
    response_body: dict,
    latency_ms: int,
    status: str,
) -> dict:
    """从 Anthropic API 响应提取运营元数据。"""
    model_version = response_body.get("model") or request_body.get("model")
    usage = response_body.get("usage", {})
    cost_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

    # 判断 event_type：检查 content 中是否有 tool_use
    event_type = "inference"
    tool_calls = []
    for block in response_body.get("content", []):
        if block.get("type") == "tool_use":
            event_type = "tool_call"
            tool_calls.append({"tool": block.get("name", "unknown")})

    return {
        "ai_system_id": "claude-code",
        "event_type": event_type,
        "model_version": model_version,
        "prompt_hash": _hash_prompt_system(request_body),
        "tool_calls": json.dumps(tool_calls) if tool_calls else None,
        "latency_ms": latency_ms,
        "cost_tokens": cost_tokens,
        "status": status,
        "event_metadata": json.dumps({"user_input": _extract_user_input(request_body)}, ensure_ascii=False),
    }


def extract_anthropic_stream_metadata(
    request_body: dict,
    stream_events: list[dict],
    latency_ms: int,
) -> dict:
    """从 Anthropic 流式事件提取运营元数据。"""
    model_version = request_body.get("model")
    input_tokens = 0
    output_tokens = 0
    tool_calls = []
    status = "success"

    for event in stream_events:
        etype = event.get("type", "")
        if etype == "message_start":
            msg = event.get("message", {})
            model_version = msg.get("model") or model_version
            input_tokens = msg.get("usage", {}).get("input_tokens", 0)
        elif etype == "content_block_start":
            cb = event.get("content_block", {})
            if cb.get("type") == "tool_use":
                tool_calls.append({"tool": cb.get("name", "unknown")})
        elif etype == "message_delta":
            output_tokens = event.get("usage", {}).get("output_tokens", 0)
        elif etype == "error":
            status = "error"

    event_type = "tool_call" if tool_calls else "inference"

    return {
        "ai_system_id": "claude-code",
        "event_type": event_type,
        "model_version": model_version,
        "prompt_hash": _hash_prompt_system(request_body),
        "tool_calls": json.dumps(tool_calls) if tool_calls else None,
        "latency_ms": latency_ms,
        "cost_tokens": input_tokens + output_tokens,
        "status": status,
        "event_metadata": json.dumps({"user_input": _extract_user_input(request_body)}, ensure_ascii=False),
    }


def extract_openai_metadata(
    request_body: dict,
    response_body: dict,
    latency_ms: int,
    status: str,
) -> dict:
    """从 OpenAI API 响应提取运营元数据。"""
    model_version = response_body.get("model") or request_body.get("model")
    usage = response_body.get("usage", {})
    cost_tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

    event_type = "inference"
    tool_calls = []
    for choice in response_body.get("choices", []):
        msg = choice.get("message", {})
        for tc in msg.get("tool_calls", []):
            event_type = "tool_call"
            fn = tc.get("function", {})
            tool_calls.append({"tool": fn.get("name", "unknown")})

    return {
        "ai_system_id": "cursor",
        "event_type": event_type,
        "model_version": model_version,
        "prompt_hash": _hash_prompt_system(request_body),
        "tool_calls": json.dumps(tool_calls) if tool_calls else None,
        "latency_ms": latency_ms,
        "cost_tokens": cost_tokens,
        "status": status,
        "event_metadata": json.dumps({"user_input": _extract_user_input(request_body)}, ensure_ascii=False),
    }


# ============================================================
# 旁路上报
# ============================================================

def report_to_aihub(event_data: dict):
    """异步上报到 AIHub 的 POST /system-events。"""
    try:
        resp = httpx.post(
            f"{AIHUB_URL}/system-events",
            json=event_data,
            timeout=5.0,
        )
        if resp.status_code == 200:
            logger.debug(f"上报成功: {event_data.get('event_type')} | {event_data.get('model_version')} | {event_data.get('cost_tokens')} tokens")
        else:
            logger.warning(f"上报失败 {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        logger.warning(f"上报异常: {e}")


# ============================================================
# HTTP 转发
# ============================================================

FORWARD_HEADERS_BLOCKLIST = {
    "host", "content-length", "transfer-encoding", "connection",
    "x-forwarded-for", "x-forwarded-proto", "x-forwarded-host",
    "content-encoding",  # 代理已解码，避免下游重复解压
}


def _clean_headers(headers: dict) -> dict:
    """过滤不应转发的 header。"""
    return {
        k: v for k, v in headers.items()
        if k.lower() not in FORWARD_HEADERS_BLOCKLIST
    }


async def _read_and_forward(
    request: Request,
    upstream_base: str,
    background_tasks: BackgroundTasks,
    metadata_extractor,
) -> Response:
    """通用转发逻辑：读请求 → 转发到上游 → 提取元数据 → 返回响应。"""
    t0 = time.time()

    # 读取请求体
    req_body = await request.body()
    try:
        req_json = json.loads(req_body) if req_body else {}
    except json.JSONDecodeError:
        req_json = {}

    # 构造上游 URL
    path = request.url.path
    upstream_url = f"{upstream_base}{path}"
    if request.url.query:
        upstream_url += f"?{request.url.query}"

    # 转发
    async with httpx.AsyncClient(timeout=120.0) as client:
        upstream_resp = await client.request(
            method=request.method,
            url=upstream_url,
            headers=_clean_headers(dict(request.headers)),
            content=req_body,
        )

    latency_ms = int((time.time() - t0) * 1000)

    # 读取响应体并提取元数据
    resp_body = upstream_resp.content
    try:
        resp_json = json.loads(resp_body) if resp_body else {}
    except json.JSONDecodeError:
        resp_json = {}

    status = "success" if 200 <= upstream_resp.status_code < 300 else "error"

    if resp_json:
        event_data = metadata_extractor(req_json, resp_json, latency_ms, status)
        background_tasks.add_task(report_to_aihub, event_data)

    # 返回响应（过滤不应转发的响应头）
    resp_headers = _clean_headers(dict(upstream_resp.headers))
    return Response(
        content=resp_body,
        status_code=upstream_resp.status_code,
        headers=resp_headers,
    )


async def _stream_and_forward_anthropic(
    request: Request,
    background_tasks: BackgroundTasks,
) -> StreamingResponse:
    """Anthropic 流式请求：逐块转发 SSE + 收集元数据。"""
    t0 = time.time()
    req_body = await request.body()
    try:
        req_json = json.loads(req_body) if req_body else {}
    except json.JSONDecodeError:
        req_json = {}

    path = request.url.path
    upstream_url = f"{UPSTREAM_ANTHROPIC}{path}"
    if request.url.query:
        upstream_url += f"?{request.url.query}"

    stream_events: list[dict] = []

    async def generate():
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                method=request.method,
                url=upstream_url,
                headers=_clean_headers(dict(request.headers)),
                content=req_body,
            ) as upstream_resp:
                async for line in upstream_resp.aiter_lines():
                    yield line + "\n"
                    # 解析 SSE 事件
                    if line.startswith("data: "):
                        try:
                            event = json.loads(line[6:])
                            stream_events.append(event)
                        except json.JSONDecodeError:
                            pass

        # 流结束后上报
        latency_ms = int((time.time() - t0) * 1000)
        if stream_events:
            event_data = extract_anthropic_stream_metadata(
                req_json, stream_events, latency_ms
            )
            report_to_aihub(event_data)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ============================================================
# 路由
# ============================================================

@app.api_route("/v1/messages", methods=["POST"])
async def proxy_anthropic(request: Request, background_tasks: BackgroundTasks):
    """转发 Anthropic API 请求（/v1/messages）。"""
    req_body = await request.body()
    try:
        req_json = json.loads(req_body) if req_body else {}
    except json.JSONDecodeError:
        req_json = {}

    # 流式请求走独立处理
    if req_json.get("stream"):
        return await _stream_and_forward_anthropic(request, background_tasks)

    return await _read_and_forward(
        request, UPSTREAM_ANTHROPIC, background_tasks,
        extract_anthropic_metadata,
    )


@app.api_route("/v1/chat/completions", methods=["POST"])
async def proxy_openai(request: Request, background_tasks: BackgroundTasks):
    """转发 OpenAI 兼容 API 请求（/v1/chat/completions）。"""
    return await _read_and_forward(
        request, UPSTREAM_OPENAI, background_tasks,
        extract_openai_metadata,
    )


@app.api_route("/{path:path}", methods=["POST", "GET", "PUT", "DELETE", "PATCH"])
async def proxy_catchall(request: Request, path: str):
    """兜底路由：透传到 Anthropic 上游。"""
    upstream_url = f"{UPSTREAM_ANTHROPIC}/{path}"
    if request.url.query:
        upstream_url += f"?{request.url.query}"

    async with httpx.AsyncClient(timeout=120.0) as client:
        upstream_resp = await client.request(
            method=request.method,
            url=upstream_url,
            headers=_clean_headers(dict(request.headers)),
            content=await request.body(),
        )

    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=_clean_headers(dict(upstream_resp.headers)),
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "AIHub Proxy"}


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AIHub Proxy · LLM 采集网关")
    parser.add_argument("--port", type=int, default=8888, help="代理监听端口（默认 8888）")
    parser.add_argument("--aihub", type=str, default=AIHUB_URL, help="AIHub 后端地址")
    args = parser.parse_args()

    AIHUB_URL = args.aihub

    logger.info(f"AIHub Proxy 启动")
    logger.info(f"  监听端口: {args.port}")
    logger.info(f"  AIHub 后端: {AIHUB_URL}")
    logger.info(f"  Anthropic 上游: {UPSTREAM_ANTHROPIC}")
    logger.info(f"  OpenAI 上游: {UPSTREAM_OPENAI}")
    logger.info(f"")
    logger.info(f"Agent 侧接入:")
    logger.info(f"  export ANTHROPIC_BASE_URL=http://localhost:{args.port}")
    logger.info(f"  export OPENAI_BASE_URL=http://localhost:{args.port}")

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
