from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: Optional[str] = Field(default=None, primary_key=True)
    platform: str = Field(index=True)
    conversation_id: str = Field(index=True)
    role: str  # "user" | "assistant"
    content: str
    title: Optional[str] = Field(default=None)
    tags: Optional[str] = Field(default=None)  # comma-separated
    summary: Optional[str] = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.now, index=True)
    created_at: datetime = Field(default_factory=datetime.now)


class MessageCreate(SQLModel):
    platform: str
    conversation_id: str
    role: str
    content: str
    timestamp: Optional[datetime] = None


class MessageResponse(SQLModel):
    id: str
    platform: str
    conversation_id: str
    role: str
    content: str
    title: Optional[str] = None
    tags: Optional[str] = None
    summary: Optional[str] = None
    timestamp: datetime


class SearchRequest(SQLModel):
    query: str


class SearchResult(SQLModel):
    message: MessageResponse
    score: float


class ConversationSummary(SQLModel):
    """Timeline 中一个对话的摘要卡片。"""
    conversation_id: str
    platform: str
    title: Optional[str] = None
    preview: str  # 首条用户消息截取
    tags: Optional[str] = None
    summary: Optional[str] = None
    message_count: int
    latest_timestamp: datetime


class TimelineGroup(SQLModel):
    date: str
    conversations: list[ConversationSummary]


class RelatedConversation(SQLModel):
    conversation_id: str
    title: Optional[str] = None
    platform: str
    score: float
    message_count: int
    latest_timestamp: datetime


class ContextRequest(SQLModel):
    query: str


class ContextResponse(SQLModel):
    query: str
    context_text: str  # 可直接复制注入的上下文段落
    key_points: list[str]  # 关键历史发现
    related: list[RelatedConversation]


class ProjectGroup(SQLModel):
    name: str
    keywords: list[str]
    conversations: list[RelatedConversation]
    total_messages: int


class GraphNode(SQLModel):
    id: str
    type: str  # "conversation" | "tag"
    label: str
    platform: str = ""
    message_count: int = 0  # 仅 conversation 节点
    weight: int = 0  # tag 节点的频率


class GraphEdge(SQLModel):
    source: str
    target: str
    type: str  # "tag_link" | "similar" | "vector_similar"
    weight: float = 1.0


class GraphData(SQLModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
