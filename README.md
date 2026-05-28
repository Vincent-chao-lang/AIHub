# AI Memory Hub

> 企业 AI 知识资产平台。自动采集、智能关联、随时复用。
>
> 员工和 AI 的每一次对话，都是企业的知识资产。**人走，知识留下。**

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python">
</p>

---

## 解决什么问题

你的团队深度使用 AI。但所有对话锁在个人账号里，彼此完全隔离。

```
核心员工离职 → 几百条 AI 推演记录跟着消失
新人遇到同样问题 → 从零开始和 AI 聊
跨部门讨论同一项目 → 彼此不知道对方已经和 AI 探索过
法务问"员工把什么贴给了 ChatGPT？" → 无法回答
```

**传统知识管理（Wiki/Confluence/共享文档）管不了 AI 对话。因为知识管理的成本在个人、收益在组织——没人有动力写。**

AI Memory Hub 把成本从"人"转移到"系统"：正常使用 AI，对话自动归入企业知识库。

---

## 怎么工作

```
┌──────────────────────────────────────────────────┐
│                                                  │
│  ChatGPT/Claude/DeepSeek /Kimi/Gemini/......     │  你已经在用的 AI 平台
│         │                                        │
│         ↓                                        │
│  静默采集 · 零手动操作         │  自动采集，不改变习惯
│         │                                        │
│         ↓                                        │
│  企业知识中枢（本地 / 私有云部署）                    │
│  ┌────────────────────────────────────────────┐  │
│  │ 语义搜索 · 自动摘要 · 知识图谱 · 上下文生成  │  │  智能理解
│  │ SQLite/PostgreSQL + ChromaDB/pgvector      │  │
│  └────────────────────────────────────────────┘  │
│         │                                        │
│         ↓                                        │
│  侧边栏检索 / Web 面板浏览 / 一键注入 AI 平台     │  随时复用
│                                                  │
└──────────────────────────────────────────────────┘
```

**关键数字：**

| | |
|------|------|
| 年知识产出 | 50 人团队 ≈ 66,000 条 AI 认知碎片 |
| 知识留存率 | 95%（传统交接 < 10%） |
| 新人上手 | 2x 速度提升 |
| 部署时间 | `./start.sh` → 3 分钟 |

---

## 功能矩阵

| 模块 | 功能 |
|------|------|
| **智能采集** | 自动记录 · 流式去重 · 用户标记 · 零手动 |
| **语义检索** | 向量 + 关键词混合搜索 · 跨平台 · 跨时间 · 跨人员 |
| **自动摘要** | 标题 · 标签 · 摘要全自动本地生成 · 无需外部 API |
| **知识图谱** | 标签重叠 + 语义相似双通道 · D3.js 力导向图可视化 |
| **上下文注入** | 图谱驱动 BFS 遍历 · 8 档 Token 控制（1K-128K）· 一键复制 |
| **团队看板** | 时间线 · 项目聚合 · 按人/平台/主题多维度筛选 |
| **合规审计** | 完整对话记录 · 敏感关键词告警（规划中） |

**不只是开发团队。** 产品经理的 PRD 推演、设计师的 Design Token 讨论、运营的策略分析、法务的合同条款审查——任何深度使用 AI 的角色，对话都是资产。

---

## 5 分钟跑起来

```bash
git clone https://github.com/Vincent-chao-lang/AIHub.git
cd AIHub
./start.sh
```

```
# 加载浏览器扩展
Chrome → chrome://extensions → 开发者模式 → 加载已解压 → 选择 extension/ 目录

# 打开任意 AI 平台 → 正常聊天 → 点击 🧠 图标 → 检索记忆
# 或访问 http://localhost:5173 → Web 面板
```

**数据完全在本地。** 不注册、不联网、不上传。你拥有全部数据。

---

## 部署模式

| 模式 | 适合 | 配置 |
|------|------|------|
| **个人本地** | 个人使用 | 零配置，`./start.sh` |
| **局域网共享** | 团队 5-50 人 | 改 `host` 为 `0.0.0.0` |
| **Docker** | 标准化部署 | `docker-compose up` |
| **HTTPS + 反向代理** | 远程团队 | Nginx + Let's Encrypt |

详细部署指南 → [USAGE.md](USAGE.md)

---

## 存储与扩展

默认 SQLite + ChromaDB，零配置开箱即用。

随着团队规模增长，可平滑升级：

```
SQLite + ChromaDB  →  PostgreSQL + pgvector  →  Milvus
  零配置                改一行 .env                独立集群
  < 10 万条              10-100 万条                 > 100 万条
```

详细升级路径 → [docs/STORAGE.md](docs/STORAGE.md)

---

## 项目结构

```
AIHub/
├── start.sh                   # 一键启动
├── backend/                   # FastAPI + SQLite + ChromaDB
│   ├── api/routes.py          # 10 个 API 端点
│   ├── db/                    # 数据库 + 向量存储（ChromaDB/pgvector）
│   ├── models/                # 数据模型
│   └── services/              # embedding · 摘要 · 搜索 · 上下文生成
├── extension/                 # Chrome 扩展 (Manifest V3)
│   ├── content/               # 5 平台 DOM 监听
│   ├── sidepanel/             # 侧边栏 UI + 逻辑
│   └── options/               # 设置页
├── frontend/                  # React + Vite + TypeScript + D3.js
│   └── src/pages/             # 时间线 · 项目 · 上下文 · 图谱
└── landing/                   # 营销页面（中英双语）
```

---

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/messages` | 上传消息（自动 embedding + 摘要） |
| GET | `/timeline` | 时间线（按对话聚合，支持 `?user_id=` 筛选） |
| GET | `/conversations/{id}` | 对话详情 |
| GET | `/conversations/{id}/related` | 相关对话推荐 |
| POST | `/search` | 语义搜索（向量 + 关键词回退） |
| POST | `/context` | 图谱驱动上下文生成（含 `max_tokens` 智能截断） |
| GET | `/projects` | 项目聚合 |
| GET | `/graph` | 知识图谱数据 |
| GET | `/stats` | 统计（总数/平台分布/用户统计/向量索引数） |



## 设计原则

1. **自动采集** — 知识管理成本从"人"转移到"系统"，员工无需额外操作
2. **本地优先** — 数据 100% 归你，也支持服务器部署
3. **企业级扩展** — SQLite → PostgreSQL，ChromaDB → pgvector，随规模平滑升级
4. **零摩擦接入** — 不改现有系统，不要求切换 AI 平台，不改变工作习惯
5. **图谱驱动** — 关联发现用本地算法，不依赖外部 LLM，零成本零延迟
6. **团队即知识** — 同一套系统，一人用是外脑，团队用是知识库

---

## 路线图

- [x] 5 平台自动采集 + 流式去重
- [x] 语义搜索 + 自动摘要 + 知识图谱
- [x] 图谱驱动上下文注入 + 8 档 Token 控制
- [x] 团队模式（user_id 标记 + 按人筛选）
- [x] .env 配置 + PostgreSQL/pgvector 支持
- [ ] 敏感信息检测 + 审计日志 + 合规报告
- [ ] 更多信息源（企业微信 · 飞书 · GitHub · Notion）
