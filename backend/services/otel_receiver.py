"""
OTel Receiver：解析 OTLP trace 数据，将 Span 转换为 SystemEvent，复用既有采集管线。

支持两种传输格式：
- application/x-protobuf：OTLP 标准 protobuf 二进制格式
- application/json：OTLP JSON 格式（便于调试和非 protobuf 环境）

Agent 侧接入方式（零代码）：
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    exporter = OTLPSpanExporter(endpoint="http://localhost:8712/v1/traces")

或通过环境变量：
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:8712/v1/traces
    OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
"""
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Any

from google.protobuf.json_format import MessageToDict

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)
from opentelemetry.proto.trace.v1.trace_pb2 import Status
from opentelemetry.proto.common.v1.common_pb2 import KeyValue

from models.operability import SystemEvent, SystemEventCreate
from db.database import get_session

logger = logging.getLogger(__name__)

# Gen AI 语义约定属性键（字符串常量）
ATTR_SERVICE_NAME = "service.name"
ATTR_GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
ATTR_GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
ATTR_GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
ATTR_GEN_AI_SYSTEM = "gen_ai.system"
ATTR_GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
ATTR_GEN_AI_PROMPT_NAME = "gen_ai.prompt.name"
ATTR_GEN_AI_DATA_SOURCE_ID = "gen_ai.data_source.id"
ATTR_GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"
ATTR_GEN_AI_AGENT_NAME = "gen_ai.agent.name"
ATTR_GEN_AI_AGENT_ID = "gen_ai.agent.id"
ATTR_GEN_AI_TOOL_NAME = "gen_ai.tool.name"
ATTR_GEN_AI_TOOL_CALL_ID = "gen_ai.tool.call.id"
ATTR_GEN_AI_TOOL_CALL_ARGUMENTS = "gen_ai.tool.call.arguments"
ATTR_GEN_AI_TOOL_CALL_RESULT = "gen_ai.tool.call.result"


def _extract_attr(attributes: list[KeyValue], key: str) -> Optional[Any]:
    """从 OTel KeyValue 列表中提取指定 key 的值。

    支持 string_value、int_value、double_value、bool_value。
    """
    for attr in attributes:
        if attr.key == key:
            which = attr.value.WhichOneof("value")
            if which is None:
                return None
            return getattr(attr.value, which)
    return None


def _attrs_to_dict(attributes: list[KeyValue]) -> dict[str, Any]:
    """将 KeyValue 列表转为普通 dict，便于序列化为 JSON。"""
    result = {}
    for attr in attributes:
        which = attr.value.WhichOneof("value")
        if which is not None:
            result[attr.key] = getattr(attr.value, which)
    return result


def _determine_event_type(span_name: str, attributes: list[KeyValue]) -> str:
    """根据 span name 和属性判断事件类型。

    优先级：
    1. 显式的 gen_ai.operation.name 属性
    2. 包含 tool 相关属性的 → tool_call
    3. span name 包含关键词判断
    4. 默认 inference
    """
    # 显式 operation.name
    op_name = _extract_attr(attributes, ATTR_GEN_AI_OPERATION_NAME)
    if op_name:
        op_lower = str(op_name).lower()
        if "tool" in op_lower or "execute" in op_lower:
            return "tool_call"
        if "approval" in op_lower or "human" in op_lower:
            return "approval"
        if "handoff" in op_lower:
            return "handoff"
        return "inference"

    # 检测工具调用
    has_tool_name = _extract_attr(attributes, ATTR_GEN_AI_TOOL_NAME)
    has_tool_call_id = _extract_attr(attributes, ATTR_GEN_AI_TOOL_CALL_ID)
    if has_tool_name or has_tool_call_id:
        return "tool_call"

    # span name 关键词
    name_lower = span_name.lower()
    if "tool" in name_lower or "function" in name_lower:
        return "tool_call"
    if "approval" in name_lower or "human" in name_lower:
        return "approval"
    if "handoff" in name_lower or "transfer" in name_lower:
        return "handoff"

    return "inference"


