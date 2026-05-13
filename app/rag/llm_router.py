import json
import re
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from app.rag.llm import get_chat_model
from app.rag.query_router import QueryRoute


ROUTER_SYSTEM_PROMPT = """你是一个谷团知识库系统的问题意图识别器。

你的任务不是回答问题，而是判断用户问题应该走哪个处理通道。

你只能从以下 intent 中选择一个：
1. term_explanation：术语解释类问题，例如“什么是吃谷”
2. product_summary：商品/谷子说明类问题，例如“movic系列有哪些谷子”
3. role_list：角色/款式清单类问题，例如“B盒有哪些角色”
4. position_lookup：排位查询类问题，例如“探幽在B盒炸弹排第几”
5. member_summary：团员已排/已买汇总类问题，例如“逗比南博万排了什么”
6. available_options：询问某人还能排什么、有什么可以排、推荐可排项
7. status_query：状态/付款/确认/空位/进度类问题
8. source_trace：来源追踪类问题，例如“这个信息来自哪里”
9. general_rag：无法明确归类的普通知识库问答
10. unknown：问题太模糊，无法判断
11. group_rule_query：团规/退款/补款/发货/售后规则类问题，例如“截排后可以退款吗”“补款怎么算”“跑单怎么处理”

你必须只输出 JSON，不要输出解释文字。
JSON 格式必须是：
{
  "intent": "...",
  "confidence": 0.0,
  "preferred_knowledge_type": null,
  "preferred_document_type": null,
  "entities": {
    "member_name": null,
    "series_name": null,
    "item_name": null,
    "box_name": null,
    "variant_name": null,
    "status": null
  },
  "reason": "简短说明"
}

preferred_knowledge_type 可选：
- schedule：排表知识库
- terms：谷圈术语知识库
- product_info：商品/谷子咨询资料
- null：不限制
- group_rules：团规知识库

preferred_document_type 可选：
- 按团员汇总
- 按谷子种类汇总
- 按款式排表
- null

判断建议：
- 问“第几、排位、谁排了、被谁排” → position_lookup
- 问“某人排了什么、买了什么、买了多少” → member_summary
- 问“某人还能排什么、有什么可以排、还有什么没排” → available_options
- 问“有哪些角色、包含哪些款式” → role_list
- 问“未付款、状态、空位、满了吗” → status_query
- 问“来源、哪一行、哪个文件” → source_trace
- 排位、成员、排表、角色清单类问题通常 preferred_knowledge_type = schedule
- 问“退款、补款、跑单、发货、改地址、运费、汇率、团规” → group_rule_query，preferred_knowledge_type = group_rules，preferred_document_type = 团规
- 术语解释类问题通常 preferred_knowledge_type = terms
- 商品资料、尺寸、价格、材质、发售信息类问题通常 preferred_knowledge_type = product_info
- 无法判断时为 null
"""


def _extract_json(text: str) -> Dict[str, Any]:
    """
    从 LLM 输出中提取 JSON。
    防止模型偶尔在 JSON 外多输出字符。
    """
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"LLM Router 没有输出 JSON：{text}")

    return json.loads(match.group(0))


def classify_query_by_llm(question: str) -> QueryRoute:
    """
    使用通义千问进行问题意图识别。

    只在规则路由低置信度时调用，避免每次都增加成本。
    """
    llm = get_chat_model()

    user_prompt = f"""请判断下面用户问题的意图。

用户问题：
{question}
"""

    response = llm.invoke(
        [
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
    )

    data = _extract_json(response.content)

    intent = data.get("intent", "general_rag")
    confidence = float(data.get("confidence", 0.5))
    preferred_document_type = data.get("preferred_document_type")
    preferred_knowledge_type = data.get("preferred_knowledge_type")
    entities = data.get("entities") or {}
    reason = data.get("reason", "")

    allowed_intents = {
    "term_explanation",
    "product_summary",
    "role_list",
    "position_lookup",
    "member_summary",
    "available_options",
    "status_query",
    "source_trace",
    "group_rule_query",
    "general_rag",
    "unknown",
}

    if intent not in allowed_intents:
        intent = "general_rag"
        confidence = 0.4

    # if intent == "role_list":
    #     preferred_document_type = preferred_document_type or "按谷子种类汇总"
    # elif intent == "position_lookup":
    #     preferred_document_type = preferred_document_type or "按款式排表"
    # elif intent == "member_summary":
    #     preferred_document_type = preferred_document_type or "按团员汇总"
    
    if intent == "role_list":
        preferred_knowledge_type = preferred_knowledge_type or "schedule"
        preferred_document_type = preferred_document_type or "按谷子种类汇总"
    elif intent == "position_lookup":
        preferred_knowledge_type = preferred_knowledge_type or "schedule"
        preferred_document_type = preferred_document_type or "按款式排表"
    elif intent == "member_summary":
        preferred_knowledge_type = preferred_knowledge_type or "schedule"
        preferred_document_type = preferred_document_type or "按团员汇总"
    elif intent == "term_explanation":
        preferred_knowledge_type = preferred_knowledge_type or "terms"
    elif intent == "product_summary":
        preferred_knowledge_type = preferred_knowledge_type or "schedule" 
    elif intent == "group_rule_query":
        preferred_knowledge_type = preferred_knowledge_type or "group_rules"
        preferred_document_type = preferred_document_type or "团规"

    return QueryRoute(
        intent=intent,
        preferred_document_type=preferred_document_type,
        preferred_knowledge_type=preferred_knowledge_type,
        confidence=confidence,
        entities=entities,
        route_source="llm",
        description=reason or "LLM Router 识别结果",
    )