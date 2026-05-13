from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

# from app.rag.llm import get_chat_model
# # from app.rag.qdrant_store import search_qdrant
# from app.rag.qdrant_store import get_chunks_by_text_block_id, search_qdrant
from app.rag.answer_prompts import SYSTEM_PROMPT, build_answer_instruction
from app.rag.llm import get_chat_model
from app.rag.qdrant_store import get_chunks_by_text_block_id, search_qdrant
# from app.rag.query_router import QueryRoute, classify_query
from app.rag.hybrid_router import route_question
from app.rag.query_router import QueryRoute
# from app.rag.table_stats import query_position_lookup
from app.rag.table_stats import query_member_summary, query_position_lookup
from app.rag.response_schema import (
    build_empty_response,
    build_rag_response,
    build_structured_response,
)

SYSTEM_PROMPT = """你是一个谷团知识库问答助手，负责根据知识库资料回答关于谷圈术语、拼谷团排表、商品资料的问题。

你必须遵守以下规则：
1. 只能根据【参考资料】回答问题。
2. 如果参考资料中没有足够信息，请明确说“知识库中没有找到足够信息”。
3. 不要编造时间、价格、成员、排位、角色、状态等信息。
4. 如果资料中出现多个相关结果，请综合整理后回答。
5. 如果资料之间存在冲突，请提醒用户“资料可能存在不一致”。
6. 回答要简洁、清楚，优先使用中文。
7. 如果问题询问“有哪些”，请尽量用列表整理。
8. 如果问题询问具体排位、成员或状态，请保留原始资料中的关键字段。
"""


def _format_context(hits: List[Dict[str, Any]]) -> str:
    """
    把 Qdrant 检索结果整理成适合放进 Prompt 的参考资料。

    hits 中每一项包含：
    - document：chunk 正文
    - metadata：来源信息
    - score：相似度分数
    """
    blocks = []

    for i, hit in enumerate(hits, start=1):
        metadata = hit.get("metadata", {})
        document = hit.get("document", "")
        score = hit.get("score", "")

        source_info = (
            f"来源文件：{metadata.get('source_file', '未知文件')}\n"
            f"Sheet：{metadata.get('sheet_name', '未知Sheet')}\n"
            f"行号：{metadata.get('row_index', '未知行号')}\n"
            f"标题：{metadata.get('title', '无标题')}\n"
            f"文档类型：{metadata.get('document_type', '未知类型')}\n"
            f"text_block_id：{metadata.get('text_block_id', '')}\n"
            f"相似度分数：{score}"
        )

        block = (
            f"【参考资料 {i}】\n"
            f"{source_info}\n"
            f"正文：\n{document}"
        )

        blocks.append(block)

    return "\n\n".join(blocks)


