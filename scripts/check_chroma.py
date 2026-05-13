import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

print("开始检查 ChromaDB...")

from app.rag.vector_store import get_chroma_collection

print("正在获取 collection...")

collection = get_chroma_collection()

print("collection 获取成功")

count = collection.count()

print(f"ChromaDB 当前 collection 中共有 {count} 条数据")