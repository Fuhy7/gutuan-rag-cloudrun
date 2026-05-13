from flask import Blueprint, jsonify


health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    """
    健康检查接口。
z
    用途：
    - 确认 Flask 服务是否正常启动
    - 后续部署 / Docker / 云平台也会用到类似接口
    """
    return jsonify(
        {
            "status": "ok",
            "service": "gutuan-rag-api",
        }
    )