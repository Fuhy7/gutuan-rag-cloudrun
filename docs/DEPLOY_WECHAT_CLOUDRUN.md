1. 部署目标

本项目准备部署为一个 Docker 化 Flask RAG API 服务。

部署后，云端提供：

GET  /health
POST /api/chat
GET  /api/admin/chat-messages
POST /api/admin/ingest

其中：

/health                 健康检查，不需要 X-API-Key
/api/chat               问答接口，需要 X-API-Key
/api/admin/chat-messages 管理员查看聊天记录，需要 X-API-Key
/api/admin/ingest        管理员触发知识库导入，需要 X-API-Key

2. 部署文件清单
需要上传 / 构建进项目的文件

云托管部署至少需要这些：

app/
scripts/
config/
data/raw/
requirements.txt
Dockerfile
.dockerignore
README.md
docs/

其中：

app/                 后端主代码
scripts/             导入、评测、检查脚本
config/              ingest_files.json
data/raw/            原始 Excel 知识库
requirements.txt     Python 依赖
Dockerfile           容器构建文件
.dockerignore        Docker 构建忽略规则

不应该上传进镜像的内容

这些不要进入镜像：

.env
.venv/
venv/
__pycache__/
data/qdrant/
data/app.db
data/chroma/
logs/
.git/

原因：

.env             有真实 API Key，不能进镜像
.venv            本地虚拟环境，体积大且不适合 Linux 容器
data/qdrant      本地向量库数据，不建议打进镜像
data/app.db      本地聊天记录，不建议打进镜像
logs             本地日志，不需要

.dockerignore 应该至少包含：

.venv/
venv/
env/

__pycache__/
*.pyc
*.pyo
*.pyd

.git/
.gitignore

.env
.env.local

data/qdrant/
data/chroma/
data/app.db

logs/
*.log

.vscode/
.idea/

~$*.xlsx

注意：不要忽略 data/raw/。因为简单版部署策略里，原始 Excel 要随项目一起部署。

3. Dockerfile 要求

当前 Dockerfile 应该类似：

FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --upgrade pip

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5001

CMD ["python", "-m", "app.main"]

检查点：

基础镜像：python:3.10-slim
工作目录：/app
启动命令：python -m app.main
暴露端口：5001

4. 云托管环境变量清单

云托管上不要上传 .env，而是在控制台配置环境变量。

需要配置：

DASHSCOPE_API_KEY=你的新 DashScope API Key
QWEN_CHAT_MODEL=qwen-turbo
QWEN_EMBEDDING_MODEL=text-embedding-v2

QDRANT_PATH=./data/qdrant
QDRANT_COLLECTION=gutuan_knowledge

FLASK_HOST=0.0.0.0
FLASK_PORT=5001
FLASK_DEBUG=false

CORS_ENABLED=true

API_DEFAULT_TOP_K=12
API_MAX_TOP_K=30
API_INCLUDE_DEBUG_DEFAULT=false
API_ACCESS_KEY=一个强随机管理密钥

SQLITE_DB_PATH=./data/app.db
CHAT_HISTORY_RETENTION_DAYS=90
CHAT_HISTORY_MAX_ROWS=50000

重点：

FLASK_HOST 必须是 0.0.0.0
FLASK_DEBUG 正式环境设为 false
API_ACCESS_KEY 不要用测试值
DASHSCOPE_API_KEY 不要写进代码或 Dockerfile

5. 服务端口和健康检查

云托管服务端口：

5001

健康检查路径：

/health

健康检查预期响应：

{
  "service": "gutuan-rag-api",
  "status": "ok"
}

6. 本地部署前最终检查

正式上云前，本地先跑一遍：

cd E:\python_pro\rr_RAG

docker compose down
docker compose up --build

另开 PowerShell：

Invoke-RestMethod -Uri "http://127.0.0.1:5001/health"

测试问答：

$apiKey = "你的真实 API_ACCESS_KEY"

$body = @{
  question = "探幽买了几个B盒？"
  top_k = 12
  user_id = "local_test_user"
  conversation_id = "local_test_conv"
} | ConvertTo-Json -Compress

$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)

$response = Invoke-RestMethod `
  -Uri "http://127.0.0.1:5001/api/chat" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Headers @{
    "X-API-Key" = $apiKey
  } `
  -Body $bytes

$response.success
$response.data.intent
$response.data.answer_type

预期：

True
member_summary
structured_table

运行 Eval：

docker compose exec gutuan-rag-api python scripts/run_eval.py

预期：

失败：0
通过率：100%
7. 首次云托管部署流程

首次部署建议按这个顺序：

1. 上传/关联项目代码
2. 配置 Dockerfile 构建
3. 配置服务端口 5001
4. 配置环境变量
5. 部署服务
6. 测试 /health
7. 触发 dry-run 导入
8. 触发真实导入
9. 测试 /api/chat
10. 运行 Eval 或 smoke test
8. 首次部署后的测试顺序
8.1 测试健康检查

假设云端域名是：

https://your-cloudrun-domain

测试：

Invoke-RestMethod -Uri "https://your-cloudrun-domain/health"

预期：

status = ok
8.2 dry-run 导入
$apiKey = "云端 API_ACCESS_KEY"

