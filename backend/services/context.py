"""
上下文生成服务。

图谱驱动模式：向量搜索找到种子对话 → 图谱遍历发现关联链 → 输出带推理路径的上下文。
"""

from collections import deque


def build_context_with_graph(
    query: str,
    seed_convs: list[dict],       # 向量搜索直接命中的对话
    conv_meta: dict[str, dict],   # conversation_id → {title, platform, summary, tags, date}
    edges: list[dict],            # [{source, target, type, weight}, ...]
    max_hops: int = 2,
    decay: float = 0.6,
    top_n: int = 8,
) -> tuple[str, list[str], list[dict]]:
    """
    图谱驱动的上下文生成。

    Args:
        query: 用户当前讨论的主题
        seed_convs: 向量搜索直接命中的对话 [{conversation_id, score}, ...]
        conv_meta: 所有对话的元信息
        edges: 图谱中的边（similar + vector_similar）
        max_hops: 图谱遍历最大跳数
        decay: 距离衰减因子
        top_n: 最终返回的对话数量上限

    Returns:
        (context_text, key_points, traversal_paths)
    """
    if not seed_convs:
        return "", [], []

    # 构建邻接表
    adjacency: dict[str, list[tuple[str, str, float]]] = {}  # node → [(neighbor, edge_type, weight)]
    for e in edges:
        if e["type"] not in ("similar", "vector_similar"):
            continue
        s, t, w = e["source"], e["target"], e.get("weight", 0.5)
        adjacency.setdefault(s, []).append((t, e["type"], w))
        adjacency.setdefault(t, []).append((s, e["type"], w))

    # BFS 图谱遍历
    discovered: dict[str, dict] = {}  # conv_id → {score, distance, path}

    # 初始化种子
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
        if dist >= max_hops:
            continue
        if current not in adjacency:
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
                    f"←{'标签' if edge_type == 'similar' else '语义'}关联→ {conv_meta.get(neighbor, {}).get('title', neighbor)[:30]}"
                ],
            }
            queue.append((neighbor, new_dist))

    # 按得分排序
    ranked = sorted(discovered.items(), key=lambda x: -x[1]["score"])[:top_n]

    # 收集片段
    conv_snippets = []
    traversal_paths = []
    key_points = []

    for cid, info in ranked:
        meta = conv_meta.get(cid, {})
        if not meta:
            continue

        summary = meta.get("summary", "")[:300]
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

        # 提取关键点（从直接匹配的对话中）
        if info["distance"] == 0 and summary:
            first_line = summary.split("\n")[0].strip()
            if 10 < len(first_line) < 200:
                key_points.append(first_line)

    context_text = _format_graph_context(query, conv_snippets)
    key_points = key_points[:5]

    return context_text, key_points, traversal_paths


def _format_graph_context(query: str, snippets: list[dict]) -> str:
    """格式化图谱驱动的上下文段落，区分直接匹配和图谱发现。"""
    if not snippets:
        return ""

    direct = [s for s in snippets if s["distance"] == 0]
    discovered = [s for s in snippets if s["distance"] > 0]

    lines = []

    # 直接匹配
    if direct:
        lines.append("[直接相关的历史讨论]\n")
        for i, s in enumerate(direct, 1):
            lines.append(f"{i}. [{s['platform'].upper()}] {s['title']} ({s['date']})")
            lines.append(f"   相关性: {s['score']:.0%}")
            summary = s["summary"]
            if len(summary) > 250:
                summary = summary[:250] + "..."
            lines.append(f"   {summary}")
            if s["tags"]:
                tags = s["tags"].replace("#", "").replace(",", "、")
                lines.append(f"   关键词: {tags}")
            lines.append("")

    # 图谱发现的关联
    if discovered:
        lines.append("[图谱发现的关联讨论]\n")
        lines.append("以下对话通过知识图谱的标签和语义关联被自动发现：\n")
        for i, s in enumerate(discovered, 1):
            lines.append(f"{i}. [{s['platform'].upper()}] {s['title']} ({s['date']})")
            lines.append(f"   关联强度: {s['score']:.0%} (图谱 {s['distance']} 跳)")
            summary = s["summary"]
            if len(summary) > 250:
                summary = summary[:250] + "..."
            lines.append(f"   {summary}")
            if s["tags"]:
                tags = s["tags"].replace("#", "").replace(",", "、")
                lines.append(f"   关键词: {tags}")
            lines.append("")

    lines.append(f"[当前讨论: {query}]")
    lines.append("请基于以上历史讨论（包括图谱自动发现的关联对话）的上下文来回答。")

    return "\n".join(lines)
