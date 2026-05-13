from typing import Any, Dict, List, Optional

from app.rag.query_router import QueryRoute


def _build_route_info(route: QueryRoute) -> Dict[str, Any]:
    """
    把 QueryRoute 转成统一的 route 字段。

    这样前端或调试脚本不需要关心 QueryRoute 类本身，
    只看普通 dict 即可。
    """
    return {
        "intent": route.intent,
        "source": route.route_source,
        "confidence": route.confidence,
        "description": route.description,
        "preferred_knowledge_type": route.preferred_knowledge_type,
        "preferred_document_type": route.preferred_document_type,
        "entities": route.entities,
    }


def build_structured_response(
    *,
    answer: str,
    route: QueryRoute,
    sources: Optional[List[Dict[str, Any]]] = None,
    structured_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    构造结构化表格通道的统一响应。

    适用于：
    - position_lookup
    - member_summary
    - 后续 status_query
    """
    return {
        "answer": answer,
        "intent": route.intent,
        "answer_type": "structured_table",
        "route": _build_route_info(route),
        "sources": sources or [],
        "debug": {
            "raw_hits": [],
            "structured_result": structured_result,
        },
        # 兼容旧脚本 / 旧 Eval 字段
        "route_description": route.description,
        "route_source": route.route_source,
        "route_confidence": route.confidence,
        "route_entities": route.entities,
        "preferred_knowledge_type": route.preferred_knowledge_type,
        "preferred_document_type": route.preferred_document_type,
        "raw_hits": [],
        "structured_result": structured_result,
    }


def build_rag_response(
    *,
    answer: str,
    route: QueryRoute,
    sources: Optional[List[Dict[str, Any]]] = None,
    raw_hits: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    构造 RAG 通道的统一响应。

    适用于：
    - role_list
    - product_summary
    - term_explanation
    - general_rag
    - 结构化查询失败后的兜底
    """
    return {
        "answer": answer,
        "intent": route.intent,
        "answer_type": "rag",
        "route": _build_route_info(route),
        "sources": sources or [],
        "debug": {
            "raw_hits": raw_hits or [],
            "structured_result": None,
        },
        # 兼容旧脚本 / 旧 Eval 字段
        "route_description": route.description,
        "route_source": route.route_source,
        "route_confidence": route.confidence,
        "route_entities": route.entities,
        "preferred_document_type": route.preferred_document_type,
        "preferred_knowledge_type": route.preferred_knowledge_type,
        "raw_hits": raw_hits or [],
        "structured_result": None,
    }


def build_empty_response(
    *,
    answer: str,
    route: QueryRoute,
) -> Dict[str, Any]:
    """
    构造没有找到资料时的统一响应。
    """
    return {
        "answer": answer,
        "intent": route.intent,
        "answer_type": "empty",
        "route": _build_route_info(route),
        "sources": [],
        "debug": {
            "raw_hits": [],
            "structured_result": None,
        },
        # 兼容旧脚本 / 旧 Eval 字段
        "route_description": route.description,
        "route_source": route.route_source,
        "route_confidence": route.confidence,
        "route_entities": route.entities,
        "preferred_document_type": route.preferred_document_type,
        "preferred_knowledge_type": route.preferred_knowledge_type,
        "raw_hits": [],
        "structured_result": None,
    }