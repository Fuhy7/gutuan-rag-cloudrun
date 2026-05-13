import os
import uuid
from typing import Any, Dict, List

import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
from langchain_core.documents import Document

from app.rag.embedding import get_embedding_model


def get_chroma_collection():
    """
    获取 ChromaDB collection。

    collection 可以理解为向量数据库里的一张表。
    """
    load_dotenv()

    chroma_dir = os.getenv("CHROMA_DIR", "./data/chroma")
    collection_name = os.getenv("CHROMA_COLLECTION", "gutuan_knowledge")

    client = chromadb.PersistentClient(
        path=chroma_dir,
        settings=Settings(anonymized_telemetry=False),
    )

    return client.get_or_create_collection(name=collection_name)


def _normalize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    ChromaDB 的 metadata 只能保存简单类型：
    str、int、float、bool、None 通常可接受，但为了稳定，
    这里统一把 None 转成空字符串。

    这样可以避免 Excel 里的空值或时间值导致入库报错。
    """
    normalized = {}

    for key, value in metadata.items():
        if value is None:
            normalized[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            normalized[key] = value
        else:
            normalized[key] = str(value)

    return normalized


def add_documents_to_chroma(documents: List[Document]) -> int:
    """
    把 chunk 写入 ChromaDB。

    每个 chunk 会保存：
    - id
    - document 正文
    - metadata 来源信息
    - embedding 向量
    """
    if not documents:
        return 0

    embedding_model = get_embedding_model()
    collection = get_chroma_collection()

    texts = [doc.page_content for doc in documents]
    metadatas = [_normalize_metadata(doc.metadata) for doc in documents]
    ids = [str(uuid.uuid4()) for _ in documents]

    print(f"正在为 {len(texts)} 个 chunk 生成 embedding...")
    embeddings = embedding_model.embed_documents(texts)

    print("正在写入 ChromaDB...")
    collection.add(
    ids=ids,
    documents=texts,
    metadatas=metadatas,
    embeddings=embeddings,
)

    print("ChromaDB 写入完成")
    print(f"当前 collection 数量：{collection.count()}")

    return len(documents)


def search_chroma(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    根据用户问题，从 ChromaDB 检索最相关的 chunk。
    """
    embedding_model = get_embedding_model()
    collection = get_chroma_collection()

    query_embedding = embedding_model.embed_query(query)

    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    hits = []

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    for doc, metadata, distance in zip(documents, metadatas, distances):
        hits.append(
            {
                "document": doc,
                "metadata": metadata,
                "distance": distance,
            }
        )

    return hits