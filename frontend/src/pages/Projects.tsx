import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { ProjectGroup } from "../types";
import { PLATFORM_LABELS, PLATFORM_COLORS } from "../types";

export default function Projects() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProjects = async () => {
    try {
      setError(null);
      const data = await api.getProjects();
      setProjects(data);
    } catch {
      setError("无法加载项目数据");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  if (loading) {
    return <div className="empty-state"><p>加载中...</p></div>;
  }

  if (error) {
    return (
      <div className="empty-state">
        <h2>加载失败</h2>
        <p>{error}</p>
        <button className="retry-btn" onClick={loadProjects}>重试</button>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">&#x1F4C1;</div>
        <h2>暂无项目</h2>
        <p>当你有足够的对话记录后，系统会自动将相关对话聚合为项目</p>
      </div>
    );
  }

  return (
    <div className="projects-page">
      <div className="page-header">
        <h2>项目聚合</h2>
        <p className="page-desc">按主题自动分组你的 AI 对话</p>
      </div>

      <div className="projects-grid">
        {projects.map((project) => (
          <div key={project.name} className="project-card">
            <div className="project-header">
              <h3>{project.name}</h3>
              <span className="project-count">{project.total_messages} 个对话</span>
            </div>
            {project.keywords.length > 0 && (
              <div className="project-keywords">
                {project.keywords.map((kw) => (
                  <span key={kw} className="tag">{kw}</span>
                ))}
              </div>
            )}
            <div className="project-conversations">
              {project.conversations.map((conv) => (
                <div
                  key={conv.conversation_id}
                  className="project-conv-item"
                  onClick={() => navigate(`/conversation/${conv.conversation_id}`)}
                >
                  <span
                    className="platform-dot"
                    style={{ backgroundColor: PLATFORM_COLORS[conv.platform] || "#666" }}
                  />
                  <span className="project-conv-title">
                    {conv.title || "未命名对话"}
                  </span>
                  <span className="project-conv-platform">
                    {PLATFORM_LABELS[conv.platform] || conv.platform}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
