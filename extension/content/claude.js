// Claude 页面监听器 (claude.ai)
(function () {
  const PLATFORM = "claude";

  const sentElements = new WeakSet();
  const contentHistory = new Map();

  function getConversationId() {
    const m = window.location.pathname.match(/\/([a-zA-Z0-9_-]{20,})(?:\/|$)/);
    if (m) return m[1];
    return window.location.pathname.slice(1, 60) || "unknown";
  }

  function scanMessages() {
    // 多策略查找消息容器
    let els = document.querySelectorAll('[data-message-role]');
    if (els.length === 0) {
      els = document.querySelectorAll('.font-user, .font-claude');
    }
    if (els.length === 0) {
      // 新版 Claude React 组件
      const containers = document.querySelectorAll('[data-test-render-count]');
      if (containers.length > 0) {
        els = containers;
      }
    }
    if (els.length === 0) {
      els = document.querySelectorAll('[class*="message"]:not([class*="ds-"])');
    }
    if (els.length === 0) return;

    const conversationId = getConversationId();
    let newSent = 0;

    els.forEach(el => {
      const text = el.innerText?.trim() || "";
      if (text.length < 3) return;
      if (sentElements.has(el)) return;

      // 识别角色
      let role = el.getAttribute('data-message-role');
      if (!role) {
        const classStr = el.className.toLowerCase();
        if (classStr.includes('font-user') || classStr.includes('user')) {
          role = "user";
        } else if (classStr.includes('font-claude') || classStr.includes('assistant') || classStr.includes('claude')) {
          role = "assistant";
        } else {
          const label = el.querySelector('span')?.innerText?.trim() || "";
          if (label === "User" || label === "用户") role = "user";
          else role = "assistant";
        }
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
      console.log(`[AI Memory Hub] Claude 新消息: ${newSent} 条, 对话: ${conversationId}`);
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
  console.log("[AI Memory Hub] Claude 监听已启动");
})();