def _build_sources(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    从检索结果中整理出来源信息，方便最终展示给用户。
    """
    sources = []

    for hit in hits:
        metadata = hit.get("metadata", {})

        sources.append(
            {
                "title": metadata.get("title"),
                "document_type": metadata.get("document_type"),
                "source_file": metadata.get("source_file"),
                "sheet_name": metadata.get("sheet_name"),
                "row_index": metadata.get("row_index"),
                "text_block_id": metadata.get("text_block_id"),
                "score": hit.get("score"),
                "content_preview": hit.get("document", "")[:300],
            }
        )

    return sources

# def _detect_preferred_document_type(question: str) -> str | None:
#     """
#     根据用户问题，粗略判断优先检索哪种文档类型。

#     这是一个简单的问题路由器。
#     后面可以继续升级成更复杂的意图识别。
#     """
#     q = question.strip()

#     role_summary_keywords = [
#         "有哪些角色",
#         "有什么角色",
#         "包含哪些角色",
#         "包含角色",
#         "有哪些款式",
#         "有什么款式",
#         "包含哪些款式",
#         "包含款式",
#         "完整排表",
#         "完整说明",
#     ]

#     member_keywords = [
#         "团员",
#         "成员",
#         "谁排了",
#         "排了什么",
#         "我的排表",
#         "我排了",
#     ]

#     position_keywords = [
#         "第几",
#         "几位",
#         "排位",
#         "第几位",
#         "排第几",
#     ]

#     if any(keyword in q for keyword in role_summary_keywords):
#         return "按谷子种类汇总"

#     if any(keyword in q for keyword in member_keywords):
#         return "按团员汇总"

#     if any(keyword in q for keyword in position_keywords):
#         return "按款式排表"

#     return None


def _dedupe_hits(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    对检索结果去重。

    为什么要去重？
    因为我们会做：
    - 带 document_type 过滤的检索
    - 普通检索兜底

    两次检索可能返回同一个 chunk。
    """
    seen = set()
    unique_hits = []

    for hit in hits:
        metadata = hit.get("metadata", {})

        key = (
            metadata.get("text_block_id"),
            metadata.get("chunk_index"),
            metadata.get("row_index"),
        )

        if key in seen:
            continue

        seen.add(key)
        unique_hits.append(hit)

    return unique_hits


# def _retrieve_hits_for_question(question: str, top_k: int = 12) -> List[Dict[str, Any]]:
#     """
#     检索优化版召回逻辑。

#     策略：
#     1. 根据问题判断优先文档类型
#     2. 如果有优先文档类型，先做一次过滤检索
#     3. 再做一次普通检索兜底
#     4. 合并去重
#     """
#     preferred_document_type = _detect_preferred_document_type(question)

#     all_hits = []

#     if preferred_document_type:
#         filtered_hits = search_qdrant(
#             query=question,
#             top_k=top_k,
#             document_type=preferred_document_type,
#         )
#         all_hits.extend(filtered_hits)

#     general_hits = search_qdrant(
#         query=question,
#         top_k=top_k,
#     )
#     all_hits.extend(general_hits)

#     # unique_hits = _dedupe_hits(all_hits)

#     # return unique_hits[:top_k]
#     unique_hits = _dedupe_hits(all_hits)
#     expandad_hits = _expand_hits_by_text_block_id(unique_hits)
#     return  expandad_hits[:top_k]

def _retrieve_hits_for_question(
    question: str,
    route: QueryRoute,
    top_k: int = 12,
) -> List[Dict[str, Any]]:
    """
    根据问题路由结果进行检索。

    策略：
    1. 如果 route 指定了 preferred_document_type，先做过滤检索。
    2. 再做一次普通检索兜底。
    3. 合并去重。
    4. 根据 text_block_id 回填完整文本块。
    """

    all_hits = []

    if route.preferred_document_type:
        # filtered_hits = search_qdrant(
        #     query=question,
        #     top_k=top_k,
        #     document_type=route.preferred_document_type,
        # )
        filtered_hits = search_qdrant(
            query=question,
            top_k=top_k,
            document_type=route.preferred_document_type,
            knowledge_type=route.preferred_knowledge_type,
)
        all_hits.extend(filtered_hits)

    general_hits = search_qdrant(
        query=question,
        top_k=top_k,
        knowledge_type=route.preferred_knowledge_type,
    )
    all_hits.extend(general_hits)

    unique_hits = _dedupe_hits(all_hits)

    expanded_hits = _expand_hits_by_text_block_id(unique_hits)

    return expanded_hits[:top_k]

# def answer_question_with_qdrant(question: str, top_k: int = 12) -> Dict[str, Any]:
#     """
#     Qdrant 版 RAG 问答主函数。

#     流程：
#     1. 用用户问题检索 Qdrant
#     2. 把检索结果整理成参考资料
#     3. 把参考资料和问题交给通义千问
#     4. 返回答案和来源
#     """
#     # hits = search_qdrant(question, top_k=top_k)
#     hits = _retrieve_hits_for_question(question, top_k=top_k)

#     if not hits:
#         return {
#             "answer": "知识库中没有找到足够信息。",
#             "sources": [],
#             "raw_hits": [],
#         }

#     context = _format_context(hits)

#     user_prompt = f"""请根据下面的【参考资料】回答【用户问题】。

# 【参考资料】
# {context}

# 【用户问题】
# {question}

# 请直接给出答案。"""

#     llm = get_chat_model()

#     response = llm.invoke(
#         [
#             SystemMessage(content=SYSTEM_PROMPT),
#             HumanMessage(content=user_prompt),
#         ]
#     )

#     return {
#         "answer": response.content,
#         "sources": _build_sources(hits),
#         "raw_hits": hits,
#     }
# def answer_question_with_qdrant(question: str, top_k: int = 12) -> Dict[str, Any]:
#     """
#     Qdrant 版 RAG 问答主函数。

#     流程：
#     1. 判断问题类型
#     2. 根据问题类型优化检索
#     3. 根据问题类型生成回答要求
#     4. 把参考资料和问题交给通义千问
#     5. 返回答案和来源
#     """

#     # route = classify_query(question)
#     route = route_question(question)
#     table_result = None

#     # ============= 新增代码开始 =============
#     #从“RAG 回答”升级成“结构化精确查询”
#     if route.intent == "position_lookup":
#         table_result = query_position_lookup(question)
#         if table_result.get("found"):
#             return {
#                 "answer": table_result["answer"],
#                 "intent": route.intent,
#                 "route_description": route.description,
#                 "route_source": route.route_source,
#                 "route_confidence": route.confidence,
#                 "route_entities": route.entities,
#                 "preferred_document_type": route.preferred_document_type,
#                 "sources": table_result.get("sources", []),
#                 "raw_hits": [],
#                 "structured_result": table_result,
#             }


#     if route.intent == "member_summary":
#         table_result = query_member_summary(question)

#     if table_result.get("found"):
#         return {
#             "answer": table_result["answer"],
#             "intent": route.intent,
#             "route_description": route.description,
#             "route_source": route.route_source,
#             "route_confidence": route.confidence,
#             "route_entities": route.entities,
#             "preferred_document_type": route.preferred_document_type,
#             "sources": table_result.get("sources", []),
#             "raw_hits": [],
#             "structured_result": table_result,
#         }
#     # ============= 新增代码结束 =============


#     # 如果结构化查询没找到，继续走原来的 Qdrant RAG 流程
#     hits = _retrieve_hits_for_question(
#         question=question,
#         route=route,
#         top_k=top_k,
#     )

#     if not hits:
#         return {
#             "answer": "知识库中没有找到足够信息。",
#             "intent": route.intent,
#             "route_description": route.description,
#             "route_source": route.route_source,
#             "route_confidence": route.confidence,
#             "route_entities": route.entities,
#             "preferred_document_type": route.preferred_document_type,
#             "sources": [],
#             "raw_hits": [],
#         }

#     context = _format_context(hits)

#     answer_instruction = build_answer_instruction(route.intent)

#     user_prompt = f"""请根据下面的【参考资料】回答【用户问题】。

# 【问题类型】
# {route.intent}
# {route.description}

# 【参考资料】
# {context}

# 【用户问题】
# {question}

# {answer_instruction}

# 请直接给出答案。"""

#     llm = get_chat_model()

#     response = llm.invoke(
#         [
#             SystemMessage(content=SYSTEM_PROMPT),
#             HumanMessage(content=user_prompt),
#         ]
#     )

#     return {
#         "answer": response.content,
#         "intent": route.intent,
#         "route_description": route.description,
#         "route_source": route.route_source,
#         "route_confidence": route.confidence,
#         "route_entities": route.entities,
#         "preferred_document_type": route.preferred_document_type,
#         "sources": _build_sources(hits),
#         "raw_hits": hits,
#         "structured_result": None,
#     }
# def answer_question_with_qdrant(question: str, top_k: int = 12) -> Dict[str, Any]:
#     """
#     Qdrant 版 RAG 问答主函数。

#     流程：
#     1. Hybrid Router 判断问题类型
#     2. position_lookup 优先走 04_排表明细结构化查询
#     3. member_summary 优先走 04_排表明细结构化统计
#     4. 其他问题走 Qdrant RAG
#     5. 结构化查不到时，自动兜底到 Qdrant RAG
#     """

#     route = route_question(question)

#     # 1. 排位查询：优先走结构化表格
#     if route.intent == "position_lookup":
#         table_result = query_position_lookup(question)

#         if table_result and table_result.get("found"):
#             return {
#                 "answer": table_result["answer"],
#                 "intent": route.intent,
#                 "route_description": route.description,
#                 "route_source": route.route_source,
#                 "route_confidence": route.confidence,
#                 "route_entities": route.entities,
#                 "preferred_document_type": route.preferred_document_type,
#                 "sources": table_result.get("sources", []),
#                 "raw_hits": [],
#                 "structured_result": table_result,
#                 "answer_type": "structured_table",
#             }

#     # 2. 团员汇总：优先走结构化表格
#     if route.intent == "member_summary":
#         table_result = query_member_summary(question)

#         if table_result and table_result.get("found"):
#             return {
#                 "answer": table_result["answer"],
#                 "intent": route.intent,
#                 "route_description": route.description,
#                 "route_source": route.route_source,
#                 "route_confidence": route.confidence,
#                 "route_entities": route.entities,
#                 "preferred_document_type": route.preferred_document_type,
#                 "sources": table_result.get("sources", []),
#                 "raw_hits": [],
#                 "structured_result": table_result,
#                 "answer_type": "structured_table",
#             }

#     # 3. 其他问题，或结构化查询没查到，走 Qdrant RAG
#     hits = _retrieve_hits_for_question(
#         question=question,
#         route=route,
#         top_k=top_k,
#     )

#     if not hits:
#         return {
#             "answer": "知识库中没有找到足够信息。",
#             "intent": route.intent,
#             "route_description": route.description,
#             "route_source": route.route_source,
#             "route_confidence": route.confidence,
#             "route_entities": route.entities,
#             "preferred_document_type": route.preferred_document_type,
#             "sources": [],
#             "raw_hits": [],
#             "structured_result": None,
#             "answer_type": "rag",
#         }

#     context = _format_context(hits)

#     answer_instruction = build_answer_instruction(route.intent)

#     user_prompt = f"""请根据下面的【参考资料】回答【用户问题】。

# 【问题类型】
# {route.intent}
# {route.description}

# 【参考资料】
# {context}

# 【用户问题】
# {question}

# {answer_instruction}

# 请直接给出答案。"""

#     llm = get_chat_model()

#     response = llm.invoke(
#         [
#             SystemMessage(content=SYSTEM_PROMPT),
#             HumanMessage(content=user_prompt),
#         ]
#     )

#     return {
#         "answer": response.content,
#         "intent": route.intent,
#         "route_description": route.description,
#         "route_source": route.route_source,
#         "route_confidence": route.confidence,
#         "route_entities": route.entities,
#         "preferred_document_type": route.preferred_document_type,
#         "sources": _build_sources(hits),
#         "raw_hits": hits,
#         "structured_result": None,
#         "answer_type": "rag",
#     }
def answer_question_with_qdrant(question: str, top_k: int = 12) -> Dict[str, Any]:
    """
    Qdrant 版 RAG 问答主函数。

    流程：
    1. Hybrid Router 判断问题类型
    2. position_lookup 优先走 04_排表明细结构化查询
    3. member_summary 优先走 04_排表明细结构化统计
    4. 其他问题走 Qdrant RAG
    5. 结构化查不到时，自动兜底到 Qdrant RAG
    """

    route = route_question(question)

    # 1. 排位查询：优先走结构化表格
    if route.intent == "position_lookup":
        table_result = query_position_lookup(question)

        if table_result and table_result.get("found"):
            return build_structured_response(
                answer=table_result["answer"],
                route=route,
                sources=table_result.get("sources", []),
                structured_result=table_result,
            )

    # 2. 团员汇总：优先走结构化表格
    if route.intent == "member_summary":
        table_result = query_member_summary(question)

        if table_result and table_result.get("found"):
            return build_structured_response(
                answer=table_result["answer"],
                route=route,
                sources=table_result.get("sources", []),
                structured_result=table_result,
            )

    # 3. 其他问题，或结构化查询没查到，走 Qdrant RAG
    hits = _retrieve_hits_for_question(
        question=question,
        route=route,
        top_k=top_k,
    )

    if not hits:
        return build_empty_response(
            answer="知识库中没有找到足够信息。",
            route=route,
        )

    context = _format_context(hits)

    answer_instruction = build_answer_instruction(route.intent)

    user_prompt = f"""请根据下面的【参考资料】回答【用户问题】。

【问题类型】
{route.intent}
{route.description}

【参考资料】
{context}

【用户问题】
{question}

{answer_instruction}

请直接给出答案。"""

    llm = get_chat_model()

    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
    )

    return build_rag_response(
        answer=response.content,
        route=route,
        sources=_build_sources(hits),
        raw_hits=hits,
    )



def _expand_hits_by_text_block_id(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    根据 text_block_id 回填完整文本块。

    为什么需要？
    因为一个长的 RAG 文本块可能被 splitter 切成多个 chunk。
    向量检索可能只命中其中一个 chunk。
    对于“某人排了什么”“有哪些角色”这种问题，只拿一个 chunk 会导致回答不完整。
    """
    expanded_hits = []

    seen_text_block_ids = set()

    for hit in hits:
        metadata = hit.get("metadata", {})
        text_block_id = metadata.get("text_block_id")

        if not text_block_id:
            expanded_hits.append(hit)
            continue

        if text_block_id in seen_text_block_ids:
            continue

        seen_text_block_ids.add(text_block_id)

        sibling_chunks = get_chunks_by_text_block_id(text_block_id)

        if sibling_chunks:
            expanded_hits.extend(sibling_chunks)
        else:
            expanded_hits.append(hit)

    return _dedupe_hits(expanded_hits)