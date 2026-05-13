import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.qdrant_store import get_collection_name, get_qdrant_client

client = get_qdrant_client()
collection_name = get_collection_name()
try:
    info = client.get_collection(collection_name=collection_name)

    print(f"Qdrant collection：{collection_name}")
    print(f"当前向量数量：{info.points_count}")
finally:
    # 关闭客户端连接
    client.close()