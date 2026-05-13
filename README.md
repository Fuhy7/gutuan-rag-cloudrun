# 谷团知识库 RAG 问答系统

这是一个面向谷团场景的本地 RAG 问答系统，用于回答排表、谷圈术语、团规等相关问题。

当前系统支持：

- 拼谷团排表问答
- 谷圈术语解释
- 团规问答
- 成员排谷统计
- 排位查询
- 多类型知识库导入
- Flask API 问答接口
- Docker Compose 启动

---

## 1. 当前能力

### RAG 问答

基于 Qdrant 向量数据库和通义千问模型，支持从知识库中检索相关资料并生成回答。

当前知识类型包括：

| knowledge_type | 说明 |
|---|---|
| schedule | 拼谷团排表 |
| terms | 谷圈术语 |
| group_rules | 团规 |
| product_info | 商品/谷子资料，预留 |
| general | 通用资料 |

### 结构化查询

部分问题不只依赖 RAG，而是直接读取 `04_排表明细` 做精确查询。

当前支持：

- `position_lookup`：排位查询
- `member_summary`：成员排谷汇总

例如：

```text
探幽在蕾塞篇场面写B盒中买的炸弹排第几？
探幽买了几个B盒？
逗比南博万排了什么？
```

---

## 2. 项目结构

```text
rr_RAG/
├─ app/
│  ├─ api/
│  │  ├─ chat.py
│  │  └─ health.py
│  ├─ rag/
│  │  ├─ answer_prompts.py
│  │  ├─ embedding.py
│  │  ├─ excel_loader.py
│  │  ├─ hybrid_router.py
│  │  ├─ llm.py
│  │  ├─ llm_router.py
│  │  ├─ qa_chain_qdrant.py
│  │  ├─ qdrant_store.py
│  │  ├─ query_router.py
│  │  ├─ response_schema.py
│  │  ├─ splitter.py
│  │  └─ table_stats.py
│  ├─ config.py
│  └─ main.py
├─ config/
│  └─ ingest_files.json
├─ data/
│  ├─ raw/
│  ├─ qdrant/
│  └─ eval/
├─ docs/
│  └─ API.md
├─ scripts/
│  ├─ ingest_folder_qdrant.py
│  ├─ run_eval.py
│  ├─ ask_qdrant.py
│  ├─ check_qdrant.py
│  └─ reset_qdrant.py
├─ .env
├─ .env.example
├─ .gitignore
├─ Dockerfile
├─ docker-compose.yml
├─ requirements.txt
└─ README.md
```

---

## 3. 环境准备

### 创建虚拟环境

```powershell
python -m venv .venv
```

### 激活虚拟环境

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 禁止运行脚本，可以先执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

然后再次激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

### 安装依赖

```powershell
pip install -r requirements.txt
```

---

## 4. 环境变量配置

复制 `.env.example` 为 `.env`，并填写真实配置。

```powershell
copy .env.example .env
```

`.env` 示例：

```env
# DashScope / Qwen
DASHSCOPE_API_KEY=your_dashscope_api_key_here
QWEN_CHAT_MODEL=qwen-turbo
QWEN_EMBEDDING_MODEL=text-embedding-v2

# Qdrant local
QDRANT_PATH=./data/qdrant
QDRANT_COLLECTION=gutuan_knowledge

# Flask
FLASK_HOST=127.0.0.1
FLASK_PORT=5001
FLASK_DEBUG=true

# API
CORS_ENABLED=true
API_DEFAULT_TOP_K=12
API_MAX_TOP_K=30
API_INCLUDE_DEBUG_DEFAULT=false
```

注意：不要把真实 `.env` 提交到 Git。

---

## 5. 知识库导入配置

批量导入配置文件：

```text
config/ingest_files.json
```

示例：