$body = @{
  dry_run = $true
  config = "config/ingest_files.json"
} | ConvertTo-Json -Compress

$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)

$response = Invoke-RestMethod `
  -Uri "https://your-cloudrun-domain/api/admin/ingest" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Headers @{
    "X-API-Key" = $apiKey
  } `
  -Body $bytes

$response.success
$response.data.summary

dry-run 只检查配置，不写入 Qdrant。

8.3 真实导入
$body = @{
  dry_run = $false
  config = "config/ingest_files.json"
} | ConvertTo-Json -Compress

$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)

$response = Invoke-RestMethod `
  -Uri "https://your-cloudrun-domain/api/admin/ingest" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Headers @{
    "X-API-Key" = $apiKey
  } `
  -Body $bytes

$response.success
$response.data.summary

成功后应看到：

success_count > 0
failed_count = 0
total_written > 0
8.4 测试问答
$body = @{
  question = "什么是吧唧？"
  top_k = 8
  user_id = "cloud_test_user"
  conversation_id = "cloud_test_conv"
} | ConvertTo-Json -Compress

$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)

$response = Invoke-RestMethod `
  -Uri "https://your-cloudrun-domain/api/chat" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Headers @{
    "X-API-Key" = $apiKey
  } `
  -Body $bytes

$response.success
$response.request_id
$response.data.display_answer
$response.data.intent
$response.data.answer_type
9. 简单版知识库更新流程

当前采用简单版：

本地更新 Excel
↓
本地测试
↓
重新部署云托管
↓
云端调用 /api/admin/ingest
↓
云端测试 /api/chat

详细步骤：

9.1 本地更新

更新：

data/raw/*.xlsx
config/ingest_files.json

本地运行：

docker compose exec gutuan-rag-api python scripts/ingest_folder_qdrant.py
docker compose exec gutuan-rag-api python scripts/run_eval.py

确认没问题。

9.2 重新部署云托管

把更新后的项目重新发布到云托管。

注意：

data/raw 要包含最新 Excel
.env 不要上传
data/qdrant 不要上传
data/app.db 不要上传
9.3 云端触发导入

先 dry-run：

POST /api/admin/ingest
dry_run=true

再真实导入：

POST /api/admin/ingest
dry_run=false
9.4 验证

至少测试：

/health
/api/chat 一个结构化问题
/api/chat 一个术语问题
/api/chat 一个团规问题

如果条件允许，再跑 Eval。

10. 云端数据持久化说明

当前项目使用：

QDRANT_PATH=./data/qdrant
SQLITE_DB_PATH=./data/app.db

这意味着：

向量库：data/qdrant
聊天记录：data/app.db

在本地 Docker 里，它们通过 volume 持久化。

在云托管里，需要确认：

容器重启后 data/qdrant 是否还存在
服务重新部署后 data/qdrant 是否还存在
data/app.db 是否会丢

第一版可以接受：

如果 qdrant 丢失，则重新调用 /api/admin/ingest
如果 app.db 丢失，聊天历史丢失但不影响知识库问答

后续正式版建议：

Qdrant 迁移到独立向量数据库或持久化存储
聊天记录迁移到云数据库
原始 Excel 迁移到对象存储
11. 回滚方案

简单版回滚方式：

1. 保留上一版 Excel
2. 保留上一版 config/ingest_files.json
3. 如果新数据有问题，恢复旧文件
4. 重新部署
5. 调用 /api/admin/ingest
6. 重新测试 /api/chat

建议本地保留：

data/raw_backup/

或者给 Excel 文件加版本号，例如：

排表知识库_movic系列_20260512.xlsx
排表知识库_movic系列_20260520.xlsx
12. 常见问题排查
12.1 /health 不通

检查：

容器是否启动
服务端口是否是 5001
FLASK_HOST 是否是 0.0.0.0
云托管是否暴露端口
12.2 /api/chat 返回未授权

检查：

请求头是否是 X-API-Key
X-API-Key 是否等于云端 API_ACCESS_KEY
不要把 API_ACCESS_KEY= 这段也写进请求头

正确：

X-API-Key: gutuan_xxx

错误：

X-API-Key: API_ACCESS_KEY=gutuan_xxx
12.3 /api/chat 返回知识库中没有找到足够信息

检查：

是否已经调用 /api/admin/ingest
Qdrant collection 是否有数据
ingest 是否失败
knowledge_type 是否匹配
12.4 /api/admin/ingest 失败

检查：

config/ingest_files.json 是否存在
data/raw 文件是否存在
sheet 名是否正确
DASHSCOPE_API_KEY 是否正确
embedding API 网络是否正常
12.5 导入接口提示已有任务

说明已有导入在执行：

当前已有导入任务正在执行，请稍后再试。

等待上一次导入完成后再试。

13. 上云前最终状态表
项目	状态
Docker 本地构建	已完成
Flask API	已完成
API Key 鉴权	已完成
request_id/user_id/conversation_id	已完成
SQLite 聊天记录	已完成
自动清理聊天记录	已完成
前端友好返回结构	已完成
管理员导入接口	已完成
云端持久化	待确认
小程序代理层	后续设计
域名 HTTPS	云托管阶段处理