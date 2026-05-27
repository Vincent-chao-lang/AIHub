# AI Memory Hub → Personal AI OS

> 跨平台 AI 长期记忆系统。记录、检索、关联你的所有 AI 对话。
>
> 最终形态：**无论使用哪个 AI 平台，都带着你的全部上下文。**

---

## 为什么需要它

你同时用 ChatGPT、Claude、DeepSeek、Kimi、Gemini。每个平台都有自己的对话历史，但它们彼此完全隔离。

**三个痛点：**

```
1. 碎片化
   "关于 RAG 架构，我在 ChatGPT 上聊过方案设计，
    在 Claude 上聊过代码实现，在 DeepSeek 上对比过向量数据库——
    但它们散落在三个平台里，无法拼成完整图景。"

2. 无法统一检索
   "我记得问过一个关于 Prompt 优化的技巧，但在哪个平台问的？
    ChatGPT？ Claude？ DeepSeek？——只能一个一个翻。"

3. 无法形成知识沉淀和关联
   "上周聊的 Python 装饰器和三个月前聊的 FastAPI 中间件，
    底层机制一模一样。但我根本没意识到它们之间有联系，
    更谈不上让 AI 基于这段认知积累来帮我。"
```

**AI Memory Hub 做一件事：在你的所有 AI 平台下面，铺一层统一的知识层。**

```
ChatGPT 对话 ↘
Claude 对话   → 自动汇聚 → 跨平台语义搜索 → 智能关联 → 知识图谱
DeepSeek 对话 ↗
Kimi 对话    ↗              你问过的，想过的，学过的，
Gemini 对话  ↗              全部沉淀为一套可检索、可关联的知识体系。
```

---
## 核心交互：侧边栏随身记忆

```
在任意 AI 平台页面（ChatGPT/Claude/DeepSeek...）
    → 点击浏览器工具栏 🧠 图标
    → 侧边栏滑出
    → 输入你想聊的话题
    → 图谱驱动检索 + 生成上下文
    → 一键复制 → 粘贴到对话框

你的记忆不再被锁在一个 App 里，在所有地方随时可用。
```

---

## 随着数据积累涌现的价值

### 第一阶段：跨平台统一搜索 ✅
```
"我之前讨论过向量数据库吗？"
→ ChatGPT: RAG 系统中如何选择向量数据库
→ 跨多个个平台检索，秒级返回，不需要记住在哪个平台聊的。
```

### 第二阶段：知识碎片自动缝合 ✅
```
自动摘要 + 标签 + 项目聚合 → 系统自动聚类出你关心的核心领域
知识图谱 → 可视化你的思维关联网络
"Python 闭包 ←→ Python 装饰器"  "RAG 设计 ←→ 向量数据库选型"
```

### 第三阶段：图谱驱动上下文注入 ✅
```
侧边栏/上下文助手 → 输入话题
→ 向量搜索定位种子对话 → 知识图谱遍历发现 N 层关联链
→ 生成结构化上下文 → 一键注入任意 AI 平台

AI 不再从零开始认识你：
"你上次搞 RAG 选了 ChromaDB，Python 装饰器的闭包原理可以直接用在这里。"
```

### 终极形态：从"工具"到"外脑"

```
无论使用哪个 AI 平台，都可以带着你的全部上下文来服务你 —— Personal AI OS
```

---

## 当前状态

### 已完成功能

| 模块 | 功能 | 状态 |
|------|------|------|
| **采集** | 浏览器插件（ChatGPT/Claude/Gemini/Kimi/DeepSeek） | ✅ |
| **采集** | 流式响应去重、DOM 元素级增量捕获 | ✅ |
| **存储** | FastAPI + SQLite 本地后端 | ✅ |
| **存储** | BGE-small 向量 embedding + ChromaDB 语义搜索 | ✅ |
| **展示** | Timeline 对话时间线（按对话聚合） | ✅ |
| **展示** | 对话详情 + 相关对话推荐 | ✅ |
| **展示** | React 前端，暗色模式自适应 | ✅ |
| **智能** | 自动摘要（标题/标签/摘要） | ✅ |
| **智能** | 项目聚合（标签重叠聚类） | ✅ |
| **智能** | 知识图谱（D3.js 力导向图可视化） | ✅ |
| **智能** | 上下文助手（一键生成可注入上下文） | ✅ |
| **智能** | 图谱驱动上下文注入（向量定位种子 → 图谱遍历发现关联链） | ✅ |
| **OS** | Personal AI OS 侧边栏（任意 AI 平台页面，随时唤起记忆） | ✅ |
| **工具** | 一键启动脚本 `start.sh` | ✅ |

### 架构

