"""
上下文生成服务。

图谱驱动模式：向量搜索找到种子对话 → 图谱遍历发现关联链 → 输出带推理路径的上下文。
智能截断：按优先级（直接匹配 > 图谱发现）控制 Token 数量，适配 LLM 上下文窗口。
"""

from collections import deque

import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


def estimate_tokens(text: str) -> int:
    """使用 tiktoken cl100k_base 编码估算 Token 数量。"""
    if not text:
        return 0
    return len(_ENCODING.encode(text))


def _trim_summary(summary: str, max_len: int) -> str:
    """截断摘要到指定长度，保留完整句子。"""
    if len(summary) <= max_len:
        return summary
    truncated = summary[:max_len]
    # 回退到最后一个句号/换行处
    last_break = max(truncated.rfind("。"), truncated.rfind("\n"), truncated.rfind("."))
    if last_break > max_len * 0.5:
        return truncated[:last_break + 1] + "..."
    return truncated + "..."


def build_context_with_graph(
    query: str,
    seed_convs: list[dict],
    conv_meta: dict[str, dict],
    edges: list[dict],
    max_hops: int = 2,
    decay: float = 0.6,
    max_tokens: int = 2000,
    top_n: int = 8,
) -> tuple[str, list[str], list[dict], int]:
    """
    图谱驱动的上下文生成。

    Args:
        query: 用户当前讨论的主题
        seed_convs: 向量搜索直接命中的对话
        conv_meta: 所有对话的元信息
        edges: 图谱中的边
        max_hops: 最大遍历跳数
        decay: 距离衰减因子
        max_tokens: 上下文最大 Token 数（超出部分智能截断）
        top_n: 最终返回的对话数量上限

    Returns:
        (context_text, key_points, traversal_paths, estimated_tokens)
    """
    if not seed_convs:
        return "", [], [], 0

    # ── 构建邻接表 ──
    adjacency: dict[str, list[tuple[str, str, float]]] = {}
    for e in edges:
        if e["type"] not in ("similar", "vector_similar"):
            continue
        s, t, w = e["source"], e["target"], e.get("weight", 0.5)
        adjacency.setdefault(s, []).append((t, e["type"], w))
        adjacency.setdefault(t, []).append((s, e["type"], w))

    # ── BFS 图谱遍历 ──
    discovered: dict[str, dict] = {}
    for seed in seed_convs:
        cid = seed["conversation_id"]
        discovered[cid] = {
            "score": seed.get("score", 0.8),
            "distance": 0,
            "path": ["直接匹配"],
        }

    queue = deque([(cid, 0) for cid in discovered])
    while queue:
        current, dist = queue.popleft()
        if dist >= max_hops or current not in adjacency:
            continue
        current_score = discovered[current]["score"]
        for neighbor, edge_type, edge_weight in adjacency[current]:
            if neighbor in discovered:
                continue
            new_dist = dist + 1
            new_score = current_score * decay * edge_weight
            discovered[neighbor] = {
                "score": round(new_score, 4),
                "distance": new_dist,
                "path": discovered[current]["path"] + [
                    f"←{'标签' if edge_type == 'similar' else '语义'}关联→ "
                    f"{conv_meta.get(neighbor, {}).get('title', neighbor)[:30]}"
                ],
            }
            queue.append((neighbor, new_dist))

    # ── 排序、分优先级 ──
    ranked = sorted(discovered.items(), key=lambda x: (-(x[1]["distance"] == 0), -x[1]["score"]))

    # ── Token 预算分配 ──
    # 固定开销：标题行 + 结尾提示 ≈ 100 tokens
    overhead = estimate_tokens(f"[当前讨论: {query}]\n请基于以上历史讨论的上下文来回答。")
    budget = max_tokens - overhead - 50  # 预留 50 margin

    conv_snippets = []
    traversal_paths = []
    key_points = []
    remaining_budget = budget

    for cid, info in ranked:
        if len(conv_snippets) >= top_n:
            break
        meta = conv_meta.get(cid, {})
        if not meta:
            continue

        # 分配这个对话的预算
        is_direct = info["distance"] == 0
        base_budget = 400 if is_direct else 250  # 直接匹配多一些空间
        conv_budget = min(base_budget, remaining_budget)
        if conv_budget < 60:  # 不够放标题了，跳过
            break

        summary = meta.get("summary", "") or ""
        # 根据预算截断摘要
        header = f"[{meta.get('platform', '')}] {meta.get('title', '')} "
        header_tokens = estimate_tokens(header)
        summary_budget = max(conv_budget - header_tokens - 30, 20)
        summary = _trim_summary(summary, int(summary_budget * 1.5))  # 字符数 ≈ token * 1.5

        conv_snippets.append({
            "platform": meta.get("platform", ""),
            "title": meta.get("title", cid[:40]),
            "summary": summary,
            "tags": meta.get("tags", ""),
            "date": meta.get("date", ""),
            "distance": info["distance"],
            "score": info["score"],
        })

        traversal_paths.append({
            "conversation_id": cid,
            "title": meta.get("title", ""),
            "platform": meta.get("platform", ""),
            "distance": info["distance"],
            "score": info["score"],
            "path": info["path"],
        })

        # 消耗预算
        snippet_text = header + summary
        remaining_budget -= estimate_tokens(snippet_text)

        # 关键点
        if is_direct and summary:
            first_line = summary.split("\n")[0].strip()
            if 10 < len(first_line) < 200:
                key_points.append(first_line)

    # ── 生成上下文 ──
    context_text = _format_graph_context(query, conv_snippets)
    estimated = estimate_tokens(context_text)

    return context_text, key_points[:5], traversal_paths, estimated


def _format_graph_context(query: str, snippets: list[dict]) -> str:
    """格式化上下文段落。"""
    if not snippets:
        return ""

    direct = [s for s in snippets if s["distance"] == 0]
    discovered = [s for s in snippets if s["distance"] > 0]

    lines = []

    if direct:
        lines.append("[直接相关的历史讨论]\n")
        for i, s in enumerate(direct, 1):
            lines.append(f"{i}. [{s['platform'].upper()}] {s['title']} ({s['date']})")
            lines.append(f"   相关性: {s['score']:.0%}")
            lines.append(f"   {s['summary']}")
            if s["tags"]:
                tags = s["tags"].replace("#", "").replace(",", "、")
                lines.append(f"   关键词: {tags}")
            lines.append("")

    if discovered:
        lines.append("[图谱发现的关联讨论]\n")
        lines.append("以下对话通过知识图谱的标签和语义关联被自动发现：\n")
        for i, s in enumerate(discovered, 1):
            lines.append(f"{i}. [{s['platform'].upper()}] {s['title']} ({s['date']})")
            lines.append(f"   关联强度: {s['score']:.0%} (图谱 {s['distance']} 跳)")
            lines.append(f"   {s['summary']}")
            if s["tags"]:
                tags = s["tags"].replace("#", "").replace(",", "、")
                lines.append(f"   关键词: {tags}")
            lines.append("")

    lines.append(f"[当前讨论: {query}]")
    lines.append("请基于以上历史讨论（包括图谱自动发现的关联对话）的上下文来回答。")

    return "\n".join(lines)
