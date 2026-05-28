# AI Memory Hub — 技术文档

> 跨平台 AI 长期记忆系统的架构设计、技术决策与工程取舍

---

## 目录

1. [系统概述](#1-系统概述)
2. [架构设计](#2-架构设计)
3. [核心算法](#3-核心算法)
4. [数据模型](#4-数据模型)
5. [API 设计](#5-api-设计)
6. [扩展设计](#6-扩展设计)
7. [设计决策与取舍](#7-设计决策与取舍)
8. [性能与扩展性](#8-性能与扩展性)
9. [安全与隐私](#9-安全与隐私)
10. [未来演进](#10-未来演进)

---

## 1. 系统概述

### 1.1 定位

AI Memory Hub 是一个**本地优先的个人 AI 长期记忆系统**。它不替代任何 AI 平台，而是在所有 AI 平台之下铺设一层统一的知识层，实现：

- **采集**：自动记录用户在多个 AI 平台（ChatGPT、Claude、DeepSeek、Kimi、Gemini）的所有对话
- **存储**：本地 SQLite + 向量数据库（ChromaDB），数据完全归用户所有
- **检索**：语义搜索 + 关键词回退 + 知识图谱遍历，多维度发现关联
- **注入**：生成结构化上下文，一键注入任意 AI 平台，让 AI 基于用户的历史知识回答问题

### 1.2 核心指标

| 指标 | 数值 |
|------|------|
| 支持的 AI 平台 | 5 个（ChatGPT / Claude / DeepSeek / Kimi / Gemini） |
| Token 档位 | 8 档（1K ~ 128K） |
| Embedding 维度 | 384（BGE-small-zh-v1.5） |
| 向量搜索算法 | ChromaDB cosine 距离 |
| 图谱遍历深度 | 最大 2 跳 |
| 数据库 | SQLite（SQLModel ORM），单文件部署 |

---

## 2. 架构设计

### 2.1 三层架构

```
┌─────────────────────────────────────────────────┐
│                   表示层                          │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ 侧边栏    │  │ Web 前端  │  │ 设置页        │  │
│  │ (原生 JS) │  │ (React)  │  │ (原生 JS)     │  │
│  └─────┬─────┘  └────┬─────┘  └───────┬───────┘  │
│        │              │                │          │
├────────┼──────────────┼────────────────┼──────────┤
│        │         代理层 │                │          │
│  ┌─────┴──────────────┴────────────────┴───────┐  │
│  │         Chrome Extension Background          │  │
│  │  消息路由 / API 代理 / 健康检查               │  │
│  └──────────────────────┬──────────────────────┘  │
│                         │                         │
├─────────────────────────┼─────────────────────────┤
│                         │         服务层           │
│  ┌──────────────────────┴──────────────────────┐  │
│  │              FastAPI (Python)                │  │
│  │  ┌──────────┐ ┌──────────┐ ┌─────────────┐ │  │
│  │  │ embedding │ │ context  │ │ summarizer  │ │  │
│  │  │ (BGE)    │ │ (图谱)   │ │ (TF-IDF)   │ │  │
│  │  └──────────┘ └──────────┘ └─────────────┘ │  │
│  └──────────┬──────────────┬───────────────────┘  │
│             │              │                       │
├─────────────┼──────────────┼───────────────────────┤
│             │         数据层 │                       │
│  ┌──────────┴──┐  ┌────────┴─────────┐            │
│  │   SQLite    │  │    ChromaDB      │            │
│  │  (结构化)   │  │  (向量索引)      │            │
│  └─────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────┘
```

### 2.2 关键设计原则

**原则 1：插件无状态，后端有状态**

Content Script 只做 DOM 观察和数据提取，不做任何 AI 推理、不去重（仅做流式去重）、不存储。所有智能处理集中在后端。这样：
- 插件体积小、权限最小的主
- 后端可独立升级、替换 embedding 模型或摘要算法
- 插件崩溃不影响数据完整性

**原则 2：本地优先，但也支持服务端部署**

默认所有数据存储在本地（SQLite + ChromaDB），无需网络、无需注册、隐私完全自控。同时通过可配置的后端地址，支持部署到共享服务器供团队使用。

**原则 3：不改变用户习惯**

不做新的聊天框，不要求用户切换工作流。侧边栏跟随所有 AI 平台页面，采集完全自动、无感知。

**原则 4：图谱驱动而非 LLM 驱动**

关联发现不依赖外部 LLM（成本高、延迟大、隐私风险）。使用纯本地图谱算法（标签重叠 + 向量相似度）发现关联链，仅用本地模型做 embedding。

**原则 5：增量涌现价值**

单条对话价值有限，但汇聚后产生涌现效应：自动摘要 → 标签聚类 → 项目聚合 → 知识图谱 → 图谱驱动上下文注入。

---

## 3. 核心算法

### 3.1 图谱驱动上下文生成 (`services/context.py`)

这是系统最核心的算法，实现从用户话题到结构化上下文的完整流程。

#### 3.1.1 算法流程

```
输入：用户查询 query, 目标 Token 数 max_tokens
输出：结构化上下文文本 + 关键发现 + 推理路径 + Token 估算

步骤 1：向量检索定位种子对话
  ├── 对 query 做 embedding → 384 维向量
  ├── ChromaDB 搜索 top_k=30 最相似消息
  └── 按 conversation_id 去重 → 种子对话集合

步骤 2：构建知识图谱边
  ├── 从 SQLite 读取所有有标签的对话
  ├── 构建 conv_tags_map（conversation_id → tags set）
  └── 两两计算标签重叠：Jaccard >= 阈值 → "similar" 边

步骤 3：BFS 图谱遍历
  ├── 种子对话作为 BFS 队列起点（distance=0, score=1.0）
  ├── 沿 similar 边扩展到未访问节点
  ├── 距离衰减：score = parent_score × 0.6 × edge_weight
  └── 记录遍历路径（用于推理路径可视化）

步骤 4：智能 Token 预算分配
  ├── 固定开销（~100 tokens）：标题 + 结尾提示
  ├── 直接匹配对话：预算 400 tokens/条
  ├── 图谱发现对话：预算 250 tokens/条
  └── 按优先级排序，预算用尽即停止

步骤 5：格式化为结构化上下文
  ├── [直接相关的历史讨论]
  │   └── 每条：平台、标题、摘要、时间
  ├── [图谱发现的关联讨论]
  │   └── 额外标注关联跳数
  └── [当前讨论] + 提示语
```

#### 3.1.2 BFS 遍历伪代码

```python
def bfs_traverse(seeds, conv_tags_map, max_depth=2):
    visited = {}
    queue = []

    # 初始化种子节点
    for conv in seeds:
        queue.append({
            "conv": conv,
            "distance": 0,
            "score": 1.0,
            "path": [conv.title]
        })

    while queue:
        node = queue.pop(0)
        if node.conv.id in visited:
            continue
        visited[node.conv.id] = node

        if node.distance >= max_depth:
            continue

        # 查找标签重叠的邻居
        for neighbor in find_similar(node.conv, conv_tags_map):
            if neighbor.id not in visited:
                overlap = len(node.conv.tags & neighbor.tags)
                edge_weight = min(overlap / 5, 1.0)  # 归一化
                queue.append({
                    "conv": neighbor,
                    "distance": node.distance + 1,
                    "score": node.score * 0.6 * edge_weight,
                    "path": node.path + [neighbor.title]
                })

    return visited
```

#### 3.1.3 Token 预算分配策略

设计考量：上下文是**摘要**而非原文，实际输出远小于预算上限。预算分配遵循"直接匹配优先"原则。

```
总预算 B = max_tokens - 固定开销(~100)

直接匹配池（距离 = 0）：
  每条预算 = 400 tokens
  排序：按向量相似度降序

图谱发现池（距离 > 0）：
  每条预算 = 250 tokens
  排序：按关联分数降序

分配算法：
  for conv in sorted(all_candidates):
      if remaining_budget <= 0:
          break
      allocation = min(per_item_budget, remaining_budget)
      # 实际文本会被截断到 allocation
      remaining_budget -= actual_tokens_used
```

**为什么不用 LLM 做摘要？**
- 成本：每次对话都需要 API 调用，累积成本高
- 延迟：LLM 摘要需要 2-5 秒，影响侧边栏即时响应
- 隐私：对话内容发送到第三方 LLM 服务
- 可控性：本地规则截断行为完全可预测

### 3.2 自动摘要算法 (`services/summarizer.py`)

纯本地实现，无需外部 API。

#### 3.2.1 标签生成（TF-IDF 风格关键词提取）

```
输入：对话中的所有消息文本
输出：关键词标签列表（最多 10 个）

1. 分词：中文 2-gram + 英文空格分词
2. 计算词频 TF
3. 计算逆文档频率 IDF（基于全局对话统计）
4. TF-IDF 排序
5. 技术关键词加权（预定义技术词典，匹配的词 ×2 权重）
6. 取 top 10
```

#### 3.2.2 标题生成

取对话中第一条用户消息，截取前 50 字符作为标题。如果首条是 AI 消息，取首条用户消息。

#### 3.2.3 摘要生成

拼接第一条用户提问 + 最后一条 AI 回答（各截断到 200 字符），中间用"..."连接。

**设计取舍：简单规则 vs. LLM 摘要**

| 维度 | 规则摘要 | LLM 摘要 |
|------|---------|----------|
| 质量 | 中等（关键词可能不精确） | 高（语义理解准确） |
| 速度 | 毫秒级 | 秒级 |
| 成本 | 零 | 每次 $0.001-0.01 |
| 隐私 | 完全本地 | 内容出站 |
| 可控性 | 完全可预测 | 可能输出不稳定 |

当前选择规则摘要，因为：
1. 系统定位是"记忆索引"而非"内容理解"——标签只需足够区分不同主题即可
2. 零成本允许无限量使用
3. 后续可引入可选的 LLM 摘要作为增强

### 3.3 Embedding 与语义搜索

#### 3.3.1 模型选择：BAAI/bge-small-zh-v1.5

| 候选模型 | 维度 | 模型大小 | 中文效果 | 推理速度 |
|---------|------|---------|---------|---------|
| BGE-small-zh | 384 | ~100MB | 优秀 | 快 |
| BGE-base-zh | 768 | ~400MB | 更好 | 中等 |
| text2vec-large-chinese | 1024 | ~1.3GB | 优秀 | 慢 |
| OpenAI text-embedding-3-small | 1536 | API | 优秀 | 取决于网络 |

**选择 BGE-small 的理由：**
- 384 维在语义搜索场景下已足够（搜索精度损失 < 5% vs. 768 维）
- 模型仅 100MB，首次下载快，MacBook 上推理 < 50ms
- BGE 系列专为检索优化，支持检索前缀（`为这个句子生成表示以用于检索相关文章：`）
- 纯本地运行，零网络依赖

#### 3.3.2 搜索流程

```
POST /search { query, top_k? }

1. 向量搜索（主路径）
   ├── query embedding → 384 维向量
   ├── ChromaDB 余弦相似度搜索 → top_k * 2 候选
   └── 按 conversation_id 去重

2. 关键词回退（向量结果不足时）
   ├── 对 query 分词（中文 2-gram）
   ├── SQLite LIKE 匹配消息内容/标题/标签
   ├── 标题匹配 ×3 权重，标签匹配 ×2 权重
   └── 合并去重

3. 返回 SearchResult[]（含相关性分数）
```

### 3.4 知识图谱构建 (`api/routes.py` → `GET /graph`)

```
输入：所有有标签的对话
输出：GraphData { nodes: GraphNode[], edges: GraphEdge[] }

节点类型：
  - conversation：对话节点（圆点，颜色 = 平台色）
  - tag：标签节点（蓝色点，大小 = 出现频率）

边类型：
  - tag_link：对话 ↔ 标签
  - similar：标签重叠 >= 2 的对话对（蓝色边）
  - vector_similar：无标签重叠但语义相似的对话对（紫色边，余弦距离 < 0.3）

去重策略：
  - 使用 edge_key = sorted([source, target]) + type 去重
  - 优先保留 tag_link > similar > vector_similar
```

---

## 4. 数据模型

### 4.1 核心表结构

```sql
-- 消息表
CREATE TABLE message (
    id TEXT PRIMARY KEY,              -- UUID
    user_id TEXT DEFAULT 'local',     -- 用户标识（团队模式）
    platform TEXT NOT NULL,           -- chatgpt/claude/deepseek/kimi/gemini
    conversation_id TEXT NOT NULL,    -- 对话 ID
    role TEXT NOT NULL,               -- user/assistant/system
    content TEXT NOT NULL,            -- 消息内容
    message_index INTEGER DEFAULT 0,  -- 消息序号
    timestamp DATETIME NOT NULL,
    title TEXT,                       -- 自动生成的标题
    tags TEXT,                        -- JSON 数组：["tag1", "tag2"]
    summary TEXT,                     -- 自动生成的摘要
    metadata TEXT                     -- JSON：额外元数据
);

-- 索引
CREATE INDEX idx_platform ON message(platform);
CREATE INDEX idx_conversation_id ON message(conversation_id);
CREATE INDEX idx_timestamp ON message(timestamp);
CREATE INDEX idx_user_id ON message(user_id);
```

### 4.2 向量存储（ChromaDB）

```
Collection: messages
  - id: message.id
  - embedding: 384 维 float 数组
  - metadata: { conversation_id, platform, role, user_id }
  - distance: cosine
```

### 4.3 关键 Pydantic 模型

```python
class ContextRequest:
    query: str
    max_tokens: int = 2000

class ContextResponse:
    context_text: str              # 格式化上下文文本
    key_points: list[str]          # 关键发现（最多 5 条）
    graph_traversal: list[TraversalPath]  # 图谱推理路径
    related: list[RelatedConversation]    # 关联对话
    estimated_tokens: int          # 估算的 Token 数

class TraversalPath:
    conversation_id: str
    title: str
    platform: str
    distance: int                  # 距种子对话的跳数
    score: float                   # 关联分数
    path: list[str]                # 遍历路径（对话标题链）

class GraphData:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
```

---

## 5. API 设计

### 5.1 端点总览

| 方法 | 路径 | 功能 | 调用方 | 典型延迟 |
|------|------|------|--------|---------|
| POST | `/messages` | 接收消息（自动触发后台任务） | Content Scripts | < 50ms（主响应）+ 后台 embedding |
| GET | `/timeline` | 按日期分组的对话时间线 | 前端 Home | < 100ms |
| GET | `/conversations/{id}` | 单条对话详情 | 前端 Conversation | < 50ms |
| GET | `/conversations/{id}/related` | 相关对话推荐 | 前端 Conversation | < 200ms（含向量搜索） |
| POST | `/search` | 语义搜索 | 前端 Home | < 500ms（含 embedding） |
| POST | `/context` | 图谱驱动上下文生成 | Sidepanel + Context 页 | < 1s |
| POST | `/summarize/{id}` | 手动触发摘要 | 手动调用 | < 100ms |
| GET | `/projects` | 项目聚合 | 前端 Projects | < 100ms |
| GET | `/graph` | 知识图谱数据 | 前端 Graph | < 500ms（全量标签分析） |
| GET | `/stats` | 统计信息 | Options / Background | < 50ms |

### 5.2 后台任务设计

`POST /messages` 接收消息后立即返回 200，同时触发两个后台任务：

```
async def post_message(message: MessageCreate):
    msg = save_to_db(message)
    background_tasks.add_task(embed_and_index, msg)  # 不阻塞
    background_tasks.add_task(auto_summarize, msg)   # 不阻塞
    return msg
```

**设计考量：**
- 消息保存是同步的（必须成功），embedding 和摘要是异步的（容许延迟）
- 用户发消息时感知延迟 < 50ms（仅 SQLite INSERT）
- embedding 失败不影响消息存储，消息仍然可通过关键词搜索找到
- ChromaDB 写入失败有重试逻辑

---

## 6. 扩展设计

### 6.1 Content Script：流式去重策略

AI 平台的流式响应会多次更新 DOM，直接转发会导致重复消息。采用了**连续两次内容相同才发送**的策略：

```javascript
// 伪代码
const contentHistory = new Map();  // conversation_id -> { content, count }

function onMessageDetected(msg) {
    const prev = contentHistory.get(msg.conversation_id);
    if (prev && prev.content === msg.content) {
        if (prev.count >= 1) {
            // 连续两次相同 → 流式响应已稳定 → 发送
            sendToAPI(msg);
            contentHistory.delete(msg.conversation_id);
        } else {
            prev.count++;
        }
    } else {
        contentHistory.set(msg.conversation_id, { content: msg.content, count: 0 });
    }
}
```

**为什么是 2 次而不是 3 次？**
- 大多数 AI 平台的 SSE 更新间隔为 100-200ms
- 1 秒轮询周期内，连续 2 次内容相同意味着已稳定至少 1 秒
- 3 次会增加约 1 秒延迟，对用户体验有影响
- 实测 2 次在 5 个平台上都能正确去重

### 6.2 侧边栏 Token 选择器

侧边栏通过 `data-tokens` 属性实现 JS 零修改扩展：

```html
<button class="token-btn" data-tokens="2000">2K</button>
```

```javascript
// 动态读取，新增按钮无需修改 JS
const maxTokens = parseInt(btn.dataset.tokens, 10);
```

当前支持 8 个档位：1K / 2K / 4K / 8K / 16K / 32K / 64K / 128K。

**为什么设置 128K 上限？**
- 上下文返回的是**摘要**而非原文，实际生成内容远小于预算
- 128K 对应 GPT-4 128K、Claude 200K、Gemini 1.5 Pro 2M 等超长上下文模型
- 后端 Token 预算分配逻辑不变——预算只是上限，不是保证长度
- 更大的预算允许系统召回更多关联对话（更多条 400/250 token 条目）

### 6.3 可配置后端地址

用户可在设置页修改后端地址，支持三种部署模式：

```
模式 1：纯本地
  后端地址 = http://127.0.0.1:8712
  数据完全在本地，零网络出站

模式 2：局域网共享
  后端地址 = http://192.168.1.100:8712
  家庭/办公室内多人共享

模式 3：服务器部署
  后端地址 = https://aihub.example.com
  团队成员远程访问，需要 HTTPS + 认证
```

当前版本未实现认证层，服务器模式建议配合反向代理（Nginx）+ Basic Auth 使用。

---

## 7. 设计决策与取舍

### 7.1 数据库：SQLite vs. PostgreSQL

| 维度 | SQLite | PostgreSQL |
|------|--------|------------|
| 部署复杂度 | 零配置，单文件 | 需要独立进程 |
| 并发能力 | 单写者（WAL 模式下可并发读） | 高并发读写 |
| 备份 | 复制文件 | pg_dump |
| 性能（< 10 万条） | 优秀 | 优秀但过度 |
| 全文搜索 | LIKE 即可（数据量小） | 需要 pgvector + 索引 |

**选择 SQLite 的理由：**
- 个人使用场景，消息量在万级别，SQLite 完全胜任
- 单文件数据库，备份 = 复制文件，迁移 = 移动文件
- 零配置，`./start.sh` 一键启动
- Python 生态中 SQLModel + SQLite 组合成熟度高
- 如需扩展，可通过 SQLModel 的数据库 URL 切换迁移到 PostgreSQL

**SQLite 的已知限制与应对：**
- 并发写入：使用 WAL 模式（Write-Ahead Logging），允许并发读
- 全文搜索：当前数据量小，LIKE 足够；未来可集成 SQLite FTS5
- 数据库锁：FastAPI 的 `get_session()` 使用 yield 模式确保连接及时释放

### 7.2 向量数据库：ChromaDB vs. Milvus vs. pgvector

| 维度 | ChromaDB | Milvus | pgvector |
|------|----------|--------|----------|
| 部署复杂度 | pip install，零配置 | Docker/云服务 | PostgreSQL 扩展 |
| 内存占用 | 低（~50MB） | 高（~4GB 起步） | 中（PostgreSQL 开销） |
| API 易用性 | Pythonic，开箱即用 | 功能全但复杂 | SQL 风格 |
| 适用规模 | < 100 万向量 | > 100 万向量 | 中等 |
| 持久化 | 本地目录（SQLite + Parquet） | MinIO/S3 | PostgreSQL 存储 |
| 中文生态 | 一般（对 BGE 无特殊优化） | 一般 | 一般 |

**选择 ChromaDB 的理由：**
- 部署成本为零——和 SQLite 一样，单目录持久化
- `PersistentClient` 模式可以直接使用本地路径，无需服务进程
- Python API 简洁，与 FastAPI 的集成零摩擦
- 100 万向量以内性能优秀（个人用户几年的 AI 对话量大约在 1-10 万条）

**ChromaDB 的已知限制与应对：**
- 不支持分布式：个人使用无此需求
- 无内置分词器：使用 BGE 模型独立生成 embedding，不依赖 ChromaDB 的分词
- 元数据过滤性能一般：使用 `where` 过滤时，数据量小可接受；量大了可考虑建立多个 Collection

### 7.3 摘要：TF-IDF vs. LLM API vs. 本地小模型

见 3.2.3 节对比表。核心取舍：**零成本 + 即时响应 > 语义质量**。

如果需要更高质量的摘要，可以预埋可选的 LLM 摘要（用户在设置中选择启用，需配置 API Key），但默认的本地规则摘要已能满足"区分主题"的需求。

### 7.4 图谱构建：标签重叠 vs. 纯向量相似度

**混合策略：**
1. 主信号：标签重叠（标签由摘要算法提取，代表对话主题）
2. 辅助信号：向量相似度（标签重叠不足时补足）

**为什么不全用向量相似度？**
- 计算复杂度 O(n²)：全量对话两两计算余弦相似度成本太高
- 标签重叠是 O(n × m)，m 为标签数（通常 < 10），快得多
- 标签提供了可解释性：用户能看到"这两个对话共享标签 Python, FastAPI"

**为什么不全用标签重叠？**
- 标签数量有限（每对话最多 10 个），可能遗漏语义关联
- 两个讨论"认证中间件"的对话可能用不同标签（"中间件" vs. "认证"）

### 7.5 前端：React vs. 纯 HTML vs. Next.js

| 维度 | React SPA | 纯 HTML | Next.js |
|------|----------|---------|---------|
| 开发效率 | 高（组件化） | 低 | 高 |
| D3.js 集成 | 良好 | 困难 | 良好 |
| 部署 | Vite 静态构建 | 直接打开 | 需要 Node 服务 |
| 包体积 | 中等 | 最小 | 大 |
| 首屏速度 | 快（CSR） | 最快 | 快（SSR） |

**选择 React + Vite 的理由：**
- 页面间有大量状态共享（搜索、筛选），纯 HTML 难以管理
- D3.js 与 React 的集成通过 `useEffect` + `useRef` 实现，成熟可靠
- Vite 开发体验优秀（HMR 热更新），构建产物小
- 无需 SSR（所有数据来自本地 API，对 SEO 无需求）

### 7.6 扩展：Manifest V3 vs. Manifest V2

Chrome 已强制要求 Manifest V3，MV2 扩展将被逐步淘汰。

MV3 的关键约束与应对：

| 约束 | 影响 | 应对 |
|------|------|------|
| Service Worker 替代 Background Page | SW 可能被浏览器休眠 | 关键逻辑无状态，消息驱动 |
| 不能使用 `eval` / `new Function` | 代码必须纯静态 | 原生 JS 不使用这些特性 |
| `webRequest` 改为 `declarativeNetRequest` | 不能动态拦截请求 | 不需要拦截请求，只需转发 |
| Content Script 隔离 | 无法访问页面 JS 变量 | 全部通过 DOM 选择器提取 |

### 7.7 去重策略

系统有两个层面的去重：

**1. 采集去重（消息级）：**
- 使用内容哈希 `generateMessageId()` 生成消息指纹
- `sentMessages` Set 缓存最近 500 条 ID
- 防止同一消息因 DOM 重渲染被重复采集

**2. 流式去重（内容级）：**
- Content Script 层面的连续两次相同判断
- 防止 AI 流式响应被多次采集

**为什么不直接用消息 ID 去重？**
- 流式响应时消息 ID 不变但内容在变——需要内容级去重
- 消息 ID 去重是最后防线，防止重跑监听器时的重复采集

---

## 8. 性能与扩展性

### 8.1 当前性能基准

| 操作 | 数据规模 | 延迟 |
|------|---------|------|
| 消息保存 | — | < 50ms |
| Embedding 单条 | 1 条消息 | < 50ms（CPU）/ < 20ms（GPU） |
| Embedding 批量 | 100 条消息 | < 2s（CPU） |
| 语义搜索 | 10000 条向量 | < 100ms |
| 上下文生成 | 1000 条对话 | < 1s |
| 图谱数据 | 500 条对话 | < 500ms |
| Timeline | 1000 条对话 | < 100ms |

### 8.2 扩展瓶颈分析

| 瓶颈 | 阈值 | 缓解方案 |
|------|------|---------|
| SQLite 写入 | 并发 > 50 QPS | 切换到 PostgreSQL |
| ChromaDB 搜索 | 向量 > 100 万 | 切换到 Milvus 或使用 HNSW 索引 |
| BGE 推理 | 批量 > 1000 条 | GPU 推理 / 批量推理 / 切换到 ONNX |
| 图谱构建 | 对话 > 10000 条 | 增量构建 / 缓存边关系 |
| 标签聚类 | 对话 > 5000 条 | 预计算 + 定时更新 |

### 8.3 已实施的优化

- **WAL 模式**：SQLite 使用 WAL 日志模式，提高并发读性能
- **懒加载模型**：BGE 模型在首次使用时才加载，服务启动快
- **后台任务**：embedding 和摘要异步执行，不阻塞消息接收
- **连接池**：SQLite 连接通过生成器模式管理，避免连接泄漏
- **ChromaDB 持久化**：向量索引持久化到磁盘，重启无需重新生成

---

## 9. 安全与隐私

### 9.1 数据所有权

所有数据默认存储在本地：
- `backend/aihub.db`：SQLite 数据库
- `backend/.chromadb/`：向量索引
- `backend/.models/`：BGE 模型缓存

用户完全拥有数据，可随时备份、迁移、删除。

### 9.2 网络安全

- 后端默认绑定 `127.0.0.1`（仅本地访问）
- 服务器部署时建议配合反向代理 + TLS + Basic Auth
- 扩展通过 `chrome.storage.local` 存储配置，不可被网页 JS 读取

### 9.3 隐私考量

**当前保护措施：**
- 对话内容不出站（使用本地 embedding 模型和本地摘要）
- 不向任何外部 API 发送对话数据
- 不收集使用数据或遥测

**需要用户注意：**
- 服务器模式时，数据通过网络传输，需要配置 TLS
- 团队模式时，所有成员可以看到共享后端的所有对话
- 没有内置对话加密（如需可配合磁盘加密如 FileVault）

### 9.4 扩展权限说明

| 权限 | 用途 | 风险 |
|------|------|------|
| `storage` | 保存后端地址、用户标识 | 低：仅存储配置 |
| `sidePanel` | 侧边栏功能 | 低：Chrome 内置 API |
| `alarms` | 定时任务（未使用） | 无 |
| 主机权限（5 个 AI 平台） | Content Script 注入 | 低：仅监听 DOM |
| 主机权限（所有 HTTP） | 连接自定义后端地址 | 中：需要信任后端服务器 |

---

## 10. 未来演进

### 10.1 Phase 8：更多信息源

扩展采集能力到非 AI 平台：
- 微信（桌面版 Web）
- 邮件（Gmail / Outlook Web）
- GitHub Issues / PR 讨论
- Notion 页面
- Obsidian 笔记

挑战：非对话格式的内容需要不同的摘要和关联策略。

### 10.2 Phase 9：Tauri 桌面应用

将 Web 前端打包为桌面应用：
- Electron 太重（~200MB），Tauri 更轻（~5MB）
- 内置 Rust 后端替代 Python（性能更好，包体积更小）
- 托盘图标 + 全局快捷键唤起

### 10.3 长期方向

| 方向 | 描述 |
|------|------|
| 可选 LLM 摘要 | 用户可选择启用 LLM 摘要，配置自己的 API Key |
| 定期知识总结 | 每周/每月自动生成知识摘要报告 |
| 记忆衰减 | 基于时间衰减的检索权重（最近对话权重更高） |
| 多语言支持 | 扩展 embedding 模型到多语言（当前 BGE 偏中文） |
| 导出/导入 | 标准格式导出，支持迁移到其他系统 |
| Agent 模式 | 记忆系统主动推送相关上下文给 AI Agent |

---

## 附录 A：Token 长度档位说明

系统支持 8 个 Token 档位（1K / 2K / 4K / 8K / 16K / 32K / 64K / 128K），用于限制返回的上下文摘要长度。

**重要理解：**
- 上下文返回的是**摘要**，不是原始对话，实际输出远小于预算上限
- 更大的预算允许系统召回更多关联对话（分配更多条目）
- 每条对话的预算固定（直接匹配 400 tokens、图谱发现 250 tokens）
- 即使选择 128K，实际输出通常不会超过 10K tokens（取决于匹配的对话数量）

**档位选择建议：**

| 模型类型 | 推荐档位 | 典型模型 |
|---------|---------|---------|
| 短上下文 | 1K-4K | 基础对话场景 |
| 标准上下文 | 4K-8K | GPT-4o、Claude Sonnet |
| 中长上下文 | 16K-32K | DeepSeek-V3、GPT-4 Turbo |
| 超长上下文 | 64K-128K | GPT-4 128K、Claude 200K、Gemini 1.5 Pro |

## 附录 B：开发环境搭建

```bash
# 后端
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py

# 前端
cd frontend
npm install
npm run dev

# 扩展
# Chrome → chrome://extensions → 开发者模式
# → 加载已解压的扩展程序 → 选择 extension/ 目录
```

## 附录 C：关键依赖版本

| 依赖 | 版本 | 用途 |
|------|------|------|
| fastapi | >= 0.110 | Web 框架 |
| sqlmodel | >= 0.0.16 | ORM |
| chromadb | >= 0.4 | 向量数据库 |
| sentence-transformers | >= 2.6 | Embedding 模型加载 |
| tiktoken | >= 0.7 | Token 估算 |
| react | ^19.0 | 前端框架 |
| vite | ^6.0 | 构建工具 |
| d3 | ^7.0 | 知识图谱可视化 |
