# AI Memory Hub — 部署与使用指南

> 面向企业 IT 管理员的完整部署文档。从零到团队全员使用，约 30 分钟。

---

## 目录

1. [环境要求](#一环境要求)
2. [快速开始（5 分钟）](#二快速开始5-分钟)
3. [部署模式](#三部署模式)
4. [数据存储](#四数据存储)
5. [团队配置](#五团队配置)
6. [日常使用](#六日常使用)
7. [运维管理](#七运维管理)
8. [常见问题](#八常见问题)

---

## 一、环境要求

| 组件 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.10+ | 后端运行环境 |
| Node.js | 18+ | 前端构建（可选，仅 Web 面板需要） |
| Chrome / Edge | 最新版 | 浏览器扩展 |
| 磁盘空间 | ~2GB | 含 BGE 模型（~100MB）+ 数据 |
| 内存 | 2GB+ | BGE 模型推理约需 1GB |

---

## 二、快速开始（5 分钟）

### 2.1 一键启动

```bash
git clone https://github.com/Vincent-chao-lang/AIHub.git
cd AIHub
./start.sh
```

脚本会自动：
1. 安装 Python 依赖（首次运行）
2. 安装前端依赖（首次运行）
3. 启动后端 → `http://127.0.0.1:8712`
4. 启动前端 → `http://localhost:5173`

### 2.2 手动启动

```bash
# 后端
cd backend
pip install -r requirements.txt
python main.py
# → http://127.0.0.1:8712

# 前端（可选，不影响侧边栏使用）
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 2.3 加载浏览器扩展

```
1. 打开 Chrome → chrome://extensions
2. 开启右上角「开发者模式」
3. 点击「加载已解压的扩展程序」
4. 选择项目中的 extension/ 目录
5. 扩展图标出现在浏览器工具栏
```

### 2.4 验证安装

```
1. 打开任意 AI 平台（如 chat.openai.com）
2. 发一条消息
3. 点击浏览器工具栏 🧠 图标 → 侧边栏滑出
4. 输入话题 → 点击「检索我的记忆」
5. 如果能返回上下文 → 采集和检索都正常
```

---

## 三、部署模式

### 模式 1：个人本地（默认）

```
┌───────────────┐
│  你的电脑      │
│  ┌──────────┐ │
│  │ 后端 :8712│ │  ← 数据在本地
│  │ 前端 :5173│ │  ← 浏览器访问
│  └──────────┘ │
└───────────────┘

适合：个人使用，数据完全私有
配置：无需任何修改，开箱即用
```

### 模式 2：局域网共享

```
┌─────────────────────────────────────┐
│  服务器（或某台机器）                  │
│  ┌────────────────────────────────┐ │
│  │ 后端 :8712（绑定 0.0.0.0）      │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
      ↑               ↑
      员工A            员工B
  扩展设置后端地址    扩展设置后端地址
  → http://192.168.x.x:8712

适合：同一办公室/家庭，多人共享
配置：
  1. 修改 main.py 最后一行的 host 为 "0.0.0.0"
  2. 每人扩展设置页填入服务器的局域网 IP
  3. 每人填入不同的 user_id（如 zhang-san, li-si）
```

### 模式 3：服务器部署（Docker）

```bash
# Dockerfile 示例（放在项目根目录）
FROM python:3.11-slim

WORKDIR /app
COPY backend/ backend/
RUN pip install -r backend/requirements.txt

EXPOSE 8712
CMD ["python", "backend/main.py"]
```

```bash
# docker-compose.yml 示例
version: '3.8'
services:
  aihub:
    build: .
    ports:
      - "8712:8712"
    volumes:
      - ./data/aihub.db:/app/backend/aihub.db
      - ./data/.chromadb:/app/backend/.chromadb
    environment:
      - DATABASE_URL=sqlite:///app/backend/aihub.db
      - CHROMA_PATH=/app/backend/.chromadb
    restart: unless-stopped
```

```bash
docker-compose up -d
# → 后端运行在 http://server-ip:8712
```

### 模式 4：HTTPS + 反向代理（推荐用于生产）

```nginx
# Nginx 配置示例
server {
    listen 443 ssl;
    server_name aihub.your-company.com;

    ssl_certificate     /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;

    # Basic Auth（最小安全措施）
    auth_basic "AI Memory Hub";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8712;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# 生成密码文件
sudo htpasswd -c /etc/nginx/.htpasswd admin
# 员工扩展设置页填入: https://aihub.your-company.com
```

---

## 四、数据存储

### 4.1 存储架构

```
┌────────────────────────────────────────┐
│              数据存储                    │
│                                        │
│  ┌──────────────┐  ┌─────────────────┐ │
│  │   SQLite      │  │    ChromaDB     │ │
│  │  aihub.db    │  │  .chromadb/     │ │
│  │               │  │                  │ │
│  │ · 消息内容     │  │ · 384 维向量     │ │
│  │ · 标题/标签   │  │ · 余弦相似度索引  │ │
│  │ · 摘要        │  │ · HNSW 索引     │ │
│  │ · 会话元数据   │  │                  │ │
│  └──────────────┘  └─────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │  BGE 模型缓存  .models/  ~100MB   │  │
│  │  首次运行自动下载                  │  │
│  └──────────────────────────────────┘  │
└────────────────────────────────────────┘
```

### 4.2 配置方式

所有配置通过 `backend/.env` 文件管理：

```bash
# 创建配置文件
cp backend/.env.example backend/.env

# 编辑 .env，按需修改
vim backend/.env
```

`.env` 文件在启动时自动加载，不会覆盖已有的系统环境变量。

### 4.3 默认存储位置

| 数据 | 路径 | 格式 |
|------|------|------|
| 结构化数据 | `backend/aihub.db` | SQLite 单文件 |
| 向量索引 | `backend/.chromadb/` | ChromaDB 持久化目录 |
| Embedding 模型 | `backend/.models/` | HuggingFace 缓存 |

### 4.4 切换到 PostgreSQL

SQLite 适合 10 万条消息以内的场景。如果数据量更大或需要高并发，编辑 `.env` 文件：

```bash
# backend/.env
DATABASE_URL=postgresql://user:password@localhost:5432/aihub
```

然后安装 PostgreSQL 驱动并重启：

```bash
pip install psycopg2-binary
cd backend && python main.py
```

**注意**：
- 切换数据库后，SQLite 中的旧数据不会自动迁移。需要导出再导入（或从零开始）
- 配合 PostgreSQL 时，建议同步切换向量存储为 pgvector（`VECTOR_STORE=pgvector`）
- 详细升级路径见 `STORAGE.md`
- SQLite 在 WAL 模式下，单机并发读取性能足够支撑 50 人团队

### 4.5 自定义存储路径

编辑 `.env` 文件：

```bash
DATABASE_URL=sqlite:///data/aihub.db   # 自定义 SQLite 路径
CHROMA_PATH=/data/aihub-vectors        # 自定义向量索引路径
```

### 4.6 备份与恢复

**SQLite（推荐每天备份）：**

```bash
# 备份
cp backend/aihub.db backend/aihub.db.$(date +%Y%m%d)

# 恢复
cp backend/aihub.db.20260528 backend/aihub.db
```

**ChromaDB（推荐每周备份）：**

```bash
# 备份
tar -czf chromadb-backup-$(date +%Y%m%d).tar.gz backend/.chromadb/

# 恢复
tar -xzf chromadb-backup-20260528.tar.gz
```

**自动备份脚本（crontab）：**

```bash
# 每天凌晨 3 点备份
0 3 * * * cp /path/to/backend/aihub.db /backup/aihub.db.$(date +\%Y\%m\%d)
```

---

## 五、团队配置

### 5.1 设置用户标识

每个团队成员需要在扩展设置页填入自己的标识：

```
1. 点击浏览器工具栏 🧠 → 侧边栏右上角 ⚙
2. 填入：
   - 后端地址：http://127.0.0.1:8712（本机）或 https://aihub.company.com（服务器）
   - 用户标识：zhang-san / li-si / wang-wu（推荐用拼音，便于检索）
3. 点击「保存」→ 绿点表示连接成功
```

### 5.2 企业 IT 政策建议

建议在员工手册中增加以下内容（模板见 `COMPLIANCE.md`）：

```
公司为保障业务连续性及知识沉淀，会在公司设备上自动记录
员工通过工作账号进行的 AI 平台对话。记录范围限于工作相
关内容，详见《IT 使用政策》。
```

### 5.3 按部门/团队筛选

- Web 面板时间线支持按 `user_id` 筛选
- `/stats` API 返回 `by_user` 统计
- 未来版本：支持部门标签和分组权限

---

## 六、日常使用

### 6.1 侧边栏（核心功能）

```
在任意 AI 平台页面（ChatGPT/Claude/DeepSeek/Gemini/Kimi）
  → 点击浏览器工具栏 🧠 图标
  → 侧边栏滑出
  → 输入你要讨论的话题
  → 选择长度档位（1K~128K）
  → 点击「检索我的记忆」
  → 系统搜索历史 + 图谱发现关联 → 生成上下文
  → 点击「复制上下文」
  → 粘贴到 AI 对话框 → AI 带着历史来回答
```

### 6.2 长度档位选择

| 档位 | 适用模型 | 推荐用途 |
|------|---------|---------|
| 1K | 基础模型 | 简单问答，快速对话 |
| 2K | 基础模型 | 日常讨论（默认） |
| 4K | GPT-4o | 需要完整背景的讨论 |
| 8K | Claude Sonnet | 长上下文模型 |
| 16K | GPT-4 Turbo / DeepSeek-V3 | 深度研究 |
| 32K | GPT-4-32K / Kimi | 多主题交叉讨论 |
| 64K | Gemini 1.5 Flash | 综合知识检索 |
| 128K | GPT-4 128K / Claude 200K | 全量记忆注入 |

> 注意：上下文返回的是**摘要**而非原文，实际输出远小于预算上限。更大档位 = 召回更多关联对话条目。

### 6.3 Web 面板

| 页面 | URL | 功能 |
|------|-----|------|
| 时间线 | `/` | 按日期浏览所有对话，按平台/用户筛选 |
| 对话详情 | `/conversation/:id` | 查看完整消息 + 相关对话推荐 |
| 项目聚合 | `/projects` | 按主题自动聚类的对话分组 |
| 上下文助手 | `/context` | 同侧边栏功能，可深度探索 |
| 知识图谱 | `/graph` | D3.js 可视化知识关联网络 |

### 6.4 采集自动运行

配置完成后，员工在 ChatGPT、Claude、DeepSeek、Kimi、Gemini 上的所有对话自动记录：

- **不需要手动操作** — 扩展后台静默运行
- **流式响应智能去重** — 不会发送不完整的消息
- **采集状态** — 打开 F12 Console 查看 `[AI Memory Hub]` 日志

---

## 七、运维管理

### 7.1 健康检查

```bash
# API 是否正常
curl http://127.0.0.1:8712/stats
# → {"total_messages": 1234, "by_platform": {...}, "by_user": {...}}

# 向量索引是否正常
curl http://127.0.0.1:8712/stats | jq .vector_count
```

### 7.2 查看日志

```bash
# 后端日志（启动时在终端可见）
python main.py

# Docker 模式
docker-compose logs -f aihub
```

### 7.3 监控指标

| 指标 | 获取方式 | 健康范围 |
|------|---------|---------|
| 消息总数 | `GET /stats` | 持续增长 |
| 向量索引数 | `GET /stats` → `vector_count` | 应 ≈ 消息总数 |
| 数据库大小 | `ls -lh backend/aihub.db` | 每条消息约 2-5KB |
| 向量索引大小 | `du -sh backend/.chromadb/` | 每条向量约 1.5KB |
| 磁盘剩余 | `df -h` | > 10GB |

---

## 八、常见问题

**Q: 侧边栏点「检索我的记忆」没反应？**

A: 检查三步：
1. 后端是否启动（`curl http://127.0.0.1:8712/stats`）
2. 扩展设置页后端地址是否正确
3. 设置页连接测试是否绿点

**Q: AI 对话没被自动采集？**

A:
1. 刷新扩展（chrome://extensions → 🔄）
2. 打开 AI 平台页面的 F12 Console
3. 看是否有 `[AI Memory Hub]` 日志
4. 如果看到 `[API 不可用]` → 后端没启动或地址配置不对

**Q: 如何备份数据？**

A:
```bash
# SQLite
cp backend/aihub.db backup/

# ChromaDB
tar -czf chromadb-backup.tar.gz backend/.chromadb/
```

**Q: 如何从 SQLite 迁移到 PostgreSQL？**

A:
1. 先备份 `aihub.db`
2. 设置 `DATABASE_URL` 环境变量
3. 重启后端（新表自动创建）
4. 当前版本不支持自动数据迁移，建议在新部署时选择
5. 旧数据可通过脚本导出 `GET /user-data/{id}` → 导入新库 `POST /messages`

**Q: 支持多少用户同时使用？**

A:
- SQLite + 单进程：20-50 人团队无压力
- PostgreSQL + 多进程：100+ 人
- 瓶颈在 BGE 模型推理（每条消息需要 embedding），可通过 GPU 加速

**Q: ChromaDB 能换成 pgvector 或 Milvus 吗？**

A: 当前不支持。ChromaDB 在 10 万条向量以内性能优秀且零配置。如果需要更大规模，可以在 Issue 中提出需求。

**Q: 如何更新到最新版本？**

A:
```bash
git pull
cd backend && pip install -r requirements.txt
# 重启后端
```