def _extract_tool_calls_json(attributes: list[KeyValue]) -> Optional[str]:
    """从 span 属性中提取工具调用信息，序列化为 JSON 字符串。"""
    tool_name = _extract_attr(attributes, ATTR_GEN_AI_TOOL_NAME)
    tool_call_id = _extract_attr(attributes, ATTR_GEN_AI_TOOL_CALL_ID)
    tool_args = _extract_attr(attributes, ATTR_GEN_AI_TOOL_CALL_ARGUMENTS)
    tool_result = _extract_attr(attributes, ATTR_GEN_AI_TOOL_CALL_RESULT)

    if not any([tool_name, tool_call_id, tool_args]):
        return None

    tool_info = {}
    if tool_name:
        tool_info["tool"] = str(tool_name)
    if tool_call_id:
        tool_info["call_id"] = str(tool_call_id)
    if tool_args:
        tool_info["arguments"] = str(tool_args)
    if tool_result:
        # 截断过长结果
        result_str = str(tool_result)
        if len(result_str) > 500:
            result_str = result_str[:500] + "..."
        tool_info["result"] = result_str

    return json.dumps([tool_info], ensure_ascii=False)


def _extract_human_approval_json(attributes: list[KeyValue]) -> Optional[str]:
    """从 span 属性中提取人工审批信息。"""
    # 查找审批相关属性（可通过自定义属性扩展）
    approver = None
    result = None
    threshold = None

    for attr in attributes:
        if "approval" in attr.key.lower() or "approver" in attr.key.lower():
            which = attr.value.WhichOneof("value")
            if which:
                val = getattr(attr.value, which)
                if "approver" in attr.key.lower():
                    approver = str(val)
                elif "result" in attr.key.lower():
                    result = str(val)
                elif "threshold" in attr.key.lower():
                    threshold = str(val)

    if approver or result:
        approval = {}
        if approver:
            approval["approver"] = approver
        if result:
            approval["result"] = result
        if threshold:
            approval["threshold"] = threshold
        return json.dumps(approval, ensure_ascii=False)

    return None


def span_to_system_event_create(
    span,
    resource_attrs: list[KeyValue],
    scope_name: Optional[str] = None,
) -> SystemEventCreate:
    """将单个 OTel Span 转换为 SystemEventCreate。

    Args:
        span: opentelemetry.proto.trace.v1.Span
        resource_attrs: resource 级别的属性列表
        scope_name: instrumentation scope 名称（可选）
    """
    # ai_system_id：优先 agent.name，其次 service.name
    ai_system_id = (
        _extract_attr(resource_attrs, ATTR_GEN_AI_AGENT_NAME)
        or _extract_attr(resource_attrs, ATTR_GEN_AI_AGENT_ID)
        or _extract_attr(resource_attrs, ATTR_SERVICE_NAME)
        or _get_span_attr(span, ATTR_GEN_AI_AGENT_NAME)
        or "unknown"
    )

    if isinstance(ai_system_id, bytes):
        ai_system_id = ai_system_id.decode("utf-8", errors="replace")

    # 合并 span 级别和 resource 级别属性（span 优先）
    merged_attrs = list(resource_attrs) + list(span.attributes)

    # event_type
    event_type = _determine_event_type(span.name, merged_attrs)

    # model_version
    model_version = _extract_attr(merged_attrs, ATTR_GEN_AI_REQUEST_MODEL)
    if model_version is not None:
        model_version = str(model_version)

    # prompt_hash（使用 prompt.name 作为版本标识）
    prompt_hash = _extract_attr(merged_attrs, ATTR_GEN_AI_PROMPT_NAME)
    if prompt_hash is not None:
        prompt_hash = str(prompt_hash)

    # retrieval_source（RAG 数据源）
    retrieval_source = _extract_attr(merged_attrs, ATTR_GEN_AI_DATA_SOURCE_ID)
    if retrieval_source is not None:
        retrieval_source = str(retrieval_source)

    # tool_calls JSON
    tool_calls = _extract_tool_calls_json(merged_attrs)

    # human_approval JSON
    human_approval = _extract_human_approval_json(merged_attrs)

    # latency_ms（纳秒 → 毫秒）
    latency_ms = None
    if span.start_time_unix_nano and span.end_time_unix_nano:
        latency_ms = int((span.end_time_unix_nano - span.start_time_unix_nano) / 1_000_000)

    # cost_tokens（合并 input + output）
    input_tokens = _extract_attr(merged_attrs, ATTR_GEN_AI_USAGE_INPUT_TOKENS)
    output_tokens = _extract_attr(merged_attrs, ATTR_GEN_AI_USAGE_OUTPUT_TOKENS)
    cost_tokens = None
    if input_tokens is not None or output_tokens is not None:
        cost_tokens = (int(input_tokens or 0)) + (int(output_tokens or 0))

    # status
    if span.status.code == Status.STATUS_CODE_ERROR:
        status = "error"
    elif span.status.code == Status.STATUS_CODE_OK:
        status = "success"
    else:
        status = None  # UNSET

    # timestamp：从 span start_time 转换（纳秒 → datetime）
    if span.start_time_unix_nano:
        timestamp = datetime.fromtimestamp(span.start_time_unix_nano / 1_000_000_000, tz=timezone.utc)
    else:
        timestamp = None

    # event_metadata：存储额外信息（resource 属性 + span ID 等）
    metadata = {
        "span_name": span.name,
        "trace_id": span.trace_id.hex() if span.trace_id else None,
        "span_id": span.span_id.hex() if span.span_id else None,
        "scope": scope_name,
        "provider": str(_extract_attr(merged_attrs, ATTR_GEN_AI_PROVIDER_NAME) or ""),
        "system": str(_extract_attr(merged_attrs, ATTR_GEN_AI_SYSTEM) or ""),
    }
    event_metadata = json.dumps(metadata, ensure_ascii=False, default=str)

    return SystemEventCreate(
        ai_system_id=str(ai_system_id),
        event_type=event_type,
        model_version=model_version,
        prompt_hash=prompt_hash,
        retrieval_source=retrieval_source,
        tool_calls=tool_calls,
        human_approval=human_approval,
        latency_ms=latency_ms,
        cost_tokens=cost_tokens,
        status=status,
        timestamp=timestamp,
        event_metadata=event_metadata,
    )


