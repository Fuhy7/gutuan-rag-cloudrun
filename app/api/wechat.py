import time
import traceback
import uuid
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request

from app.api.chat import _simplify_result
from app.rag.qa_chain_qdrant import answer_question_with_qdrant
from app.storage.chat_history import cleanup_chat_history, save_chat_message


wechat_bp = Blueprint("wechat", __name__, url_prefix="/api/wechat")


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


@wechat_bp.route("/chat", methods=["POST"])
def wechat_chat():
    """
    小程序开发版聊天接口。

    注意：
    - 当前版本暂不接微信登录鉴权。
    - user_id 暂时使用 wechat_dev_user。
    - 后续正式版需要用微信登录 code 换 openid。
    """
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    config = current_app.config["APP_CONFIG"]

    data: Dict[str, Any] = request.get_json(silent=True) or {}

    question = str(data.get("question", "")).strip()

    if not question:
        return _error_response("question 不能为空。", 400, request_id=request_id)

    top_k = data.get("top_k", config.api_default_top_k)

    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        return _error_response("top_k 必须是整数。", 400, request_id=request_id)

    if top_k <= 0:
        return _error_response("top_k 必须大于 0。", 400, request_id=request_id)

    if top_k > config.api_max_top_k:
        return _error_response(
            f"top_k 不能大于 {config.api_max_top_k}。",
            400,
            request_id=request_id,
        )

    # 开发版临时 user_id。
    # 后续正式接微信登录后，这里要替换成 openid。
    user_id = "wechat_dev_user"

    conversation_id = str(
        data.get("conversation_id")
        or f"wechat_conv_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    )

    include_debug = bool(data.get("debug", False))

    current_app.logger.info(
        "wechat chat request received | request_id=%s | user_id=%s | conversation_id=%s | question=%s | top_k=%s",
        request_id,
        user_id,
        conversation_id,
        question,
        top_k,
    )

    try:
        result = answer_question_with_qdrant(
            question=question,
            top_k=top_k,
        )

        duration = time.perf_counter() - start_time
        duration_ms = int(duration * 1000)

        current_app.logger.info(
            "wechat chat request finished | request_id=%s | user_id=%s | conversation_id=%s | intent=%s | answer_type=%s | route_source=%s | duration=%.2fs",
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

            current_app.logger.info(
                "wechat chat history cleanup checked | request_id=%s | max_rows=%s | deleted_by_time=%s | deleted_by_count=%s",
                request_id,
                config.chat_history_max_rows,
                cleanup_result["deleted_by_time"],
                cleanup_result["deleted_by_count"],
            )

        except Exception as save_exc:
            current_app.logger.error(
                "failed to save wechat chat message | request_id=%s | error=%s",
                request_id,
                save_exc,
            )

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

    except Exception as exc:
        duration = time.perf_counter() - start_time
        duration_ms = int(duration * 1000)

        current_app.logger.error(
            "wechat chat request failed | request_id=%s | user_id=%s | conversation_id=%s | question=%s | duration=%.2fs | error=%s",
            request_id,
            user_id,
            conversation_id,
            question,
            duration,
            exc,
        )
        current_app.logger.error(traceback.format_exc())

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
        except Exception as save_exc:
            current_app.logger.error(
                "failed to save failed wechat chat message | request_id=%s | error=%s",
                request_id,
                save_exc,
            )

        return _error_response(
            f"问答处理失败：{exc}",
            500,
            request_id=request_id,
        )