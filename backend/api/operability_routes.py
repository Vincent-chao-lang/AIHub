"""
运营平面 API 路由：系统事件采集、度量、成本、恢复、学习闭环。

所有端点均为纯新增，不影响既有 api/routes.py 中的 10 个端点。
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException, Request
from sqlmodel import Session, select, func

from db.database import get_session
from models.operability import (
    SystemEvent,
    SystemEventCreate,
    SystemEventResponse,
    MetricsResponse,
    CostResponse,
    OperabilityScore,
    Runbook,
    RunbookCreate,
    RunbookResponse,
    FailureSample,
    FailureSampleResponse,
)
from services.event_collector import process_system_event
from services.otel_receiver import process_otlp_traces
from services.operability import compute_metrics, compute_cost, compute_operability_score

logger = logging.getLogger(__name__)
operability_router = APIRouter()


# ============================================================
# P0 · 采集面扩展
# ============================================================

@operability_router.post("/system-events", response_model=SystemEventResponse)
def create_system_event(
    event_data: SystemEventCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """接收 AI 系统运行事件，触发后台 embedding + 摘要。

    事件类型包括：inference / tool_call / approval / handoff / error。
    与 /messages 共用同一套 embedding + 摘要 + 图谱管线。
    """
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
    session.add(event)
    session.commit()
    session.refresh(event)

    # 派发后台任务：embedding + 摘要；同步检测 error → 创建 FailureSample
    process_system_event(event, background_tasks, get_session)

    return SystemEventResponse(id=event.id, indexed=True)


# ============================================================
# P0 · OTel Receiver（OTLP 标准协议）
# ============================================================

@operability_router.post("/v1/traces")
async def receive_otlp_traces(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """接收 OTLP trace 数据（OpenTelemetry 标准协议）。

    支持 Content-Type: application/x-protobuf 和 application/json。

    Agent 侧接入（零代码）：
        exporter = OTLPSpanExporter(endpoint="http://localhost:8712/v1/traces")
    """
    content_type = request.headers.get("content-type", "application/x-protobuf")
    body = await request.body()

    if not body:
        return {"events_processed": 0, "spans_total": 0, "errors": ["empty body"]}

    result = process_otlp_traces(body, background_tasks, content_type)
    return result


# ============================================================
# P2 · 度量平面
# ============================================================

@operability_router.get("/metrics", response_model=MetricsResponse)
def get_metrics(
    ai_system_id: Optional[str] = Query(None, description="按 AI 系统过滤"),
    session: Session = Depends(get_session),
):
    """获取质量分、净收益、返工率、可观测覆盖率。

    替代 /stats 的纯计数，从 system_events 数据派生运营指标。
    """
    return compute_metrics(session, ai_system_id=ai_system_id)


# ============================================================
# P3 · 成本平面 (FinOps)
# ============================================================

@operability_router.get("/cost", response_model=CostResponse)
def get_cost(
    period: Optional[str] = Query(None, description="计费周期，格式 YYYY-MM"),
    owner: Optional[str] = Query(None, description="预算归属人"),
    ai_system_id: Optional[str] = Query(None, description="按 AI 系统过滤"),
    session: Session = Depends(get_session),
):
    """获取成本归因 + 预算对比 + 异常标记。

    从 system_events 聚合 token/金额，与 cost_records 预算对比。
    """
    return compute_cost(session, period=period, owner=owner, ai_system_id=ai_system_id)


# ============================================================
# 七维度自评分
# ============================================================

@operability_router.get("/operability/score", response_model=OperabilityScore)
def get_operability_score(
    session: Session = Depends(get_session),
):
    """获取 AI 可运营七维度自评分（满分 21）。

    每维度 0-3 分，含成熟度分档：危险区 / 脆弱区 / 基本可运营 / 较成熟。
    """
    return compute_operability_score(session)


# ============================================================
# P4 · 恢复/兜底平面
# ============================================================

@operability_router.get("/systems/{system_id}/runbook", response_model=RunbookResponse)
def get_runbook(
    system_id: str,
    session: Session = Depends(get_session),
):
    """获取指定 AI 系统的兜底/回滚配置。"""
    runbook = session.exec(
        select(Runbook).where(Runbook.ai_system_id == system_id)
    ).first()

    if runbook is None:
        raise HTTPException(status_code=404, detail=f"系统 {system_id} 的 Runbook 不存在")

    return RunbookResponse(
        id=runbook.id,
        ai_system_id=runbook.ai_system_id,
        blast_radius=runbook.blast_radius,
        fallback_plan=runbook.fallback_plan,
        rollback_target=runbook.rollback_target,
        kill_switch_enabled=bool(runbook.kill_switch_enabled),
        updated_at=runbook.updated_at,
    )


@operability_router.post("/systems/{system_id}/runbook", response_model=RunbookResponse)
def upsert_runbook(
    system_id: str,
    data: RunbookCreate,
    session: Session = Depends(get_session),
):
    """登记/更新 AI 系统的兜底配置（upsert）。

    每个 ai_system_id 最多一张 runbook，重复 POST 会更新现有记录。
    """
    runbook = session.exec(
        select(Runbook).where(Runbook.ai_system_id == system_id)
    ).first()

    if runbook is None:
        runbook = Runbook(
            id=uuid.uuid4().hex,
            ai_system_id=system_id,
        )
        session.add(runbook)

    runbook.blast_radius = data.blast_radius
    runbook.fallback_plan = data.fallback_plan
    runbook.rollback_target = data.rollback_target
    runbook.kill_switch_enabled = 1 if data.kill_switch_enabled else 0
    runbook.updated_at = datetime.now(timezone.utc)

    session.commit()
    session.refresh(runbook)

    return RunbookResponse(
        id=runbook.id,
        ai_system_id=runbook.ai_system_id,
        blast_radius=runbook.blast_radius,
        fallback_plan=runbook.fallback_plan,
        rollback_target=runbook.rollback_target,
        kill_switch_enabled=bool(runbook.kill_switch_enabled),
        updated_at=runbook.updated_at,
    )


# ============================================================
# P5 · 学习闭环
# ============================================================

@operability_router.get("/failure-samples", response_model=list[FailureSampleResponse])
def list_failure_samples(
    source_type: Optional[str] = Query(None, description="来源类型：system_event / message"),
    labeled: Optional[bool] = Query(None, description="是否已标注"),
    promoted_to_regression: Optional[bool] = Query(None, description="是否已沉淀为回归集"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """获取失败样本列表，支持按来源类型/标注状态/回归状态过滤。"""
    query = select(FailureSample)

    if source_type:
        query = query.where(FailureSample.source_type == source_type)
    if labeled is not None:
        query = query.where(FailureSample.labeled == (1 if labeled else 0))
    if promoted_to_regression is not None:
        query = query.where(FailureSample.promoted_to_regression == (1 if promoted_to_regression else 0))

    query = query.order_by(FailureSample.created_at.desc()).offset(offset).limit(limit)
    samples = session.exec(query).all()

    return [
        FailureSampleResponse(
            id=s.id,
            source_type=s.source_type,
            source_id=s.source_id,
            failure_mode=s.failure_mode,
            labeled=bool(s.labeled),
            promoted_to_regression=bool(s.promoted_to_regression),
            created_at=s.created_at,
        )
        for s in samples
    ]


@operability_router.post("/failure-samples/{sample_id}/promote", response_model=FailureSampleResponse)
def promote_failure_sample(
    sample_id: str,
    session: Session = Depends(get_session),
):
    """将失败样本提升为回归测试集。

    设置 promoted_to_regression=1，用于后续模型/提示变更的回归护航。
    """
    sample = session.get(FailureSample, sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail=f"FailureSample {sample_id} 不存在")

    sample.promoted_to_regression = 1
    session.commit()
    session.refresh(sample)

    return FailureSampleResponse(
        id=sample.id,
        source_type=sample.source_type,
        source_id=sample.source_id,
        failure_mode=sample.failure_mode,
        labeled=bool(sample.labeled),
        promoted_to_regression=True,
        created_at=sample.created_at,
    )
