import os
import logging

# from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from app.config import load_app_config

from app.api.admin import admin_bp
from app.api.chat import chat_bp
from app.api.health import health_bp

from app.storage.chat_history import init_chat_history_db


def create_app() -> Flask:
    """
    创建 Flask 应用。

    这里负责：
    - 读取环境变量
    - 初始化 Flask
    - 注册 API 路由
    - 配置 CORS
    """
    # load_dotenv()
    config = load_app_config()

    app = Flask(__name__)

    app.config["APP_CONFIG"] = config

    init_chat_history_db(config.sqlite_db_path)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    app.logger.setLevel(logging.INFO)

    if config.cors_enabled:
        CORS(app)

    # 开发阶段先允许跨域，方便后续本地前端调试。
    # CORS(app)

    app.register_blueprint(health_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    return app


app = create_app()


# if __name__ == "__main__":
#     host = os.getenv("FLASK_HOST", "127.0.0.1")
#     port = int(os.getenv("FLASK_PORT", "5001"))
#     debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"

#     app.run(
#         host=host,
#         port=port,
#         debug=debug,
#     )
if __name__ == "__main__":
    config = load_app_config()

    app = create_app()

    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", os.getenv("FLASK_PORT", "5001")))

    app.run(
        host=config.flask_host,
        port=config.flask_port,
        debug=config.flask_debug,
    )
