import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _get_bool_env(name: str, default: bool = False) -> bool:
    """
    从环境变量读取布尔值。

    支持：
    true / false
    1 / 0
    yes / no
    on / off
    """
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"true", "1", "yes", "y", "on"}


def _get_int_env(name: str, default: int) -> int:
    """
    从环境变量读取整数。
    如果没有配置或配置不合法，就使用默认值。
    """
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class AppConfig:
    """
    应用配置。

    这个类集中管理 Flask API 的常用配置。
    """

    flask_host: str
    flask_port: int
    flask_debug: bool

    cors_enabled: bool

    api_default_top_k: int
    api_max_top_k: int
    api_include_debug_default: bool
    api_access_key: str

    sqlite_db_path: str
    chat_history_retention_days: int
    chat_history_max_rows: int


def load_app_config() -> AppConfig:
    """
    读取 .env 并生成 AppConfig。
    """
    load_dotenv()

    return AppConfig(
        # flask_host=os.getenv("FLASK_HOST", "127.0.0.1"),
        # flask_port=_get_int_env("FLASK_PORT", 5001),
        # flask_debug=_get_bool_env("FLASK_DEBUG", True),
        flask_host=os.getenv("FLASK_HOST", "0.0.0.0"),
        flask_port=_get_int_env("FLASK_PORT", _get_int_env("PORT", 5001)),
        flask_debug=_get_bool_env("FLASK_DEBUG", False),
        cors_enabled=_get_bool_env("CORS_ENABLED", True),
        api_default_top_k=_get_int_env("API_DEFAULT_TOP_K", 12),
        api_max_top_k=_get_int_env("API_MAX_TOP_K", 30),
        api_include_debug_default=_get_bool_env("API_INCLUDE_DEBUG_DEFAULT", False),
        api_access_key=os.getenv("API_ACCESS_KEY", ""),
        sqlite_db_path=os.getenv("SQLITE_DB_PATH", "./data/app.db"),
        chat_history_retention_days=_get_int_env("CHAT_HISTORY_RETENTION_DAYS", 30),
        chat_history_max_rows=_get_int_env("CHAT_HISTORY_MAX_ROWS", 50000),
    )
