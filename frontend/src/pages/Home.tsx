import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { TimelineGroup, SearchResult } from "../types";
import { PLATFORM_LABELS, PLATFORM_COLORS } from "../types";
import TimelineCard from "../components/TimelineCard";
import SearchBar from "../components/SearchBar";

export default function Home() {
  const navigate = useNavigate();
  const [timeline, setTimeline] = useState<TimelineGroup[]>([]);
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [platform, setPlatform] = useState<string | undefined>();

  const loadTimeline = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getTimeline(platform);
      setTimeline(data);
      setSearchResults(null);
    } catch {
      setError("无法连接到本地服务，请确保 AI Memory Hub 后端已启动");
    } finally {
      setLoading(false);
    }
  }, [platform]);

  useEffect(() => {
    loadTimeline();
  }, [loadTimeline]);

  useEffect(() => {
    const interval = setInterval(loadTimeline, 5000);
    return () => clearInterval(interval);
  }, [loadTimeline]);

  const handleSearch = async (query: string) => {
    try {
      const results = await api.search(query);
      setSearchResults(results);
    } catch {
      setError("搜索失败");
    }
  };

  const clearSearch = () => {
    setSearchResults(null);
    loadTimeline();
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    if (dateStr === today.toISOString().slice(0, 10)) return "今天";
    if (dateStr === yesterday.toISOString().slice(0, 10)) return "昨天";
    return date.toLocaleDateString("zh-CN", {
      month: "long",
      day: "numeric",
      weekday: "long",
    });
  };

  if (error) {
    return (
      <div className="home-page">
        <SearchBar onSearch={handleSearch} />
        <div className="empty-state">
          <div className="empty-icon">&#x1F4E1;</div>
          <h2>无法连接</h2>
          <p>{error}</p>
          <button className="retry-btn" onClick={loadTimeline}>重试</button>
        </div>
      </div>
    );
  }

  return (
    <div className="home-page">
      <SearchBar onSearch={handleSearch} />

      <div className="platform-filters">
        {searchResults && (
          <button className="filter-btn active" onClick={clearSearch}>
            &#x2190; 返回时间线
          </button>
        )}
        {!searchResults && (
          <>
            <button
              className={`filter-btn ${!platform ? "active" : ""}`}
              onClick={() => setPlatform(undefined)}
            >
              全部
            </button>
            {["chatgpt", "claude", "gemini", "kimi", "deepseek"].map((p) => (
              <button
                key={p}
                className={`filter-btn ${platform === p ? "active" : ""}`}
                onClick={() => setPlatform(p)}
              >
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </button>
            ))}
          </>
        )}
      </div>

      {/* 搜索结果 */}
      {searchResults && (
        <div className="search-results">
          <h3>搜索结果（{searchResults.length} 条）</h3>
          {searchResults.length === 0 ? (
            <div className="empty-state"><p>没有找到相关对话</p></div>
          ) : (
            searchResults.map((r) => (
              <div
                key={r.message.id}
                className="timeline-card"
                onClick={() => navigate(`/conversation/${r.message.conversation_id}`)}
              >
                <div className="card-header">
                  <span
                    className="platform-badge"
                    style={{ backgroundColor: PLATFORM_COLORS[r.message.platform] || "#666" }}
                  >
                    {PLATFORM_LABELS[r.message.platform] || r.message.platform}
                  </span>
                  <span className="card-time">
                    相似度 {(r.score * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="card-title">{r.message.title || r.message.content.slice(0, 50)}</div>
                <div className="card-preview">
                  {r.message.role === "user" ? "你：" : "AI："}
                  {r.message.content.slice(0, 100)}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Timeline：按对话聚合 */}
      {!searchResults && (
        <div className="timeline">
          {loading && timeline.length === 0 && (
            <div className="empty-state"><p>加载中...</p></div>
          )}
          {!loading && timeline.length === 0 && (
            <div className="empty-state">
              <div className="empty-icon">&#x1F4AC;</div>
              <h2>还没有对话记录</h2>
              <p>开始使用 AI 平台，对话将自动出现在这里</p>
            </div>
          )}
          {timeline.map((group) => (
            <div key={group.date} className="timeline-group">
              <div className="timeline-date">{formatDate(group.date)}</div>
              <div className="timeline-divider" />
              <div className="timeline-cards">
                {group.conversations.map((conv) => (
                  <TimelineCard key={conv.conversation_id} conversation={conv} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
