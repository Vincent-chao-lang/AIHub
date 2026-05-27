import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import * as d3 from "d3-force";
import { api } from "../api/client";
import type { GraphData, GraphNode } from "../types";
import { PLATFORM_COLORS } from "../types";

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  type: string;
  label: string;
  platform: string;
  weight: number;
}

interface SimEdge {
  source: string | SimNode;
  target: string | SimNode;
  type: string;
  weight: number;
}

export default function Graph() {
  const navigate = useNavigate();
  const svgRef = useRef<SVGSVGElement>(null);
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [hovered, setHovered] = useState<GraphNode | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getGraph()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const runSimulation = useCallback(() => {
    if (!data || !svgRef.current || !containerRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = 600;
    const svg = svgRef.current;

    svg.setAttribute("width", String(width));
    svg.setAttribute("height", String(height));
    svg.innerHTML = "";

    // 构建节点和边
    const nodeMap = new Map<string, SimNode>();
    const nodes: SimNode[] = data.nodes.map(n => {
      const simNode: SimNode = {
        id: n.id,
        type: n.type,
        label: n.label,
        platform: n.platform,
        weight: n.weight,
        x: Math.random() * width,
        y: Math.random() * height,
      };
      nodeMap.set(n.id, simNode);
      return simNode;
    });

    const edges: SimEdge[] = data.edges
      .filter(e => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map(e => ({
        source: nodeMap.get(e.source)!,
        target: nodeMap.get(e.target)!,
        type: e.type,
        weight: e.weight,
      }));

    // 力导向模拟
    const simulation = d3.forceSimulation<SimNode>(nodes)
      .force("link", d3.forceLink<SimNode, SimEdge>(edges)
        .id(d => d.id)
        .distance(e => 120 / (e.weight + 0.5))
        .strength(e => e.weight * 0.3))
      .force("charge", d3.forceManyBody()
        .strength(d => (d as SimNode).type === "tag" ? -200 : -400))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide(30));

    // SVG 元素
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");

    // 边
    const edgeGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const edgeLines = edges.map(edge => {
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("stroke", edge.type === "similar" ? "#3b82f6" :
        edge.type === "vector_similar" ? "#8b5cf6" : "#e5e7eb");
      line.setAttribute("stroke-width", String(Math.max(edge.weight * 3, 0.5)));
      line.setAttribute("stroke-opacity", "0.4");
      edgeGroup.appendChild(line);
      return line;
    });

    // 节点
    const nodeGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const nodeCircles = nodes.map(node => {
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      const r = node.type === "conversation" ? 8 : Math.min(node.weight * 2 + 5, 20);
      circle.setAttribute("r", String(r));

      if (node.type === "conversation") {
        circle.setAttribute("fill", PLATFORM_COLORS[node.platform] || "#6b7280");
      } else {
        circle.setAttribute("fill", "#3b82f6");
        circle.setAttribute("opacity", "0.7");
      }
      circle.setAttribute("stroke", "#fff");
      circle.setAttribute("stroke-width", "2");
      circle.style.cursor = "pointer";
      circle.style.transition = "r 0.2s";

      circle.addEventListener("mouseenter", () => {
        circle.setAttribute("r", String(r * 1.5));
        setHovered(node as unknown as GraphNode);
      });
      circle.addEventListener("mouseleave", () => {
        circle.setAttribute("r", String(r));
        setHovered(null);
      });
      circle.addEventListener("click", () => {
        if (node.type === "conversation") {
          navigate(`/conversation/${node.id}`);
        }
      });

      nodeGroup.appendChild(circle);
      return circle;
    });

    // 标签
    const labelGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const nodeLabels = nodes.map(node => {
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      const label = node.type === "conversation"
        ? node.label.slice(0, 15) + (node.label.length > 15 ? "..." : "")
        : node.label;
      text.textContent = label;
      text.setAttribute("font-size", node.type === "conversation" ? "11" : "10");
      text.setAttribute("fill", node.type === "conversation" ? "#374151" : "#3b82f6");
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("dy", node.type === "conversation" ? "-14" : "-8");
      text.style.pointerEvents = "none";
      labelGroup.appendChild(text);
      return text;
    });

    g.appendChild(edgeGroup);
    g.appendChild(nodeGroup);
    g.appendChild(labelGroup);
    svg.appendChild(g);

    // 更新位置
    simulation.on("tick", () => {
      edgeLines.forEach((line, i) => {
        const e = edges[i];
        const s = e.source as SimNode;
        const t = e.target as SimNode;
        line.setAttribute("x1", String(s.x!));
        line.setAttribute("y1", String(s.y!));
        line.setAttribute("x2", String(t.x!));
        line.setAttribute("y2", String(t.y!));
      });
      nodeCircles.forEach((circle, i) => {
        circle.setAttribute("cx", String(nodes[i].x!));
        circle.setAttribute("cy", String(nodes[i].y!));
      });
      nodeLabels.forEach((text, i) => {
        text.setAttribute("x", String(nodes[i].x!));
        text.setAttribute("y", String(nodes[i].y!));
      });
    });

    simulation.alpha(1).restart();
    // 运行一段时间后停止
    setTimeout(() => simulation.stop(), 10000);

    return () => simulation.stop();
  }, [data, navigate]);

  useEffect(() => {
    if (data) runSimulation();
  }, [data, runSimulation]);

  if (loading) {
    return <div className="empty-state"><p>加载中...</p></div>;
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">&#x1F578;</div>
        <h2>暂无图谱数据</h2>
        <p>需要更多对话和标签来构建知识图谱</p>
      </div>
    );
  }

  const convCount = data.nodes.filter(n => n.type === "conversation").length;
  const tagCount = data.nodes.filter(n => n.type === "tag").length;

  return (
    <div className="graph-page">
      <div className="page-header">
        <h2>知识图谱</h2>
        <p className="page-desc">
          对话节点（彩色）通过标签和语义相似度自动关联
          · {convCount} 段对话 · {tagCount} 个标签 · {data.edges.length} 条关联
        </p>
      </div>

      {/* 图例 */}
      <div className="graph-legend">
        <span className="legend-item">
          <span className="legend-line" style={{ background: "#3b82f6" }} />
          标签重叠
        </span>
        <span className="legend-item">
          <span className="legend-line" style={{ background: "#8b5cf6" }} />
          语义相似
        </span>
        <span className="legend-item">
          <span className="legend-line" style={{ background: "#e5e7eb" }} />
          标签关联
        </span>
      </div>

      {/* 悬停提示 */}
      {hovered && (
        <div className="graph-tooltip">
          <strong>{hovered.type === "conversation" ? "对话" : "标签"}</strong>
          : {hovered.label}
          {hovered.type === "conversation" && (
            <span className="hint">（点击查看详情）</span>
          )}
        </div>
      )}

      {/* SVG 画布 */}
      <div ref={containerRef} className="graph-canvas">
        <svg ref={svgRef} />
      </div>
    </div>
  );
}