```json
[
  {
    "file": "data/raw/排表知识库_movic系列.xlsx",
    "source_type": "拼谷团排表",
    "knowledge_type": "schedule",
    "sheets": ["06_RAG文本块"],
    "chunk_size": 600,
    "chunk_overlap": 80,
    "rebuild": true,
    "enabled": true
  },
  {
    "file": "data/raw/团规知识库.xlsx",
    "source_type": "团规",
    "knowledge_type": "group_rules",
    "sheets": ["团规"],
    "chunk_size": 600,
    "chunk_overlap": 80,
    "rebuild": true,
    "enabled": true
  },
  {
    "file": "data/raw/谷圈术语.xlsx",
    "source_type": "谷圈术语",
    "knowledge_type": "terms",
    "sheets": [
      "基础术语",
      "商品种类",
      "交易买卖",
      "拼团预售",
      "避雷黑话",
      "平台物流",
      "价格行情",
      "圈层关系"
    ],
    "chunk_size": 500,
    "chunk_overlap": 50,
    "rebuild": true,
    "enabled": true
  }
]
```

字段说明：

| 字段 | 说明 |
|---|---|
| file | Excel 文件路径 |
| source_type | 资料类型说明 |
| knowledge_type | 知识库类型 |
| sheets | 要读取的 sheet |
| chunk_size | 文本切块大小 |
| chunk_overlap | 文本切块重叠 |
| rebuild | 导入前是否删除该文件旧数据 |
| enabled | 是否启用该文件导入 |

---

## 6. 批量导入知识库

先检查配置：

```powershell
python scripts/ingest_folder_qdrant.py --dry-run
```

正式导入：

```powershell
python scripts/ingest_folder_qdrant.py
```

检查 Qdrant 数据量：

```powershell
python scripts/check_qdrant.py
```

如果需要清空整个 Qdrant collection：

```powershell
python scripts/reset_qdrant.py
```

---

## 7. 运行 Eval 回归测试

Eval 测试集位置：

```text
data/eval/questions.jsonl
```

运行：

```powershell
python scripts/run_eval.py
```

如果全部通过，会看到类似：

```text
评测完成
总计：10
通过：10
失败：0
通过率：100.00%
```

---

## 8. 启动 Flask API（本地方式）

```powershell
python -m app.main
```

默认地址：

```text
http://127.0.0.1:5001
```

健康检查：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5001/health"
```

---

## 9. Docker 运行方式

本项目支持使用 Docker Compose 启动 Flask API 服务。

### 9.1 前置要求

需要先安装并启动 Docker Desktop。

确认 Docker 可用：

```powershell
docker --version
docker compose version
```

### 9.2 构建并启动服务

在项目根目录运行：

```powershell
docker compose up --build
```

如果已经构建过，可以直接运行：

```powershell
docker compose up
```

后台启动：

```powershell
docker compose up -d
```

### 9.3 停止服务

```powershell
docker compose down
```

### 9.4 查看日志

```powershell
docker compose logs -f
```

### 9.5 健康检查

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5001/health"
```

预期返回：

```json
{
  "service": "gutuan-rag-api",
  "status": "ok"
}
```

### 9.6 测试问答接口

PowerShell 中文 JSON 建议使用 UTF-8 bytes：

```powershell
$body = @{
  question = "探幽买了几个B盒？"
  top_k = 12
} | ConvertTo-Json -Compress

$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)

$response = Invoke-RestMethod `
  -Uri "http://127.0.0.1:5001/api/chat" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $bytes

$response.data.intent
$response.data.answer_type
$response.data.answer
```

### 9.7 在容器内执行脚本

检查 Qdrant 数据量：

```powershell
docker compose exec gutuan-rag-api python scripts/check_qdrant.py
```

运行 Eval：

```powershell
docker compose exec gutuan-rag-api python scripts/run_eval.py
```

批量导入知识库：

```powershell
docker compose exec gutuan-rag-api python scripts/ingest_folder_qdrant.py
```

批量导入前检查配置：

```powershell
docker compose exec gutuan-rag-api python scripts/ingest_folder_qdrant.py --dry-run
```

### 9.8 数据挂载说明

`docker-compose.yml` 中挂载了：

```yaml
volumes:
  - ./data:/app/data
  - ./config:/app/config