def _get_span_attr(span, key: str) -> Optional[str]:
    """从 Span 自身属性中查找（span.attributes 为 repeated KeyValue）。"""
    return _extract_attr(span.attributes, key)


def process_otlp_traces(
    body: bytes,
    background_tasks,
    content_type: str = "application/x-protobuf",
) -> dict:
    """处理 OTLP trace 请求的入口函数。

    1. 反序列化 ExportTraceServiceRequest
    2. 遍历所有 Span → 转换为 SystemEventCreate
    3. 写入数据库 + 触发后台 embedding + 摘要
    4. 返回处理统计

    Returns:
        {"events_processed": int, "spans_total": int, "errors": list[str]}
    """
    request = ExportTraceServiceRequest()

    if "json" in content_type:
        # OTLP JSON 格式
        try:
            data = json.loads(body) if isinstance(body, bytes) else body
            from google.protobuf.json_format import ParseDict
            request = ParseDict(data, ExportTraceServiceRequest())
        except Exception as e:
            logger.error(f"OTLP JSON 解析失败: {e}")
            return {"events_processed": 0, "spans_total": 0, "errors": [str(e)]}
    else:
        # OTLP protobuf 格式
        try:
            request.ParseFromString(body)
        except Exception as e:
            logger.error(f"OTLP protobuf 解析失败: {e}")
            return {"events_processed": 0, "spans_total": 0, "errors": [str(e)]}

    # 遍历所有 Span
    total_spans = 0
    events_processed = 0
    errors = []

    for resource_spans in request.resource_spans:
        resource_attrs = list(resource_spans.resource.attributes)

        for scope_spans in resource_spans.scope_spans:
            scope_name = scope_spans.scope.name if scope_spans.scope else None

            for span in scope_spans.spans:
                total_spans += 1
                try:
                    # Convert to SystemEventCreate
                    event_data = span_to_system_event_create(
                        span, resource_attrs, scope_name
                    )

                    # Write to database
                    event = SystemEvent(
                        id=uuid.uuid4().hex,
                        ai_system_id=event_data.ai_system_id,
                        event_type=event_data.event_type,
                        model_version=event_data.model_version,
                        prompt_hash=event_data.prompt_hash,
                        retrieval_source=event_data.retrieval_source,
                        tool_calls=event_data.tool_calls,
                        human_approval=event_data.human_approval,
                        latency_ms=event_data.latency_ms,
                        cost_tokens=event_data.cost_tokens,
                        cost_currency=event_data.cost_currency,
                        status=event_data.status,
                        timestamp=event_data.timestamp or datetime.now(timezone.utc),
                        event_metadata=event_data.event_metadata,
                    )

                    with next(get_session()) as session:
                        session.add(event)
                        session.commit()
                        session.refresh(event)

                    # Trigger async pipeline: embedding + summarization + failure detection
                    from services.event_collector import process_system_event
                    process_system_event(event, background_tasks, get_session)

                    events_processed += 1

                except Exception as e:
                    logger.error(f"Span 处理失败: {e}")
                    errors.append(f"span error: {e}")

    logger.info(
        f"OTLP 处理完成: {events_processed}/{total_spans} spans → system_events"
    )

    return {
        "events_processed": events_processed,
        "spans_total": total_spans,
        "errors": errors,
    }
