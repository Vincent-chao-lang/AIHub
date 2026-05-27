"""
上下文生成服务：将相关历史对话编织为可直接注入的上下文段落。
"""

from models.message import Message, RelatedConversation


def build_context(
    query: str,
    related_messages: list[Message],
    related_convs: list[dict],
) -> tuple[str, list[str]]:
    """根据检索到的相关消息生成上下文文本和关键点。

    Args:
        query: 用户当前讨论的主题
        related_messages: 按相似度排序的历史消息列表
        related_convs: 相关对话的摘要信息

    Returns:
        (context_text, key_points)
    """
    if not related_messages and not related_convs:
        return "", []

    # 收集不同对话的关键信息
    seen_convs = set()
    conv_snippets = []
    key_points = []

    for msg in related_messages:
        cid = msg.conversation_id
        if cid in seen_convs:
            continue
        seen_convs.add(cid)

        platform = msg.platform
        title = msg.title or msg.content[:60]
        summary = msg.summary or msg.content[:200]

        conv_snippets.append({
            "platform": platform,
            "title": title,
            "summary": summary,
            "tags": msg.tags or "",
            "date": msg.timestamp.strftime("%Y-%m-%d"),
        })

        # 提取关键发现
        if msg.role == "assistant" and len(msg.content) > 50:
            # 取 AI 回复的第一句作为关键点
            first_line = msg.content.split("\n")[0].strip()
            if len(first_line) > 10 and len(first_line) < 200:
                key_points.append(first_line)

        if len(conv_snippets) >= 5:
            break

    # 生成上下文段落
    context_text = _format_context(query, conv_snippets)
    key_points = key_points[:5]  # 最多 5 个关键点

    return context_text, key_points


def _format_context(query: str, snippets: list[dict]) -> str:
    """将对话片段格式化为可注入的上下文段落。"""
    if not snippets:
        return ""

    lines = ["[历史相关讨论]\n"]

    for i, s in enumerate(snippets, 1):
        lines.append(f"{i}. [{s['platform'].upper()}] {s['title']} ({s['date']})")
        # 截取摘要的关键部分
        summary = s["summary"]
        if len(summary) > 300:
            summary = summary[:300] + "..."
        lines.append(f"   {summary}")
        if s["tags"]:
            tags = s["tags"].replace("#", "").replace(",", "、")
            lines.append(f"   关键词: {tags}")
        lines.append("")

    lines.append(f"[当前讨论: {query}]")
    lines.append("请基于以上历史讨论的上下文来回答当前问题。")

    return "\n".join(lines)
