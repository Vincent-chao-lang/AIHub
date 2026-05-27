// ChatGPT 页面监听器
(function () {
  const PLATFORM = "chatgpt";

  const sentElements = new WeakSet();
  const contentHistory = new Map();

  function getConversationId() {
    const p = window.location.pathname;
    let m = p.match(/\/c\/([a-zA-Z0-9_-]+)/);
    if (m) return m[1];
    m = p.match(/\/([a-zA-Z0-9_-]{20,})/);
    if (m) return m[1];
    return p.replace(/\//g, "_").slice(1, 50) || "unknown";
  }

  function scanMessages() {
    // 多策略查找消息元素
    let els = document.querySelectorAll('[data-message-author-role]');
    if (els.length === 0) {
      els = document.querySelectorAll('article[data-testid]');
    }
    if (els.length === 0) return;

    const conversationId = getConversationId();
    let newSent = 0;

    els.forEach(el => {
      const text = el.innerText?.trim() || "";
      if (text.length < 3) return;
      if (sentElements.has(el)) return;

      // 识别角色
      let role = el.getAttribute('data-message-author-role');
      if (!role) {
        const hasModel = el.querySelector('[data-message-model-slug]');
        const hasUser = el.querySelector('[data-message-author-role="user"]');
        role = hasModel ? "assistant" : hasUser ? "user" : null;
      }
      if (!role) return;

      if (role === "assistant") {
        const prev = contentHistory.get(el);
        if (prev && prev.content === text) {
          if (prev.count >= 1) {
            contentHistory.delete(el);
            sentElements.add(el);
            sendToAPI({ platform: PLATFORM, conversation_id: conversationId, role: "assistant", content: text, timestamp: new Date().toISOString() });
            newSent++;
          } else {
            prev.count++;
          }
        } else {
          contentHistory.set(el, { content: text, count: 0 });
        }
      } else {
        sentElements.add(el);
        contentHistory.delete(el);
        sendToAPI({ platform: PLATFORM, conversation_id: conversationId, role: "user", content: text, timestamp: new Date().toISOString() });
        newSent++;
      }
    });

    if (newSent > 0) {
      console.log(`[AI Memory Hub] ChatGPT 新消息: ${newSent} 条, 对话: ${conversationId}`);
    }
  }

  setInterval(scanMessages, 1000);

  let timer = null;
  const observer = new MutationObserver(() => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(scanMessages, 800);
  });

  observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  setTimeout(scanMessages, 2000);
  console.log("[AI Memory Hub] ChatGPT 监听已启动");
})();
