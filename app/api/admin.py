import threading
import time
import traceback
import uuid
from typing import Any, Dict

from pathlib import Path
from werkzeug.utils import secure_filename

from flask import Blueprint, current_app, jsonify, request

from scripts.ingest_folder_qdrant import run_ingest_from_config


admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


_ingest_lock = threading.Lock()

ALLOWED_RAW_EXTENSIONS = {".xlsx", ".xls", ".xlsm"}


def _get_raw_dir() -> Path:
    """
    原始 Excel 文件存放目录。

    云端容器中对应 /app/data/raw
    本地项目中对应 data/raw
    """
    raw_dir = Path("data/raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir


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


@admin_bp.route("/upload-raw", methods=["POST"])
def upload_raw_file():
    """
    上传原始 Excel 知识库文件到 data/raw。

    请求：
    - Content-Type: multipart/form-data
    - file: Excel 文件

    需要 X-API-Key。
    """
    request_id = str(uuid.uuid4())

    if not _check_api_key():
        return _error_response("未授权访问。", 401, request_id=request_id)

    if "file" not in request.files:
        return _error_response("缺少 file 字段。", 400, request_id=request_id)

    file = request.files["file"]

    if not file or not file.filename:
        return _error_response("上传文件为空。", 400, request_id=request_id)

    original_filename = file.filename
    suffix = Path(original_filename).suffix.lower()

    if suffix not in ALLOWED_RAW_EXTENSIONS:
        return _error_response(
            f"不支持的文件类型：{suffix}。仅支持 {sorted(ALLOWED_RAW_EXTENSIONS)}。",
            400,
            request_id=request_id,
        )

    # secure_filename 会处理路径穿越等风险，但对中文名不友好。
    # 因此这里仅取 basename，保留原始中文文件名，同时禁止路径分隔符。
    safe_name = Path(original_filename).name

    if "/" in safe_name or "\\" in safe_name or safe_name in {"", ".", ".."}:
        return _error_response("文件名不合法。", 400, request_id=request_id)

    raw_dir = _get_raw_dir()
    save_path = raw_dir / safe_name

    file.save(save_path)

    current_app.logger.info(
        "raw file uploaded | request_id=%s | filename=%s | size=%s",
        request_id,
        safe_name,
        save_path.stat().st_size if save_path.exists() else None,
    )

    return jsonify(
        {
            "success": True,
            "request_id": request_id,
            "data": {
                "filename": safe_name,
                "path": str(save_path),
                "size_bytes": save_path.stat().st_size,
            },
        }
    )

@admin_bp.route("/raw-files", methods=["GET"])
def list_raw_files():
    """
    查看云端 data/raw 下已有的原始文件。

    需要 X-API-Key。
    """
    request_id = str(uuid.uuid4())

    if not _check_api_key():
        return _error_response("未授权访问。", 401, request_id=request_id)

    raw_dir = _get_raw_dir()

    files = []

    for path in sorted(raw_dir.iterdir()):
        if not path.is_file():
            continue

        files.append(
            {
                "filename": path.name,
                "path": str(path),
                "size_bytes": path.stat().st_size,
            }
        )

    return jsonify(
        {
            "success": True,
            "request_id": request_id,
            "data": {
                "raw_dir": str(raw_dir),
                "files": files,
            },
        }
    )