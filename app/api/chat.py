import time
import traceback
import uuid
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request

from app.rag.qa_chain_qdrant import answer_question_with_qdrant
from app.storage.chat_history import (
    cleanup_chat_history,
    get_recent_chat_messages,
    save_chat_message,
)

chat_bp = Blueprint("chat", __name__, url_prefix="/api")


# def _error_response(message: str, status_code: int = 400):
#     """
#     统一错误返回格式。
#     """
#     response = jsonify(
#         {
#             "success": False,
#             "error": {
#                 "message": message,
#             },
#         }
#     )
#     return response, status_code

def _error_response(
    message: str,
    status_code: int = 400,
    request_id: str | None = None,
):
    payload = {
        "success": False,
        "error": {
            "message": message,
        },
    }

    if request_id:
        payload["request_id"] = request_id

    response = jsonify(payload)
    return response, status_code

def _check_api_key() -> bool:
    """
    检查请求头里的 X-API-Key。

    如果 .env 没有配置 API_ACCESS_KEY，则开发阶段默认不启用校验。
    如果配置了 API_ACCESS_KEY，则请求必须携带正确的 X-API-Key。
    """
    config = current_app.config["APP_CONFIG"]

    expected_key = config.api_access_key

    if not expected_key:
        return True

    provided_key = request.headers.get("X-API-Key", "")

    return provided_key == expected_key

def _build_source_cards(sources: Any) -> list[Dict[str, Any]]:
    """
    把后端 sources 转成前端更容易展示的 source_cards。

    前端不需要理解完整 metadata，只需要：
    - title：来源标题
    - subtitle：来源位置
    - text：简短内容
    - metadata：必要追踪字段
    """
    if not sources:
        return []

    cards = []

    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            continue

        title = (
            source.get("title")
            or source.get("source_file")
            or source.get("metadata", {}).get("title")
            or source.get("metadata", {}).get("source_file")
            or f"来源 {index}"
        )

        metadata = source.get("metadata") or {}

        source_file = (
            source.get("source_file")
            or metadata.get("source_file")
            or ""
        )

        sheet_name = (
            source.get("sheet_name")
            or metadata.get("sheet_name")
            or ""
        )

        row_index = (
            source.get("row_index")
            or metadata.get("row_index")
            or ""
        )

        text_block_id = (
            source.get("text_block_id")
            or metadata.get("text_block_id")
            or ""
        )

        document_type = (
            source.get("document_type")
            or metadata.get("document_type")
            or ""
        )

        subtitle_parts = []

        if source_file:
            subtitle_parts.append(str(source_file))

        if sheet_name:
            subtitle_parts.append(str(sheet_name))

        if row_index != "":
            subtitle_parts.append(f"行号 {row_index}")

        subtitle = " / ".join(subtitle_parts)

        text = (
            source.get("content_preview")
            or source.get("preview")
            or source.get("text")
            or source.get("document")
            or ""
        )

        if text and len(text) > 300:
            text = text[:300] + "..."

        cards.append(
            {
                "title": str(title),
                "subtitle": subtitle,
                "text": text,
                "metadata": {
                    "source_file": source_file,
                    "sheet_name": sheet_name,
                    "row_index": row_index,
                    "text_block_id": text_block_id,
                    "document_type": document_type,
                },
            }
        )

    return cards

def _simplify_result(result: Dict[str, Any], include_debug: bool = False) -> Dict[str, Any]:
    """
    精简并前端化问答结果。

    默认返回前端展示所需字段：
    - display_answer
    - intent
    - answer_type
    - source_cards
    - meta

    debug=true 时再返回后端内部字段。
    """
    sources = result.get("sources", [])

    simplified = {
        "display_answer": result.get("answer", ""),
        "answer": result.get("answer", ""),
        "intent": result.get("intent"),
        "answer_type": result.get("answer_type"),
        "source_cards": _build_source_cards(sources),
        "meta": {
            "route_source": result.get("route_source"),
            "route_confidence": result.get("route_confidence"),
            "preferred_knowledge_type": result.get("preferred_knowledge_type"),
            "preferred_document_type": result.get("preferred_document_type"),
        },
    }

    if include_debug:
        simplified["route"] = result.get("route", {})
        simplified["sources"] = sources
        simplified["debug"] = result.get("debug", {})
        simplified["raw_hits"] = result.get("raw_hits", [])
        simplified["structured_result"] = result.get("structured_result")

    return simplified


