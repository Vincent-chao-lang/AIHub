// Personal AI OS 侧边栏逻辑

document.addEventListener("DOMContentLoaded", () => {
  const queryEl = document.getElementById("query");
  const generateBtn = document.getElementById("generateBtn");
  const copyBtn = document.getElementById("copyBtn");
  const settingsBtn = document.getElementById("settingsBtn");
  const resultDiv = document.getElementById("result");
  const statusEl = document.getElementById("status");
  const contextText = document.getElementById("contextText");
  const keypointsDiv = document.getElementById("keypoints");
  const traversalDiv = document.getElementById("traversal");
  const traversalList = document.getElementById("traversalList");
  const toast = document.getElementById("toast");
  const userBadge = document.getElementById("userBadge");
  const tokenEstimate = document.getElementById("tokenEstimate");
  const tokenBtns = document.querySelectorAll(".token-btn");

  // 加载用户标识
  chrome.storage.local.get(["userId"], (result) => {
    userBadge.textContent = result.userId ? `@${result.userId}` : "";
  });

  let maxTokens = 2000;

  // Token 长度选择
  tokenBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tokenBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      maxTokens = parseInt(btn.dataset.tokens, 10);
    });
  });

  // ESC 转义
  function esc(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  // 生成上下文
  async function generate() {
    const query = queryEl.value.trim();
    if (!query) return;

    generateBtn.disabled = true;
    generateBtn.textContent = "检索中...";
    statusEl.style.display = "none";

    try {
      const data = await chrome.runtime.sendMessage({
        type: "GET_CONTEXT",
        query: query,
        maxTokens: maxTokens,
      });

      if (!data || data.error) {
        throw new Error(data?.error || "请求失败");
      }

      if (!data.context_text) {
        statusEl.style.display = "block";
        statusEl.textContent = "未找到相关记忆，这是全新话题。";
        statusEl.className = "status";
        generateBtn.disabled = false;
        generateBtn.textContent = "检索我的记忆";
        return;
      }

      contextText.textContent = data.context_text;
      resultDiv.style.display = "block";
      statusEl.style.display = "none";
      tokenEstimate.textContent = data.estimated_tokens ? `约 ${data.estimated_tokens} tokens` : "";

      // 关键发现
      if (data.key_points && data.key_points.length > 0) {
        keypointsDiv.style.display = "block";
        keypointsDiv.innerHTML = "<strong>关键历史发现：</strong><ul>" +
          data.key_points.map(p => `<li>${esc(p)}</li>`).join("") + "</ul>";
      } else {
        keypointsDiv.style.display = "none";
      }

      // 图谱遍历
      if (data.graph_traversal && data.graph_traversal.length > 0) {
        traversalDiv.style.display = "block";
        traversalList.innerHTML = data.graph_traversal.map(tp => {
          const badge = tp.distance === 0
            ? '<span class="traversal-badge seed">直接匹配</span>'
            : `<span class="traversal-badge discovered">${tp.distance} 跳关联</span>`;
          const pathHtml = tp.path.length > 1
            ? `<div class="traversal-path">${tp.path.map(s => esc(s)).join(" → ")}</div>`
            : "";
          return `<div class="traversal-item">
            ${badge}
            <span style="margin-left:6px;font-size:10px;color:var(--text-secondary)">
              强度 ${Math.round(tp.score * 100)}%
            </span>
            <div class="traversal-title">[${tp.platform}] ${esc(tp.title)}</div>
            ${pathHtml}
          </div>`;
        }).join("");
      } else {
        traversalDiv.style.display = "none";
      }

      generateBtn.textContent = "检索我的记忆";

    } catch (e) {
      statusEl.style.display = "block";
      statusEl.textContent = "无法连接本地服务。请确保后端已启动（./start.sh）。";
      statusEl.className = "status error";
    }

    generateBtn.disabled = false;
  }

  // 复制上下文
  async function copyContext() {
    await navigator.clipboard.writeText(contextText.textContent);
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 1500);
  }

  // 事件绑定
  generateBtn.addEventListener("click", generate);
  copyBtn.addEventListener("click", copyContext);
  settingsBtn.addEventListener("click", () => {
    chrome.runtime.openOptionsPage();
  });

  queryEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      generate();
    }
  });
});
