from app.rag.llm_router import classify_query_by_llm
from app.rag.query_router import QueryRoute, classify_query_by_rules


RULE_CONFIDENCE_THRESHOLD = 0.85
LLM_CONFIDENCE_THRESHOLD = 0.55


def route_question(question: str) -> QueryRoute:
    """
    Hybrid Router v1。

    路由策略：
    1. 先走规则路由。
    2. 如果规则置信度足够高，直接使用规则结果。
    3. 如果规则不确定，再调用 LLM Router。
    4. 如果 LLM 也不确定，兜底到 general_rag。
    """

    rule_route = classify_query_by_rules(question)

    if rule_route.confidence >= RULE_CONFIDENCE_THRESHOLD:
        return rule_route

    try:
        llm_route = classify_query_by_llm(question)

        if llm_route.confidence >= LLM_CONFIDENCE_THRESHOLD:
            return llm_route

    except Exception as exc:
        return QueryRoute(
            intent="general_rag",
            preferred_document_type=None,
            confidence=0.2,
            route_source="fallback",
            description=f"LLM Router 失败，使用 general_rag 兜底：{exc}",
        )

    return QueryRoute(
        intent="general_rag",
        preferred_document_type=None,
        confidence=0.3,
        route_source="fallback",
        description="规则和 LLM 都未能高置信识别，使用 general_rag 兜底",
    )