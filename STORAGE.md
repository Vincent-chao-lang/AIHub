# 存储升级路径方案

> AI Memory Hub 从个人使用到企业级部署的数据库和向量存储升级路径。
> 核心原则：**升级路径和用户规模同步增长，不让小团队承担大企业的运维成本。**

---

## 一、当前方案

| 层 | 技术 | 配置方式 |
|------|------|---------|
| 结构化数据 | SQLite（SQLModel） | `DATABASE_URL` 环境变量 |
| 向量索引 | ChromaDB（PersistentClient） | `VECTOR_STORE` 环境变量 |

默认零配置，`./start.sh` 一键启动。数据全部本地，备份 = 复制文件。

---

## 二、向量数据库对比

### 2.1 一句话定位

| | ChromaDB | pgvector | Milvus |
|------|---------|---------|--------|
| 定位 | 开发者的"零配置"向量库 | PostgreSQL 的向量插件 | 专业向量数据库 |
| 类比 | SQLite 之于数据库 | PostGIS 之于地理信息 | Elasticsearch 之于搜索 |
| 适合 | 原型→中小规模 | 已有 PG 的团队 | 大规模生产环境 |

### 2.2 关键对比

| 维度 | ChromaDB | pgvector | Milvus |
|------|---------|---------|--------|
| **部署** | `pip install`，零配置 | PG 扩展，一行 SQL | 需要 etcd + MinIO + 多个服务 |
| **索引算法** | HNSW | HNSW / IVFFlat | HNSW / IVF / DiskANN / 十几种 |
| **10 万向量查询** | < 10ms | < 20ms | < 5ms |
| **1000 万向量查询** | 不可行 | 勉强（需大量调优） | < 50ms（GPU 加速） |
| **元数据过滤** | 基础，性能一般 | SQL WHERE，灵活且快 | 丰富，支持标量+向量混合 |
| **分布式** | 不支持 | 依赖 PG 主从 | 原生分片+副本 |
| **内存占用** | ~100MB | 取决于 PG 配置 | 4GB 起步 |
| **运维复杂度** | 零 | 等于运维 PostgreSQL | 高（多组件协调） |
| **备份恢复** | 复制目录 | PG 原生工具 | 多组件分别备份 |

### 2.3 选型速查

```
 < 10 万条向量  →  ChromaDB（零配置，完美匹配）
 10-100 万条    →  pgvector（已有 PostgreSQL 即可）
 > 100 万条     →  Milvus（需要专门的向量数据库团队）

AI Memory Hub 的规模估算：
 50 人团队 × 每天 50 条 AI 消息 × 365 天 = 约 90 万条/年
 ChromaDB 覆盖前 1-2 年，pgvector 覆盖 3-5 年。
```

---

## 三、推荐的升级路径

### 3.1 为什么不能直接跳 Milvus

Milvus 的部署栈：

```
AI Memory Hub（当前）          AI Memory Hub + Milvus
    ./start.sh                      │
      │                         docker-compose up
      ├── Python 后端               │
      ├── Vite 前端                 ├── Python 后端
      └── ChromaDB（进程内）         ├── Vite 前端
                                    ├── Milvus（独立服务）
                                    ├── etcd（元数据）
                                    ├── MinIO（对象存储）
                                    ├── Pulsar/Kafka（消息队列）
                                    └── 至少 4GB 内存

   一个命令。                     一个运维团队。
```

把"零配置"产品变成"需要运维团队"的产品，不是升级，是换赛道。Milvus 和产品的定位直接冲突。

### 3.2 三段式升级路径

```
阶段 1（当前）         阶段 2（自然升级）        阶段 3（企业级）

  ChromaDB      →      pgvector       →      Milvus
  pip install          PG 扩展               独立集群
  零配置               已有 PG 就能用          需要运维

  SQLite               PostgreSQL            PostgreSQL
  单文件                客户端/服务器           集群+读写分离

  < 10 万条             10-100 万条             > 100 万条
  个人/小团队            中型团队                大企业
```

### 3.3 升级路径和数据库升级天然重合

```
用户用 SQLite 时 → ChromaDB（零配置，完美匹配）
用户切 PostgreSQL 时 → pgvector（不需要新服务，PG 自带）
用户需要分布式时 → Milvus（这时已经有运维团队了）
```

---

## 四、如何切换

### 4.1 ChromaDB → pgvector

```bash
# backend/.env
DATABASE_URL=postgresql://user:password@localhost:5432/aihub
VECTOR_STORE=pgvector

# 安装依赖
pip install pgvector psycopg2-binary

# 在 PostgreSQL 中启用扩展（首次）
psql -d aihub -c "CREATE EXTENSION IF NOT EXISTS vector"

# 重启后端
python main.py
```

表会自动创建，HNSW 索引自动建立。切换后新消息会写入 pgvector，旧数据保留在 ChromaDB 中。

### 4.2 一行配置完成切换

代码层已实现抽象接口（`services/vector_store.py`），所有后端实现同一套方法：

```python
# 所有后端都实现这 4 个方法
class VectorStore(ABC):
    def add(self, msg_id, content, metadata): ...
    def search(self, query, top_k): ...
    def find_related(self, conversation_id, query_text, exclude_conv_id, top_k): ...
    def count(self): ...
```

路由层通过工厂函数获取实例，自动根据 `VECTOR_STORE` 选择后端：

```python
store = get_vector_store()  # 自动选择 chromadb 或 pgvector
```

---

## 五、当前阶段建议

1. **保持 ChromaDB 作为默认** — 对目标用户（20-200 人团队）完全够用
2. **升级路径已预留** — 用户切 PostgreSQL 时，改一行 `.env` 即可同步切 pgvector
3. **不要为还没发生的需求写代码** — 等第一个用户真的跑满了 ChromaDB 再考虑

> ChromaDB → pgvector 是自然升级（和 PG 切换同步发生）
> ChromaDB → Milvus 是跨级跳（需要额外的运维能力，和产品定位冲突）
>
> 当前阶段引入 Milvus 反而会劝退用户——部署门槛太高。"零配置"本身就是产品壁垒的一部分。
