import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.qdrant_store import get_collection_name, get_qdrant_client


def main():
    client = get_qdrant_client()
    collection_name = get_collection_name()

    try:
        if client.collection_exists(collection_name=collection_name):
            client.delete_collection(collection_name=collection_name)
            print(f"已删除 Qdrant collection：{collection_name}")
        else:
            print(f"Qdrant collection 不存在，无需删除：{collection_name}")
    finally:
        client.close()


if __name__ == "__main__":
    main()