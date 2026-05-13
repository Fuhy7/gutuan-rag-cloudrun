# from dataclasses import dataclass
# from typing import Optional


# @dataclass
# class QueryRoute:
#     """
#     问题路由结果。

#     intent:
#         问题意图，例如 member_summary、role_list、position_lookup。

#     preferred_document_type:
#         推荐优先检索的文档类型。
#         这个值会用于 Qdrant metadata filter。

#     description:
#         给开发者看的说明，方便调试。
#     """

#     intent: str
#     preferred_document_type: Optional[str]
#     description: str


# def classify_query(question: str) -> QueryRoute:
#     """
#     根据用户问题判断问题类型。

#     当前 v1 使用关键词规则。
#     后续可以升级成：
#     - LLM 意图识别
#     - 规则 + LLM 混合
#     - 基于测试集不断补充关键词
#     """

#     q = question.strip()

#     # 1. 术语解释类
#     term_keywords = [
#         "什么是",
#         "是什么意思",
#         "解释一下",
#         "术语",
#         "黑话",
#         "含义",
#     ]

#     # 2. 角色/款式清单类
#     role_list_keywords = [
#         "有哪些角色",
#         "有什么角色",
#         "包含哪些角色",
#         "包含角色",
#         "角色清单",
#         "角色列表",
#         "有哪些款式",
#         "有什么款式",
#         "包含哪些款式",
#         "款式清单",
#         "完整排表",
#         "完整说明",
#         "都有谁",
#     ]

#     # 3. 商品/谷子说明类
#     product_summary_keywords = [
#         "有哪些谷子",
#         "谷子种类",
#         "商品信息",
#         "商品资料",
#         "这个谷",
#         "这个商品",
#         "有哪些盒",
#         "有哪些盒型",
#         "A盒",
#         "B盒",
#     ]

#     # 4. 排位查询类
#     position_keywords = [
#         "第几",
#         "几位",
#         "排位",
#         "第几位",
#         "排第几",
#         "在哪位",
#         "谁排了",
#         "被谁排",
#     ]

#     # 5. 团员汇总类
#     member_summary_keywords = [
#         "排了什么",
#         "买了什么",
#         "买了哪些",
#         "排谷情况",
#         "购买情况",
#         "买了多少",
#         "排了多少",
#         "一共排了",
#         "一共买了",
#         "总共排了",
#         "总共买了",
#         "我的排表",
#         "我排了",
#     ]

#     # 6. 状态查询类
#     status_keywords = [
#         "状态",
#         "付款",
#         "未付款",
#         "已付款",
#         "确认",
#         "未确认",
#         "满了吗",
#         "还有空位",
#         "空位",
#         "余量",
#         "进度",
#     ]

#     # 7. 来源追踪类
#     source_keywords = [
#         "来自哪里",
#         "来源",
#         "原始表",
#         "哪一行",
#         "哪个sheet",
#         "哪个文件",
#         "来源文件",
#         "来源单元格",
#     ]

#     # 注意顺序：
#     # “什么是 A盒” 可能既像术语解释也像商品说明。
#     # v1 先按更明确的业务意图匹配。

#     if any(keyword in q for keyword in source_keywords):
#         return QueryRoute(
#             intent="source_trace",
#             preferred_document_type=None,
#             description="来源追踪类问题",
#         )

#     if any(keyword in q for keyword in member_summary_keywords):
#         return QueryRoute(
#             intent="member_summary",
#             preferred_document_type="按团员汇总",
#             description="团员/成员排谷汇总类问题",
#         )

#     if any(keyword in q for keyword in role_list_keywords):
#         return QueryRoute(
#             intent="role_list",
#             preferred_document_type="按谷子种类汇总",
#             description="角色/款式清单类问题",
#         )

#     if any(keyword in q for keyword in position_keywords):
#         return QueryRoute(
#             intent="position_lookup",
#             preferred_document_type="按款式排表",
#             description="排位查询类问题",
#         )

