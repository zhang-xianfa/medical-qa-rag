# PostgreSQL + pgvector 知识库持久化计划

> 日期: 2026-06-24 | 状态: 执行中

## 当前状态

| 组件 | 状态 | 问题 |
|------|------|------|
| PGVectorStore | 代码已完成 | 未接入——pgvector 扩展未安装 |
| InMemoryVectorStore | 运行中 | 重启即丢失，每次启动重新加载 |
| PostgreSQL 18 | 运行中 (127.0.0.1:5432) | pgvector 扩展不可用 |
| BGE-M3 | 本地可用 | 模型加载正常 |

## 执行步骤

### Step 1: 安装 pgvector 扩展 (5min)

```powershell
# 下载 pgvector Windows 预编译二进制
# https://github.com/pgvector/pgvector/releases
# 解压 vector.dll 到 PostgreSQL lib 目录
# 解压 vector.control + vector--*.sql 到 PostgreSQL extension 目录

# 或使用 Docker 替代方案（推荐）：
docker run -d --name pgvector -p 5433:5432 \
  -e POSTGRES_PASSWORD=root \
  pgvector/pgvector:pg16
```

### Step 2: 配置 .env (1min)

```ini
DATABASE_URL=postgresql+asyncpg://postgres:root@127.0.0.1:5433/medical_qa
VECTOR_STORE_BACKEND=pgvector
```

### Step 3: 验证 PGVectorStore 连接 (1min)

```bash
python -c "
from knowledge.vector_store import get_vector_store
import asyncio
async def t():
    store = get_vector_store()
    await store.create_collection()
    print('pgvector OK, count:', await store.count())
asyncio.run(t())
"
```

### Step 4: 导入知识库 (2min)

```bash
python scripts/load_knowledge.py ../docs/医学参考文献.json
```

### Step 5: 验证持久化 (1min)

```bash
# 重启后数据仍在
python scripts/check_knowledge.py
```

### Step 6: 清理 (1min)

- 删除 `api/main.py` 中的 lifespan 自动加载逻辑（不再需要）
- 保留 `scripts/load_knowledge.py` 用于手动导入

## 风险

| 风险 | 缓解 |
|------|------|
| pgvector Windows 编译复杂 | 使用 Docker pgvector 镜像 |
| 数据迁移 | 数据量小(1条)，重导即可 |
| 连接串变更 | 更新 .env + restart uvicorn |
