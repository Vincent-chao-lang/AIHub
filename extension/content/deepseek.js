// DeepSeek 页面监听器 (chat.deepseek.com)
(function () {
  const PLATFORM = "deepseek";

  // 追踪每个 DOM 元素是否已发送，以及内容变化历史（用于流式去重）
  const sentElements = new WeakSet();
  const contentHistory = new Map(); // element → {content, count}

  function getConversationId() {
    const p = window.location.pathname;
    const m = p.match(/\/([a-f0-9-]{20,})/);
    if (m) return m[1];
    return p.replace(/\//g, "_").slice(1, 50) || "unknown";
  }

  function scanMessages() {
    const els = document.querySelectorAll('.ds-message');
    if (els.length === 0) return;

    const conversationId = getConversationId();
    let newSent = 0;

    els.forEach(el => {
      const text = el.innerText?.trim() || "";
      if (text.length < 3) return;

      const isAssistant = el.querySelector('.ds-assistant-message-main-content') !== null;
      const role = isAssistant ? "assistant" : "user";

      // 已成功发送过的元素，跳过
      if (sentElements.has(el)) return;

      if (isAssistant) {
        // AI 消息：检查内容是否已稳定（流式响应去重）
        const prev = contentHistory.get(el);
        if (prev && prev.content === text) {
          // 内容连续两次相同 → 流式已完成，可以发送
          if (prev.count >= 1) {
            contentHistory.delete(el);
            sentElements.add(el);
            sendToAPI({
              platform: PLATFORM,
              conversation_id: conversationId,
              role: "assistant",
              content: text,
              timestamp: new Date().toISOString(),
            });
            newSent++;
          } else {
            // 第一次稳定，再确认一轮
            prev.count++;
          }
        } else {
          // 内容变化中或首次出现 → 记录当前状态
          contentHistory.set(el, { content: text, count: 0 });
        }
      } else {
        // 用户消息：直接发送（不存在流式问题）
        sentElements.add(el);
        contentHistory.delete(el);
        sendToAPI({
          platform: PLATFORM,
          conversation_id: conversationId,
          role: "user",
          content: text,
          timestamp: new Date().toISOString(),
        });
        newSent++;
      }
    });

    if (newSent > 0) {
      console.log(`[AI Memory Hub] DeepSeek 新消息: ${newSent} 条, 对话: ${conversationId}`);
    }
  }

  // 定期扫描：每秒一次（应对流式响应延迟）
  setInterval(scanMessages, 1000);

  // MutationObserver 作为补充：DOM 变化时触发
  let timer = null;
  const observer = new MutationObserver(() => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(scanMessages, 800);
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
  });

  setTimeout(scanMessages, 2000);
  console.log("[AI Memory Hub] DeepSeek 监听已启动 (v0.3)");
})();