#     if any(keyword in q for keyword in status_keywords):
#         return QueryRoute(
#             intent="status_query",
#             preferred_document_type="按款式排表",
#             description="状态/进度查询类问题",
#         )

#     if any(keyword in q for keyword in product_summary_keywords):
#         return QueryRoute(
#             intent="product_summary",
#             preferred_document_type="按谷子种类汇总",
#             description="商品/谷子说明类问题",
#         )

#     if any(keyword in q for keyword in term_keywords):
#         return QueryRoute(
#             intent="term_explanation",
#             preferred_document_type=None,
#             description="术语解释类问题",
#         )

#     return QueryRoute(
#         intent="general_rag",
#         preferred_document_type=None,
#         description="通用 RAG 问答",
#     )
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class QueryRoute:
    """
    问题路由结果。

    intent:
        问题意图。

    preferred_document_type:
        推荐优先检索的文档类型，用于 Qdrant metadata filter。

    confidence:
        当前路由置信度，0~1。
        规则命中明确问题时较高；无法判断时较低。

    entities:
        从问题中初步识别到的实体。
        v1 可以为空，后续 LLM Router 会补充。

    route_source:
        路由来源：rule / llm / fallback。

    description:
        给开发者看的说明。
    """

    # intent: str
    # preferred_document_type: Optional[str]
    # confidence: float
    # entities: Dict[str, Optional[str]] = field(default_factory=dict)
    # route_source: str = "rule"
    # description: str = ""
    intent: str
    preferred_document_type: Optional[str]
    confidence: float
    preferred_knowledge_type: Optional[str] = None
    entities: Dict[str, Optional[str]] = field(default_factory=dict)
    route_source: str = "rule"
    description: str = ""


def classify_query_by_rules(question: str) -> QueryRoute:
    """
    规则路由器。

    只处理高确定性问题。
    如果没有明显命中，返回 general_rag + 低置信度，
    后续交给 LLM Router 判断。
    """

    q = question.strip()

    source_keywords = [
        "来自哪里",
        "来源",
        "原始表",
        "哪一行",
        "哪个sheet",
        "哪个文件",
        "来源文件",
        "来源单元格",
    ]

    # member_summary_keywords = [
    #     "排了什么",
    #     "买了几个"
    #     "买了什么",
    #     "买了哪些",
    #     "排谷情况",
    #     "购买情况",
    #     "买了多少",
    #     "排了多少",
    #     "一共排了",
    #     "一共买了",
    #     "总共排了",
    #     "总共买了",
    #     "我的排表",
    #     "我排了",
    # ]

    member_summary_keywords = [
    "排了什么",
    "买了什么",
    "买了哪些",
    "排谷情况",
    "购买情况",
    "买了多少",
    "排了多少",
    "买了几个",
    "排了几个",
    "买几个",
    "排几个",
    "一共排了",
    "一共买了",
    "总共排了",
    "总共买了",
    "我的排表",
    "我排了",
]

    available_options_keywords = [
        "可以排",
        "能排",
        "还能排",
        "有什么可以排",
        "有什么谷子可以排",
        "可以排什么",
        "推荐排什么",
        "还有什么没排",
        "还能买什么",
        "有什么能上车",
        "还能上车",
    ]

    role_list_keywords = [
        "有哪些角色",
        "有什么角色",
        "包含哪些角色",
        "包含角色",
        "角色清单",
        "角色列表",
        "有哪些款式",
        "有什么款式",
        "包含哪些款式",
        "款式清单",
        "完整排表",
        "完整说明",
        "都有谁",
    ]

    position_keywords = [
        "第几",
        "几位",
        "排位",
        "第几位",
        "排第几",
        "在哪位",
        "谁排了",
        "被谁排",
    ]

    status_keywords = [
        "状态",
        "付款",
        "未付款",
        "已付款",
        "确认",
        "未确认",
        "满了吗",
        "还有空位",
        "空位",
        "余量",
        "进度",
    ]

    product_summary_keywords = [
        "有哪些谷子",
        "谷子种类",
        "商品信息",
        "商品资料",
        "这个谷",
        "这个商品",
        "有哪些盒",
        "有哪些盒型",
    ]

    term_keywords = [
        "什么是",
        "是什么意思",
        "解释一下",
        "术语",
        "黑话",
        "含义",
    ]