# def _simplify_result(result: Dict[str, Any], include_debug: bool = False) -> Dict[str, Any]:
#     """
#     精简问答结果。

#     默认给前端返回稳定、轻量的数据：
#     - answer
#     - intent
#     - answer_type
#     - route
#     - sources

#     调试模式下再返回：
#     - debug
#     - raw_hits
#     - structured_result
#     """
#     simplified = {
#         "answer": result.get("answer"),
#         "intent": result.get("intent"),
#         "answer_type": result.get("answer_type"),
#         "route": result.get("route", {}),
#         "sources": result.get("sources", []),
#     }

#     # 为了兼容旧字段，也可以保留几个常用字段
#     simplified["route_source"] = result.get("route_source")
#     simplified["route_confidence"] = result.get("route_confidence")
#     simplified["preferred_knowledge_type"] = result.get("preferred_knowledge_type")
#     simplified["preferred_document_type"] = result.get("preferred_document_type")

#     if include_debug:
#         simplified["debug"] = result.get("debug", {})
#         simplified["raw_hits"] = result.get("raw_hits", [])
#         simplified["structured_result"] = result.get("structured_result")

#     return simplified


@chat_bp.route("/chat", methods=["POST"])
def chat():
    """
    RAG 问答接口。

    请求示例：
    {
      "question": "探幽买了几个B盒？",
      "top_k": 12
    }

    返回：
    {
      "success": true,
      "data": {
        "answer": "...",
        "intent": "...",
        "answer_type": "...",
        "sources": [...]
      }
    }
    """

    start_time = time.perf_counter()
    request_id = str(uuid.uuid4())

    if not _check_api_key():
        return _error_response("未授权访问。", 401, request_id=request_id)

    data: Dict[str, Any] = request.get_json(silent=True) or {}

    question = str(data.get("question", "")).strip()
    user_id = str(data.get("user_id", "anonymous")).strip() or "anonymous"
    conversation_id = str(data.get("conversation_id", "")).strip()

    
    # current_app.logger.info(
    #     "chat request received | question=%s | top_k=%s | debug=%s",
    #     question,
    #     data.get("top_k", 12),
    #     data.get("debug", False),
    # )

    if not question:
        return _error_response("缺少 question 字段，或 question 为空。", 400, request_id=request_id)

    # top_k = data.get("top_k", 12)

    # include_debug = bool(data.get("debug", False))
    config = current_app.config["APP_CONFIG"]

    top_k = data.get("top_k", config.api_default_top_k)
    include_debug = bool(data.get("debug", config.api_include_debug_default))

    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        return _error_response("top_k 必须是整数。", 400, request_id=request_id)

    if top_k <= 0:
        return _error_response("top_k 必须大于 0。", 400, request_id=request_id)

    # if top_k > 30:
    #     return _error_response("top_k 不能大于 30。", 400)
    if top_k > config.api_max_top_k:
        return _error_response(f"top_k 不能大于 {config.api_max_top_k}。", 400, request_id=request_id)
    
    current_app.logger.info(
        "chat request received | request_id=%s | user_id=%s | conversation_id=%s | question=%s | top_k=%s | debug=%s",
        request_id,
        user_id,
        conversation_id,
        question,
        top_k,
        include_debug,
    )


    try:
        result = answer_question_with_qdrant(
            question=question,
            top_k=top_k,
        )

        duration = time.perf_counter() - start_time
        duration_ms = int(duration * 1000)

        # current_app.logger.info(
        #     "chat request finished | intent=%s | answer_type=%s | route_source=%s | duration=%.2fs",
        #     result.get("intent"),
        #     result.get("answer_type"),
        #     result.get("route_source"),
        #     duration,
        # )

        current_app.logger.info(
            "chat request finished | request_id=%s | user_id=%s | conversation_id=%s | intent=%s | answer_type=%s | route_source=%s | duration=%.2fs",
            request_id,
            user_id,
            conversation_id,
            result.get("intent"),
            result.get("answer_type"),
            result.get("route_source"),
            duration,
        )

        try:
            save_chat_message(
                db_path=config.sqlite_db_path,
                request_id=request_id,
                user_id=user_id,
                conversation_id=conversation_id,
                question=question,
                answer=result.get("answer"),
                intent=result.get("intent"),
                answer_type=result.get("answer_type"),
                route_source=result.get("route_source"),
                route_confidence=result.get("route_confidence"),
                preferred_knowledge_type=result.get("preferred_knowledge_type"),
                preferred_document_type=result.get("preferred_document_type"),
                sources=result.get("sources", []),
                success=True,
                error_message=None,
                duration_ms=duration_ms,
            )

            cleanup_result = cleanup_chat_history(
                db_path=config.sqlite_db_path,
                retention_days=config.chat_history_retention_days,
                max_rows=config.chat_history_max_rows,
            )

            # if cleanup_result["deleted_by_time"] or cleanup_result["deleted_by_count"]:
            #     current_app.logger.info(
            #         "chat history cleaned | request_id=%s | deleted_by_time=%s | deleted_by_count=%s",
            #         request_id,
            #         cleanup_result["deleted_by_time"],
            #         cleanup_result["deleted_by_count"],
            #     )
            current_app.logger.info(
                "chat history cleanup checked | request_id=%s | max_rows=%s | deleted_by_time=%s | deleted_by_count=%s",
                request_id,
                config.chat_history_max_rows,
                cleanup_result["deleted_by_time"],
                cleanup_result["deleted_by_count"],
            )


           
        except Exception as save_exc:
            current_app.logger.error(
                "failed to save chat message | request_id=%s | error=%s",
                request_id,
                save_exc,
        )


        # result.setdefault("debug", {})
        # result["debug"]["received_question"] = question

    # except Exception as exc:
    #     # 开发阶段先把错误返回出来，方便调试。
    #     # 后续生产环境可以改成记录日志，不直接暴露异常细节。
    #     return _error_response(f"问答处理失败：{exc}", 500)

    except Exception as exc:
        duration = time.perf_counter() - start_time

        # current_app.logger.error(
        #     "chat request failed | question=%s | duration=%.2fs | error=%s",
        #     question,
        #     duration,
        #     exc,
        # )
        current_app.logger.error(
            "chat request failed | request_id=%s | user_id=%s | conversation_id=%s | question=%s | duration=%.2fs | error=%s",
            request_id,
            user_id,
            conversation_id,
            question,
            duration,
            exc,
        )

        

        current_app.logger.error(traceback.format_exc())

        duration_ms = int(duration * 1000)

        try:
            save_chat_message(
                db_path=config.sqlite_db_path,
                request_id=request_id,
                user_id=user_id,
                conversation_id=conversation_id,
                question=question,
                answer=None,
                intent=None,
                answer_type=None,
                route_source=None,
                route_confidence=None,
                preferred_knowledge_type=None,
                preferred_document_type=None,
                sources=[],
                success=False,
                error_message=str(exc),
                duration_ms=duration_ms,
            )
            cleanup_result = cleanup_chat_history(
                db_path=config.sqlite_db_path,
                retention_days=config.chat_history_retention_days,
                max_rows=config.chat_history_max_rows,
            )

            if cleanup_result["deleted_by_time"] or cleanup_result["deleted_by_count"]:
                current_app.logger.info(
                    "chat history cleaned | request_id=%s | deleted_by_time=%s | deleted_by_count=%s",
                    request_id,
                    cleanup_result["deleted_by_time"],
                    cleanup_result["deleted_by_count"],
                ) 


        except Exception as save_exc:
            current_app.logger.error(
                "failed to save failed chat message | request_id=%s | error=%s",
                request_id,
                save_exc,
            )

        return _error_response(f"问答处理失败：{exc}", 500, request_id=request_id)


    return jsonify(
        {
            "success": True,
            "request_id": request_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "data": _simplify_result(
                result,
                include_debug=include_debug,
            ),
        }
    )

@chat_bp.route("/admin/chat-messages", methods=["GET"])
def list_chat_messages():
    """
    查看最近聊天记录。

    开发调试用。
    需要 X-API-Key。
    """
    request_id = str(uuid.uuid4())

    if not _check_api_key():
        return _error_response("未授权访问。", 401, request_id=request_id)

    config = current_app.config["APP_CONFIG"]

    limit = request.args.get("limit", 20)
    user_id = request.args.get("user_id")

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return _error_response("limit 必须是整数。", 400, request_id=request_id)

    messages = get_recent_chat_messages(
        db_path=config.sqlite_db_path,
        limit=limit,
        user_id=user_id,
    )

    return jsonify(
        {
            "success": True,
            "request_id": request_id,
            "data": {
                "messages": messages,
            },
        }
    )