```
                    ┌─────────────────────────┐
                    │  Chrome 侧边栏            │
                    │  在任意 AI 平台页面可用     │
                    │  输入话题 → 图谱驱动上下文   │
                    │  一键复制注入               │
                    └────────────┬────────────┘
                                 │ POST /context
                                 ↓
┌──────────────────────────────────────────┐
│  浏览器插件 (Chrome Extension)             │
│  5 平台 DOM 监听 → 流式去重 → 自动采集       │
└──────────────┬───────────────────────────┘
               │ POST /messages
               ↓
┌──────────────────────────────────────────┐
│  本地后端 (FastAPI + SQLite + ChromaDB)    │
│  ┌─────────────────────────────────────┐ │
│  │ 消息存储 → embedding → 自动摘要      │ │
│  │ 语义搜索 → 图谱遍历 → 上下文生成     │ │
│  │ 项目聚合 → 对话关联 → 10 个 API      │ │
│  └─────────────────────────────────────┘ │
└──────────────┬───────────────────────────┘
               │
               ↓
┌──────────────────────────────────────────┐
│  前端 (React + Vite + D3.js)              │
│  时间线 / 搜索 / 项目 / 上下文 / 图谱       │
└──────────────────────────────────────────┘
```

---

## 快速开始

```bash
# 1. 一键启动前后端
./start.sh

# 2. 加载浏览器插件
# Chrome → chrome://extensions → 开发者模式
# → 加载已解压的扩展程序 → 选择 extension/ 目录

# 3. 使用
# 打开任意 AI 平台 → 点击 🧠 图标 → 侧边栏唤起记忆
# 或访问 http://localhost:5173 查看完整面板
```

### 页面导航

| URL | 功能 |
|-----|------|
| `http://localhost:5173` | 时间线首页 |
| `http://localhost:5173/projects` | 项目聚合 |
| `http://localhost:5173/context` | 上下文助手 |
| `http://localhost:5173/graph` | 知识图谱 |

---

## 项目结构

```
AIHub/
├── start.sh              # 一键启动脚本
├── backend/              # FastAPI + SQLite + ChromaDB
│   ├── main.py           # 入口 (port 8712)
│   ├── api/routes.py     # 12 个 API 端点
│   ├── models/           # 数据模型（Graph / Context / Message）
│   ├── db/               # SQLite + ChromaDB 客户端
│   └── services/         # embedding / 摘要 / 搜索 / 上下文生成
├── extension/            # Chrome 插件 (Manifest V3)
│   ├── content/          # 5 平台 DOM 监听（流式去重）
│   ├── background/       # Service Worker + 侧边栏管理
│   ├── sidepanel/        # Personal AI OS 侧边栏（随身记忆）
│   └── shared/           # 统一消息格式
├── frontend/             # React + Vite + TypeScript + D3.js
│   └── src/
│       ├── pages/        # Home / Conversation / Projects / Context / Graph
│       ├── components/   # TimelineCard / SearchBar / Layout
│       ├── api/          # API 客户端
│       └── types/        # TypeScript 类型定义
└── README.md
```

---

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/messages` | 插件上传消息（自动 embedding + 摘要） |
| GET | `/timeline` | 时间线（按对话聚合） |
| GET | `/conversations/{id}` | 对话详情 |
| GET | `/conversations/{id}/related` | 相关对话推荐 |
| POST | `/search` | 语义搜索（向量 + 关键词回退） |
| POST | `/summarize/{id}` | 手动触发摘要 |
| POST | `/context` | 生成可注入上下文 |
| GET | `/projects` | 项目聚合 |
| GET | `/graph` | 知识图谱数据 |
| GET | `/stats` | 统计信息 |

---

## 设计原则

1. **插件无状态** — 只观察、提取、转发，不在插件里做 AI
2. **本地优先** — 数据、embedding、搜索全部本地，保护隐私
3. **不改变习惯** — 不做新的聊天框，不强迫迁移工作流
4. **记忆随身** — 侧边栏跟随你到所有 AI 平台，随时唤起
5. **增量涌现** — 每条对话都是孤立的，汇聚后才产生价值
6. **图即认知** — 知识图谱 = 你的思维地图 = 系统理解你的数据结构

---

## 路线图

- [x] Phase 1 — AI 聊天记录聚合器（5 平台 + Timeline + 流式去重）
- [x] Phase 2 — AI 记忆系统（BGE embedding + ChromaDB 语义搜索 + 自动摘要）
- [x] Phase 3 — 智能关联（相关对话推荐 + 标签聚类项目聚合）
- [x] Phase 4 — 知识图谱（D3.js 力导向图 + 对话-标签关联网络）
- [x] Phase 5 — 上下文注入（向量搜索定位种子 → 图谱遍历发现关联链 → 一键注入）
- [ ] Phase 6 — Tauri 桌面壳打包
- [ ] Phase 7 — 更多信息源（微信、邮件、GitHub、Notion、Obsidian）
- [x] Phase 8 — Personal AI OS（Chrome 侧边栏随身记忆，任意 AI 平台随时唤起图谱驱动上下文）
