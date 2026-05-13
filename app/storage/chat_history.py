import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional


CREATE_CHAT_MESSAGES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    conversation_id TEXT,
    question TEXT NOT NULL,
    answer TEXT,
    intent TEXT,
    answer_type TEXT,
    route_source TEXT,
    route_confidence REAL,
    preferred_knowledge_type TEXT,
    preferred_document_type TEXT,
    sources_json TEXT,
    success INTEGER NOT NULL,
    error_message TEXT,
    duration_ms INTEGER,
    created_at TEXT NOT NULL
);
"""


def init_chat_history_db(db_path: str) -> None:
    """
    初始化聊天记录数据库和表。

    SQLite 是文件型数据库：
    - 不需要单独启动数据库服务
    - db_path 对应一个 .db 文件
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as conn:
        conn.execute(CREATE_CHAT_MESSAGES_TABLE_SQL)
        conn.commit()


def _json_dumps(value: Any) -> str:
    """
    把 Python 对象安全转成 JSON 字符串。
    """
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


def save_chat_message(
    *,
    db_path: str,
    request_id: str,
    user_id: str,
    conversation_id: str,
    question: str,
    answer: Optional[str],
    intent: Optional[str],
    answer_type: Optional[str],
    route_source: Optional[str],
    route_confidence: Optional[float],
    preferred_knowledge_type: Optional[str],
    preferred_document_type: Optional[str],
    sources: Any,
    success: bool,
    error_message: Optional[str],
    duration_ms: Optional[int],
) -> None:
    """
    保存一条聊天请求记录。

    注意：
    - 这里不抛异常给主流程，调用方可以捕获日志。
    - SQLite 写入很快，当前 MVP 阶段足够用。
    """
    created_at = datetime.now(timezone.utc).isoformat()

    sources_json = _json_dumps(sources or [])

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (
                request_id,
                user_id,
                conversation_id,
                question,
                answer,
                intent,
                answer_type,
                route_source,
                route_confidence,
                preferred_knowledge_type,
                preferred_document_type,
                sources_json,
                success,
                error_message,
                duration_ms,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                user_id,
                conversation_id,
                question,
                answer,
                intent,
                answer_type,
                route_source,
                route_confidence,
                preferred_knowledge_type,
                preferred_document_type,
                sources_json,
                1 if success else 0,
                error_message,
                duration_ms,
                created_at,
            ),
        )
        conn.commit()

def cleanup_chat_history(
    *,
    db_path: str,
    retention_days: int = 30,
    max_rows: int = 50000,
) -> Dict[str, int]:
    """
    清理聊天记录，避免 SQLite 数据库无限增长。

    清理规则：
    1. 删除超过 retention_days 天的记录
    2. 如果剩余记录超过 max_rows，只保留最新 max_rows 条

    返回：
    {
        "deleted_by_time": 10,
        "deleted_by_count": 5
    }
    """
    path = Path(db_path)

    if not path.exists():
        return {
            "deleted_by_time": 0,
            "deleted_by_count": 0,
        }

    retention_days = max(1, int(retention_days))
    max_rows = max(1, int(max_rows))

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_text = cutoff.isoformat()

    deleted_by_time = 0
    deleted_by_count = 0

    with sqlite3.connect(path) as conn:
        cursor = conn.execute(
            """
            DELETE FROM chat_messages
            WHERE created_at < ?
            """,
            (cutoff_text,),
        )
        deleted_by_time = cursor.rowcount if cursor.rowcount is not None else 0

        cursor = conn.execute("SELECT COUNT(*) FROM chat_messages")
        total_rows = int(cursor.fetchone()[0])

        if total_rows > max_rows:
            rows_to_delete = total_rows - max_rows

            cursor = conn.execute(
                """
                DELETE FROM chat_messages
                WHERE id IN (
                    SELECT id
                    FROM chat_messages
                    ORDER BY id ASC
                    LIMIT ?
                )
                """,
                (rows_to_delete,),
            )
            deleted_by_count = cursor.rowcount if cursor.rowcount is not None else 0

        conn.commit()

    return {
        "deleted_by_time": deleted_by_time,
        "deleted_by_count": deleted_by_count,
    }


def get_recent_chat_messages(
    *,
    db_path: str,
    limit: int = 20,
    user_id: Optional[str] = None,
) -> list[Dict[str, Any]]:
    """
    查询最近聊天记录。

    当前主要用于开发调试。
    """
    limit = max(1, min(int(limit), 100))

    path = Path(db_path)

    if not path.exists():
        return []

    if user_id:
        sql = """
        SELECT
            request_id,
            user_id,
            conversation_id,
            question,
            answer,
            intent,
            answer_type,
            route_source,
            route_confidence,
            preferred_knowledge_type,
            preferred_document_type,
            sources_json,
            success,
            error_message,
            duration_ms,
            created_at
        FROM chat_messages
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """
        params = (user_id, limit)
    else:
        sql = """
        SELECT
            request_id,
            user_id,
            conversation_id,
            question,
            answer,
            intent,
            answer_type,
            route_source,
            route_confidence,
            preferred_knowledge_type,
            preferred_document_type,
            sources_json,
            success,
            error_message,
            duration_ms,
            created_at
        FROM chat_messages
        ORDER BY id DESC
        LIMIT ?
        """
        params = (limit,)

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()

    results = []

    for row in rows:
        item = dict(row)

        try:
            item["sources"] = json.loads(item.pop("sources_json") or "[]")
        except json.JSONDecodeError:
            item["sources"] = []

        item["success"] = bool(item["success"])

        results.append(item)

    return results