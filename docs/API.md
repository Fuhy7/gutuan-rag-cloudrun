# API 文档

谷团知识库 RAG 问答系统当前提供两个接口：

```text
GET  /health
POST /api/chat
```

默认服务地址：

```text
http://127.0.0.1:5001
```

---

## 1. 健康检查

### 请求

```http
GET /health
```

### PowerShell 示例

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5001/health"
```

### 响应示例

```json
{
  "service": "gutuan-rag-api",
  "status": "ok"
}
```

### 用途

用于确认 Flask API 服务是否正常运行。

---

## 2. 问答接口

### 请求

```http
POST /api/chat
Content-Type: application/json; charset=utf-8
```

### 请求体

```json
{
  "question": "探幽买了几个B盒？",
  "top_k": 12,
  "debug": false
}
```

### 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| question | string | 是 | 无 | 用户问题 |
| top_k | integer | 否 | 由 `.env` 中 `API_DEFAULT_TOP_K` 决定 | RAG 检索数量 |
| debug | boolean | 否 | 由 `.env` 中 `API_INCLUDE_DEBUG_DEFAULT` 决定 | 是否返回调试信息 |

### top_k 限制

`top_k` 最大值由 `.env` 中的配置控制：

```env
API_MAX_TOP_K=30
```

如果请求超过最大值，会返回错误。

---

## 3. PowerShell 请求示例

中文 JSON 推荐使用 UTF-8 bytes 方式发送：

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

$response.data.answer
```

不建议直接写：

```powershell
-Body '{"question":"探幽买了几个B盒？"}'
```

因为 PowerShell 中直接写中文 JSON 可能出现编码问题。

---

## 4. 成功响应

### 响应示例

```json
{
  "success": true,
  "data": {
    "answer": "根据 04_排表明细，找到 探幽 的 7 条有效排谷记录...",
    "intent": "member_summary",
    "answer_type": "structured_table",
    "route": {
      "intent": "member_summary",
      "source": "rule",
      "confidence": 0.9,
      "description": "团员/成员排谷汇总类问题",
      "preferred_knowledge_type": "schedule",
      "preferred_document_type": "按团员汇总",
      "entities": {
        "member_name": "探幽",
        "box_name": "B盒"
      }
    },
    "sources": []
  }
}
```

---

## 5. 响应字段说明

### 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| success | boolean | 请求是否成功 |
| data | object | 问答结果 |
| error | object | 错误信息，仅失败时出现 |

### data 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| answer | string | 最终回答 |
| intent | string | 问题意图 |
| answer_type | string | 回答类型 |
| route | object | 路由信息 |
| sources | array | 来源信息 |

### answer_type

| 值 | 说明 |
|---|---|
| structured_table | 结构化表格查询/统计结果 |
| rag | RAG 检索生成结果 |
| empty | 没有找到足够信息 |

### intent

当前常见 intent：

| intent | 说明 |
|---|---|
| term_explanation | 谷圈术语解释 |
| product_summary | 商品/谷子说明 |
| role_list | 角色/款式清单 |
| position_lookup | 排位查询 |
| member_summary | 成员排谷汇总 |
| status_query | 状态/付款/确认/进度查询 |
| source_trace | 来源追踪 |
| group_rule_query | 团规/退款/补款/发货/售后规则 |
| general_rag | 通用知识库问答 |

### knowledge_type

| knowledge_type | 说明 |
|---|---|
| schedule | 拼谷团排表 |
| terms | 谷圈术语 |
| group_rules | 团规 |
| product_info | 商品/谷子资料 |
| general | 通用资料 |

---

## 6. debug 模式

请求时传：

```json
{
  "question": "探幽买了几个B盒？",
  "top_k": 12,
  "debug": true
}
```

会额外返回：

```json
{
  "debug": {},
  "raw_hits": [],
  "structured_result": {}
}
```

这些字段用于开发调试，不建议前端默认展示。

---

## 7. 错误响应

### 缺少 question

请求：

```json
{}
```

响应：

```json
{
  "success": false,
  "error": {
    "message": "缺少 question 字段，或 question 为空。"
  }
}
```

### top_k 不是整数

请求：

```json
{
  "question": "探幽买了几个B盒？",
  "top_k": "abc"
}
```

响应：

```json
{
  "success": false,
  "error": {
    "message": "top_k 必须是整数。"
  }
}
```

### top_k 超过最大值

请求：

```json
{
  "question": "探幽买了几个B盒？",
  "top_k": 999
}
```

响应：

```json
{
  "success": false,
  "error": {
    "message": "top_k 不能大于 30。"
  }
}
```

---

## 8. 示例问题

### 成员汇总

```json
{
  "question": "探幽买了几个B盒？"
}
```

预期：

```text
intent = member_summary
answer_type = structured_table
```

### 排位查询

```json
{
  "question": "探幽在蕾塞篇场面写B盒中买的炸弹排第几？"
}
```

预期：

```text
intent = position_lookup
answer_type = structured_table
```

### 术语解释

```json
{
  "question": "什么是吧唧？"
}
```

预期：

```text
intent = term_explanation
answer_type = rag
```

### 团规查询

```json
{
  "question": "下单规则是什么？"
}
```

预期：

```text
intent = group_rule_query
answer_type = rag
```

### 来源追踪

```json
{
  "question": "蕾塞篇场面写B盒的信息来自哪里？"
}
```

预期：

```text
intent = source_trace
answer_type = rag
```
