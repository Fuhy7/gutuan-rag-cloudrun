import threading
import time
import traceback
import uuid
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request

from scripts.ingest_folder_qdrant import run_ingest_from_config


admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


_ingest_lock = threading.Lock()


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
    """
    config = current_app.config["APP_CONFIG"]
    expected_key = config.api_access_key

    if not expected_key:
        return True

    provided_key = request.headers.get("X-API-Key", "")

    return provided_key == expected_key


@admin_bp.route("/ingest", methods=["POST"])
def admin_ingest():
    """
    管理员触发批量导入。

    请求示例：
    {
      "config": "config/ingest_files.json",
      "dry_run": false
    }

    注意：
    - 需要 X-API-Key
    - 使用锁避免并发导入
    """
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    if not _check_api_key():
        return _error_response("未授权访问。", 401, request_id=request_id)

    data: Dict[str, Any] = request.get_json(silent=True) or {}

    config_path = str(data.get("config", "config/ingest_files.json")).strip()
    dry_run = bool(data.get("dry_run", False))

    if not config_path:
        return _error_response("config 不能为空。", 400, request_id=request_id)

    acquired = _ingest_lock.acquire(blocking=False)

    if not acquired:
        return _error_response(
            "当前已有导入任务正在执行，请稍后再试。",
            409,
            request_id=request_id,
        )

    current_app.logger.info(
        "admin ingest started | request_id=%s | config=%s | dry_run=%s",
        request_id,
        config_path,
        dry_run,
    )

    try:
        output = run_ingest_from_config(
            config_path=config_path,
            dry_run=dry_run,
        )

        duration = time.perf_counter() - start_time

        current_app.logger.info(
            "admin ingest finished | request_id=%s | duration=%.2fs | summary=%s",
            request_id,
            duration,
            output.get("summary"),
        )

        return jsonify(
            {
                "success": True,
                "request_id": request_id,
                "data": output,
            }
        )

    except Exception as exc:
        duration = time.perf_counter() - start_time

        current_app.logger.error(
            "admin ingest failed | request_id=%s | duration=%.2fs | error=%s",
            request_id,
            duration,
            exc,
        )
        current_app.logger.error(traceback.format_exc())

        return _error_response(
            f"导入失败：{exc}",
            500,
            request_id=request_id,
        )

    finally:
        _ingest_lock.release()