```

因此容器中的：

```text
/app/data
/app/config
```

对应本机项目目录下的：

```text
data/
config/
```

这意味着：

- Excel 原始文件保存在本机 `data/raw`
- Qdrant 本地向量库保存在本机 `data/qdrant`
- Eval 文件保存在本机 `data/eval`
- 导入配置保存在本机 `config/ingest_files.json`

即使容器被删除，这些数据也不会丢失。

### 9.9 常见 Docker 问题

#### docker 命令无法识别

说明 Docker Desktop 没有安装，或没有加入 PATH。安装 Docker Desktop 后重新打开 PowerShell。

#### 构建时无法拉取 python:3.10-slim

可能是 Docker Hub 网络问题，可以先手动拉取：

```powershell
docker pull python:3.10-slim
```

然后重新运行：

```powershell
docker compose up --build
```

#### requirements 安装失败，提示 pywin32

`pywin32` 是 Windows 专用依赖，Linux 容器无法安装。请从 `requirements.txt` 中移除：

```text
pywin32
```

#### API 返回知识库中没有找到足够信息

先确认 Qdrant 数据量：

```powershell
docker compose exec gutuan-rag-api python scripts/check_qdrant.py
```

如果数据量为 0，运行：

```powershell
docker compose exec gutuan-rag-api python scripts/ingest_folder_qdrant.py
```

---

## 10. API 文档

接口说明见：

```text
docs/API.md
```

---

## 11. 常用命令速查

### 本地运行

```powershell
python -m app.main
```

### Docker 启动

```powershell
docker compose up
```

### Docker 后台启动

```powershell
docker compose up -d
```

### Docker 停止

```powershell
docker compose down
```

### 查看 Docker 日志

```powershell
docker compose logs -f
```

### 批量导入知识库

```powershell
python scripts/ingest_folder_qdrant.py
```

### Docker 内批量导入知识库

```powershell
docker compose exec gutuan-rag-api python scripts/ingest_folder_qdrant.py
```

### 运行 Eval

```powershell
python scripts/run_eval.py
```

### Docker 内运行 Eval

```powershell
docker compose exec gutuan-rag-api python scripts/run_eval.py
```

---

## 12. 常见问题

### 1. `ModuleNotFoundError: No module named 'app'`

确认你在项目根目录运行命令，不要进入 `scripts/` 或 `app/` 目录运行。

### 2. `ModuleNotFoundError: No module named 'langchain_core'`

通常是虚拟环境没有激活，或依赖没有安装。

检查当前 Python：

```powershell
python -c "import sys; print(sys.executable)"
```

应指向：

```text
E:\python_pro\rr_RAG\.venv\Scripts\python.exe
```

然后安装依赖：

```powershell
pip install -r requirements.txt
```

### 3. PowerShell 中文 JSON 请求导致识别异常

不要直接写：

```powershell
-Body '{"question":"探幽买了几个B盒？"}'
```

建议使用 UTF-8 bytes：

```powershell
$body = @{
  question = "探幽买了几个B盒？"
} | ConvertTo-Json -Compress

$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
```

### 4. Qdrant local 被锁

如果看到：

```text
Storage folder ./data/qdrant is already accessed by another instance
```

可能有旧 Python 进程占用 Qdrant。

可以先关闭 Flask / Python 进程，或运行：

```powershell
Get-Process python -ErrorAction SilentlyContinue
```

必要时：

```powershell
Stop-Process -Name python -Force
```

---

## 13. 当前开发状态

当前是本地 MVP 阶段。

已完成：

- 本地 Qdrant 向量库
- 多知识类型 metadata 隔离
- Hybrid Router
- 结构化查询与统计
- Flask API
- Docker Compose 启动
- Eval 回归测试

后续计划：

- 接入微信公众号 / 小程序
- 增加用户与权限
- 增加聊天记录
- 增加后台导入接口