#     policy_keywords = [
#     "退款",
#     "退换",
#     "售后",
#     "规则",
#     "补款规则",
#     "退款规则",
#     "退货",
#     "取消订单",
# ]
    policy_keywords = [
        "团规",
        "规则",
        "退款",
        "退换",
        "退货",
        "取消",
        "取消订单",
        "补款",
        "余款",
        "定金",
        "尾款",
        "跑单",
        "黑名单",
        "改地址",
        "地址修改",
        "发货",
        "合并发货",
        "国际运费",
        "运费",
        "汇率",
        "截排后",
        "截团后",
        "售后",
]
    


    if any(keyword in q for keyword in source_keywords):
        return QueryRoute(
            intent="source_trace",
            preferred_document_type=None,
            preferred_knowledge_type=None,
            confidence=0.95,
            route_source="rule",
            description="来源追踪类问题",
        )

    if any(keyword in q for keyword in available_options_keywords):
        return QueryRoute(
            intent="available_options",
            preferred_document_type=None,
            confidence=0.9,
            route_source="rule",
            description="可排/推荐选项类问题",
        )

    if any(keyword in q for keyword in member_summary_keywords):
        return QueryRoute(
            intent="member_summary",
            preferred_document_type="按团员汇总",
            preferred_knowledge_type="schedule",
            confidence=0.9,
            route_source="rule",
            description="团员/成员排谷汇总类问题",
        )

    if any(keyword in q for keyword in role_list_keywords):
        return QueryRoute(
            intent="role_list",
            preferred_document_type="按谷子种类汇总",
            preferred_knowledge_type="schedule",
            confidence=0.9,
            route_source="rule",
            description="角色/款式清单类问题",
        )

    if any(keyword in q for keyword in position_keywords):
        return QueryRoute(
            intent="position_lookup",
            preferred_document_type="按款式排表",
            preferred_knowledge_type="schedule",
            confidence=0.9,
            route_source="rule",
            description="排位查询类问题",
        )

    if any(keyword in q for keyword in status_keywords):
        return QueryRoute(
            intent="status_query",
            preferred_document_type="按款式排表",
            confidence=0.85,
            route_source="rule",
            description="状态/进度查询类问题",
        )

    if any(keyword in q for keyword in product_summary_keywords):
        return QueryRoute(
            intent="product_summary",
            preferred_document_type="按谷子种类汇总",
            preferred_knowledge_type=None,
            confidence=0.8,
            route_source="rule",
            description="商品/谷子说明类问题",
        )

    if any(keyword in q for keyword in term_keywords):
        return QueryRoute(
            intent="term_explanation",
            preferred_document_type=None,
            preferred_knowledge_type="terms",
            confidence=0.8,
            route_source="rule",
            description="术语解释类问题",
        )
    
    # if any(keyword in q for keyword in policy_keywords):
    #     return QueryRoute(
    #         intent="general_rag",
    #         preferred_document_type="",
    #         preferred_knowledge_type=None,
    #         confidence=0.9,
    #         route_source="rule",
    #         description="规则/售后/说明类知识库问答",
    # )
    if any(keyword in q for keyword in policy_keywords):
        return QueryRoute(
            intent="group_rule_query",
            preferred_document_type="团规",
            preferred_knowledge_type="group_rules",
            confidence=0.9,
            route_source="rule",
            description="团规/退款/补款/发货/售后规则类问题",
    )

    return QueryRoute(
        intent="general_rag",
        preferred_document_type=None,
        confidence=0.3,
        route_source="rule",
        description="规则未能明确识别，建议交给 LLM Router",
    )