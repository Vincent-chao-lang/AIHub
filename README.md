# AI Memory Hub

> 一个自动记录和检索 AI 对话历史的本地长期记忆系统。
>
> 不改变你使用任何 AI 平台的习惯，只帮你**记住**。

---

## 为什么需要它

每次打开 ChatGPT、Claude、DeepSeek，都是全新对话。AI 不认识你，你也不记得上次聊到哪了。

**AI Memory Hub 做一件事：在你的所有 AI 平台下面，铺一层统一的记忆。**

```
没有它：
  ChatGPT 对话 → 关闭标签页 → 永远消失
  Claude 对话   → 关闭标签页 → 永远消失
  DeepSeek 对话 → 关闭标签页 → 永远消失

有了它：
  ChatGPT 对话 ↘
  Claude 对话   → 自动汇聚 → 跨平台搜索 → 智能关联 → 永久记忆
  DeepSeek 对话 ↗
```

---

## 随着数据积累涌现的价值

### 第一阶段：跨平台统一搜索（你现在在这里）
```
"我之前讨论过向量数据库吗？"
→ ChatGPT: RAG 系统中如何选择向量数据库
→ 跨 3 个平台检索，秒级返回，不需要记住在哪个平台聊的。
```

### 第二阶段：知识碎片自动缝合
```
50+ 段对话 → 系统自动聚类出你关心的核心领域
200+ 段对话 → 看到你对某个问题的理解怎么一步步深入
"你上周聊的 X 和你三个月前聊的 Y，其实是同一个问题的不同侧面"
```

### 第三阶段：Personal AI Context
```
500+ 段对话 → 任何新对话开始前，自动注入你的历史上下文

AI 不再从零开始认识你：
"你上次搞 RAG 选了 ChromaDB，这次要直接基于那个继续吗？"
"你过去 3 个月反复讨论 Agent 架构，我帮你整理了一份设计总结。"
```

### 终极形态：从"工具"到"外脑"

```
现在：每次打开 AI 都是全新对话
未来：AI 带着你的全部上下文来服务你 —— Personal AI OS
```

---

## 当前状态（MVP）

### 已完成

| 功能 | 状态 |
|------|------|
| 5 平台浏览器插件（ChatGPT/Claude/Gemini/Kimi/DeepSeek） | ✅ |
| 本地后端（FastAPI + SQLite） | ✅ |
| Timeline 对话时间线 | ✅ |
| 对话详情 + 相关对话推荐 | ✅ |
| BGE 向量 embedding + ChromaDB 语义搜索 | ✅ |
| 自动摘要（标题/标签/摘要） | ✅ |
| 项目聚合（标签重叠聚类） | ✅ |
| React 前端（暗色模式自适应） | ✅ |

### 架构

```
┌─────────────────────────────────────┐
│  浏览器插件 (Chrome Extension)        │
│  监听 5 个 AI 平台，提取消息            │
└──────────────┬──────────────────────┘
               │ POST localhost:8712
               ↓
┌─────────────────────────────────────┐
│  本地 App (FastAPI + SQLite + ChromaDB)│
│  消息存储 / embedding / 摘要 / 搜索     │
└──────────────┬──────────────────────┘
               │
               ↓
┌─────────────────────────────────────┐
│  前端 (React + Vite)                  │
│  Timeline / 搜索 / 项目 / 对话详情      │
└─────────────────────────────────────┘
```

---

## 快速开始

```bash
# 1. 启动后端
cd backend
pip install -r requirements.txt
python main.py
# → http://127.0.0.1:8712

# 2. 启动前端
cd frontend
npm install
npm run dev
# → http://localhost:5173

# 3. 加载浏览器插件
# Chrome → chrome://extensions → 开发者模式
# → 加载已解压的扩展程序 → 选择 extension/ 目录

# 4. 正常使用 AI 平台，对话自动汇聚
```

---

## 项目结构

```
AIHub/
├── backend/            # FastAPI + SQLite + ChromaDB
│   ├── api/            # 9 个 API 端点
│   ├── models/         # 数据模型
│   ├── db/             # SQLite + ChromaDB 客户端
│   └── services/       # embedding / 摘要 / 搜索
├── extension/          # Chrome 插件 (Manifest V3)
│   ├── content/        # 5 个平台的 DOM 监听脚本
│   ├── background/     # Service Worker
│   └── shared/         # 统一消息格式
├── frontend/           # React + Vite + TypeScript
│   └── src/
│       ├── pages/      # Timeline / 对话详情 / 项目
│       └── components/ # TimelineCard / SearchBar / Layout
└── README.md
```

---

## 设计原则

1. **插件无状态** — 只观察、提取、转发，不在插件里做 AI
2. **本地优先** — 数据、embedding、搜索全部本地，保护隐私
3. **不改变习惯** — 不做新的聊天框，不强迫迁移工作流
4. **增量涌现** — 每条对话都是孤立的，汇聚后才产生价值

---

## 未来方向

- Tauri 桌面壳打包
- 更多平台支持（微信、邮件、GitHub、Notion、Obsidian）
- LLM 驱动的自动上下文注入
- Personal AI OS — 统一记忆 → AI 理解 → 长期上下文
