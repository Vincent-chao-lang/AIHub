"""
运营计算引擎：度量、成本归因、七维度可运营性自评分。

所有函数为纯计算，接受 SQLModel Session，返回 Pydantic 响应对象。
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Session, select, func, case

from models.operability import (
    SystemEvent,
    CostRecord,
    Runbook,
    FailureSample,
    MetricsResponse,
    CostDetailItem,
    CostResponse,
    DimensionScore,
    OperabilityScore,
)

logger = logging.getLogger(__name__)

# 七维度名称
DIMENSION_NAMES = {
    1: "可观测·可归因",
    2: "可评估·可度量",
    3: "可恢复·可兜底",
    4: "可演进·可迭代",
    5: "可治理·可控",
    6: "可学习·可改进",
    7: "成本可控 (FinOps)",
}


def _status_to_label(score: int) -> str:
    """将 0-3 评分映射为状态标签。"""
    if score >= 3:
        return "strong"
    elif score >= 1:
        return "partial"
    else:
        return "missing"


def compute_metrics(
    session: Session,
    ai_system_id: Optional[str] = None,
) -> MetricsResponse:
    """计算质量/净收益/返工率/可观测覆盖率。

    Args:
        session: 数据库会话
        ai_system_id: 可选，按系统过滤
    """
    total = session.exec(
        select(func.count()).select_from(SystemEvent).where(
            SystemEvent.ai_system_id == ai_system_id if ai_system_id else True
        )
    ).one()

    if total == 0:
        return MetricsResponse(
            quality_score=0.0,
            net_benefit_hours=0.0,
            rework_rate=0.0,
            observability_coverage=0.0,
        )

    # 成功事件数
    success_query = select(func.count()).select_from(SystemEvent).where(SystemEvent.status == "success")
    if ai_system_id:
        success_query = success_query.where(SystemEvent.ai_system_id == ai_system_id)
    success_count = session.exec(success_query).one()

    # 失败/回滚事件数
    error_query = select(func.count()).select_from(SystemEvent).where(
        SystemEvent.status.in_(["error", "rolled_back"])
    )
    if ai_system_id:
        error_query = error_query.where(SystemEvent.ai_system_id == ai_system_id)
    error_count = session.exec(error_query).one()

    # 质量分：成功事件占比
    quality_score = round(success_count / total, 4)

    # 返工率：失败事件占比
    rework_rate = round(error_count / total, 4)

    # 净收益：成功事件延迟之和 / 3600000 * 0.5（MVP 近似值）
    latency_query = select(func.coalesce(func.sum(SystemEvent.latency_ms), 0)).select_from(
        SystemEvent
    ).where(SystemEvent.status == "success")
    if ai_system_id:
        latency_query = latency_query.where(SystemEvent.ai_system_id == ai_system_id)
    total_latency = session.exec(latency_query).one()
    net_benefit_hours = round((total_latency or 0) / 3_600_000 * 0.5, 2)

    # 可观测覆盖率：有追踪的系统比例
    if ai_system_id:
        observability_coverage = 1.0
    else:
        all_systems = session.exec(
            select(func.count(func.distinct(SystemEvent.ai_system_id)))
        ).one()
        observability_coverage = 1.0 if all_systems > 0 else 0.0

    return MetricsResponse(
        quality_score=quality_score,
        net_benefit_hours=net_benefit_hours,
        rework_rate=rework_rate,
        observability_coverage=round(observability_coverage, 4),
    )


def compute_cost(
    session: Session,
    period: Optional[str] = None,
    owner: Optional[str] = None,
    ai_system_id: Optional[str] = None,
) -> CostResponse:
    """聚合 token/金额成本，对比预算，标记异常。

    Args:
        session: 数据库会话
        period: 计费周期，格式 "YYYY-MM"
        owner: 预算归属人（通过 cost_records 关联）
        ai_system_id: 系统过滤
    """
    # 构建查询
    query = select(SystemEvent)

    if ai_system_id:
        query = query.where(SystemEvent.ai_system_id == ai_system_id)

    if period:
        try:
            year, month = period.split("-")
            query = query.where(
                func.strftime("%Y", SystemEvent.timestamp) == year,
                func.strftime("%m", SystemEvent.timestamp) == month.zfill(2),
            )
        except ValueError:
            pass  # 忽略格式错误的 period

    events = session.exec(query).all()

    # 按 ai_system_id 聚合
    agg: dict[str, dict] = {}
    for e in events:
        sid = e.ai_system_id
        if sid not in agg:
            agg[sid] = {"tokens_input": 0, "tokens_output": 0, "cost_currency": 0.0, "event_count": 0}
        # cost_tokens 既包含 input 也包含 output，简单按 70/30 拆分
        tokens = e.cost_tokens or 0
        agg[sid]["tokens_input"] += int(tokens * 0.7)
        agg[sid]["tokens_output"] += int(tokens * 0.3)
        agg[sid]["cost_currency"] += e.cost_currency or 0.0
        agg[sid]["event_count"] += 1

    totals = {"tokens_input": 0, "tokens_output": 0, "cost_currency": 0.0}
    details = []
    for sid, data in agg.items():
        totals["tokens_input"] += data["tokens_input"]
        totals["tokens_output"] += data["tokens_output"]
        totals["cost_currency"] += data["cost_currency"]
        details.append(CostDetailItem(
            ai_system_id=sid,
            tokens_input=data["tokens_input"],
            tokens_output=data["tokens_output"],
            cost_currency=round(data["cost_currency"], 4),
            event_count=data["event_count"],
        ))

    # 查找匹配的预算记录
    budget_query = select(CostRecord)
    if ai_system_id:
        budget_query = budget_query.where(CostRecord.ai_system_id == ai_system_id)
    if owner:
        budget_query = budget_query.where(CostRecord.owner == owner)
    if period:
        budget_query = budget_query.where(CostRecord.period == period)

    budget_record = session.exec(budget_query).first()

    budget_currency = None
    anomaly_flag = 0
    if budget_record is not None:
        budget_currency = budget_record.budget_currency
        if budget_currency is not None and totals["cost_currency"] > budget_currency:
            anomaly_flag = 1

    return CostResponse(
        period=period,
        owner=owner,
        tokens_input=totals["tokens_input"],
        tokens_output=totals["tokens_output"],
        cost_currency=round(totals["cost_currency"], 4),
        budget_currency=budget_currency,
        anomaly_flag=anomaly_flag,
        details=details,
    )


def compute_operability_score(session: Session) -> OperabilityScore:
    """计算七维度可运营性自评分（满分 21）。

    每个维度 0-3 分：0=否, 1=部分, 2=是, 3=强。
    """
    breakdown: list[DimensionScore] = []

    # ---- D1: 可观测·可归因 ----
    event_count = session.exec(
        select(func.count()).select_from(SystemEvent)
    ).one()
    if event_count > 10:
        d1_score = 3
    elif event_count > 0:
        d1_score = 2
    else:
        # 至少 messages 表有数据（usage 侧有覆盖）
        from models.message import Message
        msg_count = session.exec(select(func.count()).select_from(Message)).one()
        d1_score = 1 if msg_count > 0 else 0

    breakdown.append(DimensionScore(
        dimension=1,
        name=DIMENSION_NAMES[1],
        score=d1_score,
        max_score=3,
        status=_status_to_label(d1_score),
    ))

    # ---- D2: 可评估·可度量 ----
    metrics = compute_metrics(session)
    if metrics.quality_score > 0 and metrics.observability_coverage > 0.5:
        d2_score = 3
    elif metrics.observability_coverage > 0:
        d2_score = 1
    else:
        d2_score = 0

    breakdown.append(DimensionScore(
        dimension=2,
        name=DIMENSION_NAMES[2],
        score=d2_score,
        max_score=3,
        status=_status_to_label(d2_score),
    ))

    # ---- D3: 可恢复·可兜底 ----
    runbook_count = session.exec(
        select(func.count()).select_from(Runbook).where(
            (Runbook.kill_switch_enabled == 1) | (Runbook.rollback_target.isnot(None))
        )
    ).one()
    total_runbooks = session.exec(
        select(func.count()).select_from(Runbook)
    ).one()
    if runbook_count > 0:
        d3_score = 3
    elif total_runbooks > 0:
        d3_score = 1
    else:
        d3_score = 0

    breakdown.append(DimensionScore(
        dimension=3,
        name=DIMENSION_NAMES[3],
        score=d3_score,
        max_score=3,
        status=_status_to_label(d3_score),
    ))

    # ---- D4: 可演进·可迭代 ----
    # 检查 prompt_hash 多样性 + 图谱节点数
    distinct_hashes = session.exec(
        select(func.count(func.distinct(SystemEvent.prompt_hash))).where(
            SystemEvent.prompt_hash.isnot(None)
        )
    ).one()
    # 图谱节点数：conversation 节点
    from models.message import Message
    conv_count = session.exec(
        select(func.count(func.distinct(Message.conversation_id)))
    ).one()

    if distinct_hashes > 1 and conv_count > 10:
        d4_score = 3
    elif conv_count > 0:
        d4_score = 1
    else:
        d4_score = 0

    breakdown.append(DimensionScore(
        dimension=4,
        name=DIMENSION_NAMES[4],
        score=d4_score,
        max_score=3,
        status=_status_to_label(d4_score),
    ))

    # ---- D5: 可治理·可控 ----
    approval_count = session.exec(
        select(func.count()).select_from(SystemEvent).where(
            SystemEvent.human_approval.isnot(None)
        )
    ).one()
    if approval_count > 0:
        d5_score = 3
    elif event_count > 0:
        d5_score = 1
    else:
        d5_score = 0

    breakdown.append(DimensionScore(
        dimension=5,
        name=DIMENSION_NAMES[5],
        score=d5_score,
        max_score=3,
        status=_status_to_label(d5_score),
    ))

    # ---- D6: 可学习·可改进 ----
    promoted_count = session.exec(
        select(func.count()).select_from(FailureSample).where(
            FailureSample.promoted_to_regression == 1
        )
    ).one()
    total_failures = session.exec(
        select(func.count()).select_from(FailureSample)
    ).one()
    if promoted_count > 0:
        d6_score = 3
    elif total_failures > 0:
        d6_score = 1
    else:
        d6_score = 0

    breakdown.append(DimensionScore(
        dimension=6,
        name=DIMENSION_NAMES[6],
        score=d6_score,
        max_score=3,
        status=_status_to_label(d6_score),
    ))

    # ---- D7: 成本可控 (FinOps) ----
    budget_count = session.exec(
        select(func.count()).select_from(CostRecord).where(
            CostRecord.budget_currency.isnot(None)
        )
    ).one()
    anomaly_count = session.exec(
        select(func.count()).select_from(CostRecord).where(
            CostRecord.anomaly_flag == 1
        )
    ).one()
    total_cost_records = session.exec(
        select(func.count()).select_from(CostRecord)
    ).one()

    if budget_count > 0 and anomaly_count == 0:
        d7_score = 3
    elif total_cost_records > 0:
        d7_score = 1
    else:
        d7_score = 0

    breakdown.append(DimensionScore(
        dimension=7,
        name=DIMENSION_NAMES[7],
        score=d7_score,
        max_score=3,
        status=_status_to_label(d7_score),
    ))

    # 计算总分与成熟度
    total_score = sum(d.score for d in breakdown)

    if total_score <= 7:
        maturity = "危险区"
    elif total_score <= 12:
        maturity = "脆弱区"
    elif total_score <= 17:
        maturity = "基本可运营"
    else:
        maturity = "较成熟"

    return OperabilityScore(
        total_score=total_score,
        max_score=21,
        maturity_level=maturity,
        breakdown=breakdown,
    )
