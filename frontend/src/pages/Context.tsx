import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { ContextResponse } from "../types";
import { PLATFORM_LABELS, PLATFORM_COLORS } from "../types";

export default function Context() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<ContextResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [maxTokens, setMaxTokens] = useState(2000);

  const handleGenerate = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await api.getContext(query.trim(), maxTokens);
      setResult(data);
      setCopied(false);
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!result?.context_text) return;
    await navigator.clipboard.writeText(result.context_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="context-page">
      <div className="page-header">
        <h2>上下文助手</h2>
        <p className="page-desc">
          输入你即将讨论的话题，系统自动检索历史相关对话并生成上下文，
          一键复制粘贴到任意 AI 平台，让 AI 基于你的历史来回答。
        </p>
      </div>

      {/* 输入区 */}
      <div className="context-input-area">
        <textarea
          className="context-textarea"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="例如：我想讨论 RAG 系统的优化方案"
          rows={3}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              handleGenerate();
            }
          }}
        />
        <div className="context-controls">
          <div className="token-selector">
            <span className="token-label">长度</span>
            {[1000, 2000, 4000, 8000, 16000, 32000, 64000, 128000].map((n) => (
              <button
                key={n}
                className={`token-btn ${maxTokens === n ? "active" : ""}`}
                onClick={() => setMaxTokens(n)}
              >
                {n >= 1000 ? `${n / 1000}K` : n}
              </button>
            ))}
          </div>
          {result && (
            <span className="token-estimate">
              约 {result.estimated_tokens} tokens
            </span>
          )}
        </div>
        <button
          className="context-generate-btn"
          onClick={handleGenerate}
          disabled={loading || !query.trim()}
        >
          {loading ? "检索中..." : "生成上下文"}
        </button>
      </div>

      {/* 结果区 */}
      {result && (
        <div className="context-result">
          {result.context_text ? (
            <>
              {/* 关键发现 */}
              {result.key_points.length > 0 && (
                <div className="context-keypoints">
                  <h4>关键历史发现</h4>
                  <ul>
                    {result.key_points.map((point, i) => (
                      <li key={i}>{point}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 图谱遍历路径 */}
              {result.graph_traversal && result.graph_traversal.length > 0 && (
                <div className="context-traversal">
                  <h4>图谱推理路径</h4>
                  {result.graph_traversal.map((tp, i) => (
                    <div key={i} className="traversal-item">
                      <div className="traversal-header">
                        <span className={`traversal-badge ${tp.distance === 0 ? "seed" : "discovered"}`}>
                          {tp.distance === 0 ? "直接匹配" : `${tp.distance} 跳关联`}
                        </span>
                        <span className="traversal-score">
                          强度 {(tp.score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="traversal-title">
                        [{PLATFORM_LABELS[tp.platform] || tp.platform}] {tp.title}
                      </div>
                      {tp.path.length > 1 && (
                        <div className="traversal-path">
                          {tp.path.map((step, j) => (
                            <span key={j} className="traversal-step">
                              {step}
                              {j < tp.path.length - 1 && <span className="step-arrow"> → </span>}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* 上下文文本 */}
              <div className="context-output">
                <div className="context-output-header">
                  <h4>可注入上下文</h4>
                  <button className="copy-btn" onClick={handleCopy}>
                    {copied ? "已复制 ✓" : "复制到剪贴板"}
                  </button>
                </div>
                <pre className="context-text">{result.context_text}</pre>
              </div>

              {/* 关联对话 */}
              {result.related.length > 0 && (
                <div className="context-related">
                  <h4>关联对话</h4>
                  {result.related.map((conv) => (
                    <div
                      key={conv.conversation_id}
                      className="related-card"
                      onClick={() => navigate(`/conversation/${conv.conversation_id}`)}
                    >
                      <div className="related-header">
                        <span
                          className="platform-badge"
                          style={{
                            backgroundColor: PLATFORM_COLORS[conv.platform] || "#666",
                          }}
                        >
                          {PLATFORM_LABELS[conv.platform] || conv.platform}
                        </span>
                      </div>
                      <div className="related-title">{conv.title || "未命名对话"}</div>
                      <div className="related-meta">
                        {conv.message_count} 条消息 |{" "}
                        {new Date(conv.latest_timestamp).toLocaleDateString("zh-CN")}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="empty-state">
              <p>没有找到相关的历史对话</p>
              <p className="hint">这是全新话题，继续探索吧</p>
            </div>
          )}
        </div>
      )}

      {/* 空状态提示 */}
      {!result && !loading && (
        <div className="context-hint">
          <div className="empty-icon">&#x1F4A1;</div>
          <h3>如何使用</h3>
          <div className="hint-steps">
            <div className="hint-step">
              <span className="step-num">1</span>
              <span>输入你准备在 AI 平台讨论的话题</span>
            </div>
            <div className="hint-step">
              <span className="step-num">2</span>
              <span>向量搜索定位种子对话，知识图谱遍历发现 N 层关联链</span>
            </div>
            <div className="hint-step">
              <span className="step-num">3</span>
              <span>一键复制上下文，粘贴到 ChatGPT/Claude/DeepSeek 等任意平台</span>
            </div>
            <div className="hint-step">
              <span className="step-num">4</span>
              <span>AI 带着你的全部思维关联来回答</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
