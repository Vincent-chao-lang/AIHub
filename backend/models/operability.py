"""
运营平面数据模型：系统事件、成本记录、兜底登记、失败样本库。

所有表复用 SQLModel，与 message 表同库存储。
"""
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


# ============================================================
# 数据库表（SQLModel, table=True）
# ============================================================

class SystemEvent(SQLModel, table=True):
    """AI 系统运行事件表（P0 采集扩展核心）。

    每一次 AI 系统运行事件（inference / tool_call / approval / handoff / error）
    都落一条记录，复用 embedding + 摘要 + 图谱管线。
    """
    __tablename__ = "system_events"

    id: str = Field(primary_key=True)
    ai_system_id: str = Field(index=True)
    event_type: str = Field(index=True)  # inference / tool_call / approval / handoff / error
    model_version: Optional[str] = Field(default=None)
    prompt_hash: Optional[str] = Field(default=None)
    retrieval_source: Optional[str] = Field(default=None)
    tool_calls: Optional[str] = Field(default=None)       # JSON
    human_approval: Optional[str] = Field(default=None)   # JSON: approver / result / threshold
    latency_ms: Optional[int] = Field(default=None)
    cost_tokens: Optional[int] = Field(default=None)
    cost_currency: Optional[float] = Field(default=None)
    status: Optional[str] = Field(default=None)  # success / error / blocked / rolled_back
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    title: Optional[str] = Field(default=None)    # 自动摘要标题
    tags: Optional[str] = Field(default=None)     # 自动标签（逗号分隔）
    summary: Optional[str] = Field(default=None)  # 自动摘要
    embedding_id: Optional[str] = Field(default=None)  # ChromaDB 关联 ID
    event_metadata: Optional[str] = Field(default=None)  # JSON: blast_radius / risk_tier 等
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CostRecord(SQLModel, table=True):
    """成本记录表（P3 成本平面 / FinOps）。"""
    __tablename__ = "cost_records"

    id: str = Field(primary_key=True)
    ai_system_id: str = Field(index=True)
    owner: str = Field(index=True)           # 预算归属人
    period: str = Field(index=True)          # 计费周期，如 "2026-07"
    tokens_input: int = Field(default=0)
    tokens_output: int = Field(default=0)
    cost_currency: float = Field(default=0.0)
    budget_currency: Optional[float] = Field(default=None)  # 该 owner 当月预算上限
    anomaly_flag: int = Field(default=0)    # 0=正常, 1=越线
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Runbook(SQLModel, table=True):
    """兜底/恢复登记表（P4 恢复平面）。"""
    __tablename__ = "runbooks"

    id: str = Field(primary_key=True)
    ai_system_id: str = Field(index=True)
    blast_radius: Optional[str] = Field(default=None)   # 爆炸半径描述
    fallback_plan: Optional[str] = Field(default=None)  # 兜底方案
    rollback_target: Optional[str] = Field(default=None)  # 回滚目标（模型/提示/索引版本）
    kill_switch_enabled: int = Field(default=0)  # 是否预置熔断（0/1）
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FailureSample(SQLModel, table=True):
    """失败样本库表（P5 学习闭环）。"""
    __tablename__ = "failure_samples"

    id: str = Field(primary_key=True)
    source_type: str = Field(index=True)  # system_event / message
    source_id: str                        # 对应 system_event.id 或 message.id
    failure_mode: Optional[str] = Field(default=None)  # 错误类型 / 根因
    labeled: int = Field(default=0)       # 是否已标注（0/1）
    promoted_to_regression: int = Field(default=0)  # 是否已沉淀为回归集（0/1）
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================
# 请求 / 响应模型（SQLModel，非表）
# ============================================================

class SystemEventCreate(SQLModel):
    """POST /system-events 请求体。"""
    ai_system_id: str
    event_type: str
    model_version: Optional[str] = None
    prompt_hash: Optional[str] = None
    retrieval_source: Optional[str] = None
    tool_calls: Optional[str] = None        # JSON 字符串
    human_approval: Optional[str] = None    # JSON 字符串
    latency_ms: Optional[int] = None
    cost_tokens: Optional[int] = None
    cost_currency: Optional[float] = None
    status: Optional[str] = None
    timestamp: Optional[datetime] = None
    event_metadata: Optional[str] = None


class SystemEventResponse(SQLModel):
    """POST /system-events 响应。"""
    id: str
    indexed: bool = True


class MetricsResponse(SQLModel):
    """GET /metrics 响应。"""
    quality_score: float
    net_benefit_hours: float
    rework_rate: float
    observability_coverage: float


class CostDetailItem(SQLModel):
    """成本归因明细（按 ai_system_id 拆分）。"""
    ai_system_id: str
    tokens_input: int
    tokens_output: int
    cost_currency: float
    event_count: int


class CostResponse(SQLModel):
    """GET /cost 响应。"""
    period: Optional[str] = None
    owner: Optional[str] = None
    tokens_input: int = 0
    tokens_output: int = 0
    cost_currency: float = 0.0
    budget_currency: Optional[float] = None
    anomaly_flag: int = 0
    details: list[CostDetailItem] = []


class RunbookCreate(SQLModel):
    """POST /systems/{id}/runbook 请求体。"""
    blast_radius: Optional[str] = None
    fallback_plan: Optional[str] = None
    rollback_target: Optional[str] = None
    kill_switch_enabled: bool = False


class RunbookResponse(SQLModel):
    """Runbook 响应（所有字段，int → bool 转换）。"""
    id: str
    ai_system_id: str
    blast_radius: Optional[str] = None
    fallback_plan: Optional[str] = None
    rollback_target: Optional[str] = None
    kill_switch_enabled: bool = False
    updated_at: Optional[datetime] = None


class FailureSampleResponse(SQLModel):
    """FailureSample 响应（int → bool 转换）。"""
    id: str
    source_type: str
    source_id: str
    failure_mode: Optional[str] = None
    labeled: bool = False
    promoted_to_regression: bool = False
    created_at: Optional[datetime] = None


class DimensionScore(SQLModel):
    """七维度单项评分。"""
    dimension: int       # 1-7
    name: str            # 维度名称
    score: int           # 0-3（0=否, 1=部分, 2=是, 3=强）
    max_score: int = 3
    status: str          # "strong" / "partial" / "missing"


class OperabilityScore(SQLModel):
    """GET /operability/score 响应。"""
    total_score: int
    max_score: int = 21
    maturity_level: str  # "危险区" / "脆弱区" / "基本可运营" / "较成熟"
    breakdown: list[DimensionScore]
