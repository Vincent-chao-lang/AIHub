// Gemini 页面监听器 (gemini.google.com)
(function () {
  const PLATFORM = "gemini";

  const sentElements = new WeakSet();
  const contentHistory = new Map();

  function getConversationId() {
    const p = window.location.pathname;
    const m = p.match(/\/([a-zA-Z0-9_-]{15,})/);
    if (m) return m[1];
    return p.replace(/\//g, "_").slice(1, 50) || "unknown";
  }

  function scanMessages() {
    // Gemini 消息容器
    let els = document.querySelectorAll('[data-message-content], [class*="message-content"]');
    if (els.length === 0) {
      els = document.querySelectorAll('.response-content, .query-content');
    }
    if (els.length === 0) {
      els = document.querySelectorAll('[class*="bubble"], [class*="turn"]');
    }
    if (els.length === 0) {
      const main = document.querySelector('main, [role="main"]');
      if (main) els = main.querySelectorAll('p, .markdown');
    }
    if (els.length === 0) return;

    const conversationId = getConversationId();
    let newSent = 0;

    els.forEach(el => {
      const text = el.innerText?.trim() || "";
      if (text.length < 3) return;
      if (sentElements.has(el)) return;

      // 识别角色
      let role = null;
      const classStr = el.className.toLowerCase();
      if (classStr.includes('query') || classStr.includes('user') || classStr.includes('human')) {
        role = "user";
      } else if (classStr.includes('response') || classStr.includes('assistant') || classStr.includes('model') || classStr.includes('gemini')) {
        role = "assistant";
      } else {
        role = el.closest('[class*="query"]') || el.closest('[class*="user"]') ? "user" : "assistant";
      }

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
      console.log(`[AI Memory Hub] Gemini 新消息: ${newSent} 条, 对话: ${conversationId}`);
    }
  }

  setInterval(scanMessages, 1000);

  let timer = null;
  const observer = new MutationObserver(() => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(scanMessages, 800);
  });

  observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  setTimeout(scanMessages, 3000);
  console.log("[AI Memory Hub] Gemini 监听已启动");
})();
