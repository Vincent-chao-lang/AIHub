# AIHub

> 企业 AI 可运营平台。自动采集、智能关联、透明审计。
>
> **人走，知识留下；AI 上线，你接得住。**

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python">
  <img src="https://img.shields.io/badge/version-0.2.0-blue" alt="Version">
</p>

---

## 目录

1. [产品定位](#一产品定位)
2. [V2 升级：从记忆到可运营](#二v2-升级从记忆到可运营)
3. [核心能力](#三核心能力)
4. [5 分钟跑起来](#四-5-分钟跑起来)
5. [采集指南](#五采集指南)
6. [数据查看](#六数据查看)
7. [部署模式](#七-部署模式)
8. [项目结构](#八-项目结构)
9. [API 参考](#九-api-参考)
10. [设计原则](#十-设计原则)

---

## 一、产品定位

**AIHub** 解决企业 AI 化过程中的两个核心问题：

| | V1 · 记忆中枢 | V2 · 运营平面 |
|---|---|---|
| **问题** | 员工和 AI 的对话，离职就没了 | AI 系统跑起来，没人知道它在干什么 |
| **回答** | 自动采集、结构化、可检索 | 可观测、可审计、可度量、可恢复 |
| **一句话** | 人走，知识留下 | AI 上线，你接得住 |

---

## 二、V2 升级：从记忆到可运营

### 2.1 为什么需要运营平面

```
2024-2026 年，你的团队开始大规模使用 AI 编程工具：

  研发用 Claude Code 写代码
  运维用 Cursor 修配置
  数据团队用自建 Agent 跑分析

  问题来了：
  · 上周谁用了什么模型？花了多少 Token？
  · AI 有没有执行过危险命令？谁审批的？
  · 出问题时，能定位到是哪次调用、哪个 Prompt 导致的吗？
  · 那个 Agent 的 Prompt 改了之后，效果变好还是变差？

  答案很可能是：不知道。
```

### 2.2 AI 可运营七维度

AIHub V2 围绕**"AI 可运营七维度"模型**构建了完整的度量与审计体系：

| # | 维度 | AIHub 的能力 |
|---|------|-------------|
| 1 | **可观测·可归因** | 每次 LLM 调用自动记录：谁、什么模型、什么 Prompt、耗时、Token |
| 2 | **可评估·可度量** | 质量分、净收益、返工率——从运行数据自动计算 |
| 3 | **可恢复·可兜底** | 每个 AI 系统登记爆炸半径、回滚目标、熔断开关 |
| 4 | **可演进·可迭代** | Prompt 版本追踪 + 图谱关联——改 Prompt 之前知道影响范围 |
| 5 | **可治理·可控** | 审批结果回流审计链——高风险操作有痕迹可追溯 |
| 6 | **可学习·可改进** | 错误事件自动沉淀为失败样本 → 提升为回归测试集 |
| 7 | **成本可控** | Token → 金额折算 + 预算上限 + 越线告警——FinOps for AI |

`GET /operability/score` 返回 0-21 分自评 + 成熟度分档（危险区 / 脆弱区 / 基本可运营 / 较成熟）。

---

## 三、核心能力

### 3.1 四条采集路径，覆盖全部 AI 使用场景

```
┌──────────────────────────────────────────────────────────────┐
│                     采集层（零侵入）                           │
│                                                              │
│  Chrome 扩展     │  HTTP 代理      │  OTel Receiver  │  REST  │
│  浏览器 AI 对话   │  Claude Code    │  LangChain 等   │  自定义 │
│  ChatGPT/Claude  │  Cursor/Cont..  │  自建 Agent     │  任意   │
│  /Kimi/DeepSeek  │  终端 AI 编程    │  框架自动埋点    │  场景   │
└──────────┬──────────────────────────┬──────────────────┬─────┘
           │                          │                  │
           └──────────────────────────┴──────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────┐
│                   AIHub 后端 (:8712)                          │
│                                                              │
│  对话记忆          │  运营平面（V2 新增）                       │
│  /messages         │  /system-events  系统事件采集            │
│  /search           │  /v1/traces      OTel 标准协议           │
│  /context          │  /metrics         质量/返工/覆盖率        │
│  /graph            │  /cost            成本归因+预算           │
│  /projects         │  /operability/score  七维度自评           │
│  /stats            │  /systems/{id}/runbook  兜底/回滚         │
│                    │  /failure-samples    失败样本→回归集       │
│                                                              │
│  SQLite + ChromaDB（默认）  ←→  PostgreSQL + pgvector（可选）  │
└──────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────┐
│              AIHub 前端 (:5173)                               │
│         时间线 │ 对话详情 │ 知识图谱 │ 项目聚类                │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 知识记忆（V1 延续）

- **自动采集**：浏览器扩展静默运行，员工正常使用 AI，对话自动入库
- **智能理解**：每条对话自动生成标题、标签、摘要；跨平台语义搜索
- **知识图谱**：自动发现对话之间的深层关联，按主题聚合为项目
- **上下文注入**：AI 回答时注入历史上下文，基于团队知识积累来回答

---

## 四、5 分钟跑起来

### 4.1 一键启动

```bash
git clone https://github.com/Vincent-chao-lang/AIHub.git
cd AIHub
./start.sh
# → 后端 http://localhost:8712
# → 前端 http://localhost:5173
# → API 文档 http://localhost:8712/docs
```

### 4.2 加载浏览器扩展

```
Chrome → chrome://extensions → 开发者模式 → 加载已解压 → 选择 extension/ 目录
→ 打开 ChatGPT/Claude.ai/Kimi/DeepSeek → 正常聊天 → 自动采集
```

### 4.3 启动 HTTP 代理（采集 Claude Code / Cursor）

```bash
cd backend
python proxy.py

# 如果使用智谱/DeepSeek 等兼容 API：
UPSTREAM_ANTHROPIC=https://open.bigmodel.cn/api/anthropic python proxy.py
```

Claude Code 配置（`settings.json`）：

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:8888"
  }
}
```

Cursor / Continue 配置：

```bash
export OPENAI_BASE_URL=http://localhost:8888
```

**数据完全在本地。** 不注册、不联网、不上传。你拥有全部数据。

---

## 五、采集指南

### 快速对照

| 你用的是什么 | 怎么接入 | 采集路径 |
|-------------|---------|---------|
| 浏览器 ChatGPT / Claude.ai / Kimi / DeepSeek / Gemini | 装 Chrome 扩展 | `/messages` |
| 终端 Claude Code | 配 `ANTHROPIC_BASE_URL` | `/system-events` |
| 终端 Cursor / Continue | 配 `OPENAI_BASE_URL` | `/system-events` |
| 自建 LangChain / CrewAI Agent | 配 OTel Exporter | `/v1/traces` |
| 任意 HTTP 客户端 | 调 `POST /system-events` | `/system-events` |

### 采集到的数据示例

```
[08:14:51] claude-code | tool_call | glm-5.2 | 1251 tok | 43.8s | success
  💬 提示词: 当前系统的冗余和重复代码检测
  📋 系统:   You are Claude Code, Anthropic's official CLI...
  🔧 工具:   Read×7
```

每条事件记录：模型、Token 用量、延迟、工具调用、提示词原文、System Prompt 全文。

---

## 六、数据查看

### 命令行

```bash
curl http://localhost:8712/stats              # 全局统计
curl http://localhost:8712/metrics            # 运营指标（质量分/返工率/覆盖率）
curl http://localhost:8712/cost               # 成本归因（按系统/Token）
curl http://localhost:8712/operability/score  # 七维度自评分
curl http://localhost:8712/failure-samples    # 失败样本
```

### Web 前端

| 页面 | 路由 | 内容 |
|------|------|------|
| 时间线 | `/` | 按日期浏览 AI 对话 |
| 对话详情 | `/conversation/:id` | 完整消息列表 |
| 知识图谱 | `/graph` | D3.js 可视化知识网络 |
| 项目聚类 | `/projects` | 按主题自动归类 |

### 直接查数据库

```bash
cd backend
python -c "
from sqlmodel import Session, select
from db.database import engine
from models.operability import SystemEvent
import json

with Session(engine) as session:
    for e in session.exec(select(SystemEvent).order_by(SystemEvent.created_at.desc()).limit(5)).all():
        tools = ','.join([t['tool'] for t in json.loads(e.tool_calls or '[]')])
        print(f'[{e.timestamp}] {e.ai_system_id} | {e.event_type} | {e.model_version} | {e.cost_tokens}tok | {e.latency_ms}ms | {e.status} | {tools}')
"
```

---

## 七、部署模式

| 模式 | 适合 | 配置 |
|------|------|------|
| **个人本地** | 个人使用 | 零配置，`./start.sh` |
| **局域网共享** | 团队 5-50 人 | 改 `host` 为 `0.0.0.0` |
| **Docker** | 标准化部署 | `docker-compose up` |
| **HTTPS + 反向代理** | 远程团队 | Nginx + Let's Encrypt |

### 存储升级

```
SQLite + ChromaDB  →  PostgreSQL + pgvector  →  Milvus
  零配置                改一行 .env                独立集群
  < 10 万条              10-100 万条                 > 100 万条
```

```bash
# backend/.env
DATABASE_URL=postgresql://user:pass@host:5432/aihub
VECTOR_STORE=pgvector
```

详见 [docs/STORAGE.md](docs/STORAGE.md) 和 [docs/USAGE.md](docs/USAGE.md)。

---

## 八、项目结构

```
AIHub/
├── start.sh                        # 一键启动
├── backend/                        # FastAPI + SQLite + ChromaDB
│   ├── main.py                     # 入口 (:8712)
│   ├── proxy.py                    # HTTP 透明代理 (:8888) [V2 新增]
│   ├── api/
│   │   ├── routes.py               # 10 个对话记忆端点
│   │   └── operability_routes.py   # 8 个运营平面端点 [V2 新增]
│   ├── db/                         # 数据库 + 向量存储
│   ├── models/
│   │   ├── message.py              # 对话模型
│   │   └── operability.py          # 运营模型 [V2 新增]
│   └── services/
│       ├── context.py              # 图谱上下文生成
│       ├── summarizer.py           # TF-IDF 自动摘要
│       ├── search.py               # 语义搜索
│       ├── embedding.py            # 本地 BGE 模型
│       ├── event_collector.py      # 系统事件采集 [V2 新增]
│       ├── operability.py          # 度量/成本/评分引擎 [V2 新增]
│       └── otel_receiver.py        # OpenTelemetry 接收器 [V2 新增]
├── extension/                      # Chrome 扩展 (Manifest V3)
│   └── content/                    # 5 平台 DOM 监听
├── frontend/                       # React + Vite + TypeScript + D3.js
│   └── src/pages/                  # 时间线 · 项目 · 图谱 · 上下文
├── landing/                        # 营销页面
└── docs/                           # 文档
    ├── USAGE.md                    # 使用指南 [V2 新增]
    ├── TECHNICAL.md                # 技术架构
    ├── STORAGE.md                  # 存储升级路径
    └── 运营平面开发设计文档.md        # 运营平面设计规格
```

---

## 九、API 参考

### 对话记忆（V1，10 个端点）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/messages` | 上传消息（自动 embedding + 摘要） |
| GET | `/timeline` | 时间线（按对话聚合） |
| GET | `/conversations/{id}` | 对话详情 |
| GET | `/conversations/{id}/related` | 相关对话推荐 |
| POST | `/search` | 语义搜索（向量 + 关键词回退） |
| POST | `/context` | 图谱驱动上下文生成 |
| GET | `/projects` | 项目聚合 |
| GET | `/graph` | 知识图谱数据 |
| POST | `/summarize/{id}` | 重新生成摘要 |
| GET | `/stats` | 统计概览 |

### 运营平面（V2，9 个端点）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/system-events` | 接收系统运行事件 |
| POST | `/v1/traces` | OTLP 标准协议（OpenTelemetry） |
| GET | `/metrics` | 质量分/净收益/返工率/覆盖率 |
| GET | `/cost` | 成本归因 + 预算对比 |
| GET | `/operability/score` | 七维度自评分（0-21） |
| GET | `/systems/{id}/runbook` | 获取兜底/回滚配置 |
| POST | `/systems/{id}/runbook` | 登记兜底/回滚配置 |
| GET | `/failure-samples` | 失败样本列表 |
| POST | `/failure-samples/{id}/promote` | 提升为回归测试集 |

启动后端后访问 `http://localhost:8712/docs` 可在线调试所有端点。

---

## 十、设计原则

1. **自动采集** — 采集成本从"人"转移到"系统"，无需额外操作
2. **本地优先** — 数据 100% 归你，零网络依赖
3. **非破坏性** — 新功能纯增量，不影响已有数据和 API
4. **复用优先** — 运营事件复用对话记忆的 embedding + 摘要 + 图谱管线
5. **元数据最小化** — 采集运营指标（模型、Token、延迟），原始代码/对话内容不落地
6. **企业级扩展** — SQLite → PostgreSQL，ChromaDB → pgvector，随规模平滑升级

---

<p align="center">
  <a href="https://github.com/Vincent-chao-lang/AIHub">GitHub</a> ·
  <a href="docs/USAGE.md">使用文档</a> ·
  <a href="docs/TECHNICAL.md">技术架构</a> ·
  <a href="docs/运营平面开发设计文档.md">运营平面设计</a>
</p>
