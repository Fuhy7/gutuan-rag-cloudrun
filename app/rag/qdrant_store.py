import os
import uuid
# from typing import Any, Dict, List
from typing import Any, Dict, List, Optional


from dotenv import load_dotenv
from langchain_core.documents import Document
from qdrant_client import QdrantClient
# from qdrant_client.models import Distance, PointStruct, VectorParams

from app.rag.embedding import get_embedding_model

from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

def get_qdrant_client() -> QdrantClient:
    """
    获取 Qdrant 本地客户端。

    path="./data/qdrant" 表示使用本地文件存储，
    暂时不需要 Docker，也不需要单独启动数据库服务。
    """
    load_dotenv()

    qdrant_dir = os.getenv("QDRANT_DIR", "./data/qdrant")

    return QdrantClient(path=qdrant_dir)


def get_collection_name() -> str:
    load_dotenv()
    return os.getenv("QDRANT_COLLECTION", "gutuan_knowledge")


def _normalize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Qdrant 的 payload 可以保存 JSON 风格数据。
    为了稳定，我们也把复杂类型转成字符串。
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

def _build_stable_point_id(doc: Document) -> str:
    """
    为每个 chunk 生成稳定的 Qdrant point ID。

    为什么不用 uuid.uuid4()？
    - uuid.uuid4() 每次都会生成新的随机 ID
    - 重复导入同一个 Excel 会产生重复数据

    为什么用 uuid.uuid5()？
    - uuid.uuid5(namespace, name) 对同一个 name 永远生成同一个 UUID
    - 适合做“稳定 ID”

    ID 组成：
    - source_file：来源文件
    - sheet_name：来源 sheet
    - text_block_id：06_RAG文本块里的文本块ID
    - row_index：Excel 行号
    - chunk_index：切分后的 chunk 编号
    """
    metadata = doc.metadata or {}

    source_file = str(metadata.get("source_file", ""))
    sheet_name = str(metadata.get("sheet_name", ""))
    text_block_id = str(metadata.get("text_block_id", ""))
    row_index = str(metadata.get("row_index", ""))
    chunk_index = str(metadata.get("chunk_index", ""))

    # text_block_id 是最重要的稳定字段。
    # 如果没有 text_block_id，就用 row_index 兜底。
    stable_key = "|".join(
        [
            source_file,
            sheet_name,
            text_block_id or f"row_{row_index}",
            f"chunk_{chunk_index}",
        ]
    )

    return str(uuid.uuid5(uuid.NAMESPACE_URL, stable_key))

def _ensure_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int,
) -> None:
    """
    确保 collection 存在。

    vector_size 必须和 embedding 向量维度一致。
    所以我们会先生成 embedding，再用第一条向量的长度创建 collection。
    """
    existing = client.collection_exists(collection_name=collection_name)

    if existing:
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE,
        ),
    )


def add_documents_to_qdrant(documents: List[Document]) -> int:
    """
    把 chunk 写入 Qdrant。

    每条数据包含：
    - id
    - vector
    - payload，其中保存正文和 metadata
    """
    if not documents:
        return 0

    embedding_model = get_embedding_model()
    client = get_qdrant_client()
    collection_name = get_collection_name()

    texts = [doc.page_content for doc in documents]

    print(f"正在为 {len(texts)} 个 chunk 生成 embedding...", flush=True)
    embeddings = embedding_model.embed_documents(texts)
    print("embedding 生成完成", flush=True)

    vector_size = len(embeddings[0])
    _ensure_collection(client, collection_name, vector_size)

    # points: List[PointStruct] = []

    # for doc, vector in zip(documents, embeddings):
    #     payload = _normalize_metadata(doc.metadata)
    #     payload["document"] = doc.page_content

    #     points.append(
    #         PointStruct(
    #             id=str(uuid.uuid4()),
    #             vector=vector,
    #             payload=payload,
    #         )
    #     )

    #固定ID，避免重复导入产生重复数据
    points: List[PointStruct] = []

    for doc, vector in zip(documents, embeddings):
        payload = _normalize_metadata(doc.metadata)
        payload["document"] = doc.page_content

        points.append(
            PointStruct(
                id=_build_stable_point_id(doc),
                vector=vector,
                payload=payload,
            )
        )



    batch_size = 32
    total = len(points)

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)

        print(f"正在写入 Qdrant：{start + 1}-{end} / {total}", flush=True)

        client.upsert(
            collection_name=collection_name,
            points=points[start:end],
        )

        print(f"已写入：{end} / {total}", flush=True)

    print("Qdrant 写入完成", flush=True)

    return len(documents)


# def search_qdrant(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
#     """
#     根据用户问题，从 Qdrant 检索最相关的 chunk。
#     """
#     embedding_model = get_embedding_model()
#     client = get_qdrant_client()
#     collection_name = get_collection_name()

#     try:
#         query_vector = embedding_model.embed_query(query)

#         response = client.query_points(
#             collection_name=collection_name,
#             query=query_vector,
#             limit=top_k,
#             with_payload=True,
#         )

#         hits = []

#         for item in response.points:
#             payload = item.payload or {}

#             document = payload.get("document", "")

#             metadata = {
#                 key: value
#                 for key, value in payload.items()
#                 if key != "document"
#             }

#             hits.append(
#                 {
#                     "document": document,
#                     "metadata": metadata,
#                     "score": item.score,
#                 }
#             )

#         return hits

#     finally:
#         client.close()
def search_qdrant(
    query: str,
    top_k: int = 5,
    document_type: Optional[str] = None,
    knowledge_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    根据用户问题，从 Qdrant 检索最相关的 chunk。

    参数：
    - query：用户问题
    - top_k：返回多少条结果
    - document_type：可选。指定只检索某一种文档类型，例如“按谷子种类汇总”。

    为什么加 document_type？
    因为你的排表知识库里有多种文档：
    - 按谷子种类汇总
    - 按款式排表
    - 按团员汇总

    不同问题适合查不同类型的文档。
    """
    embedding_model = get_embedding_model()
    client = get_qdrant_client()
    collection_name = get_collection_name()

    try:
        query_vector = embedding_model.embed_query(query)

        query_filter = None

        if document_type:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="document_type",
                        match=MatchValue(value=document_type),
                    )
                ]
            )

        response = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )

        hits = []

        for item in response.points:
            payload = item.payload or {}

            document = payload.get("document", "")

            metadata = {
                key: value
                for key, value in payload.items()
                if key != "document"
            }

            hits.append(
                {
                    "document": document,
                    "metadata": metadata,
                    "score": item.score,
                }
            )

        return hits

    finally:
        client.close()
    
def delete_points_by_source_file(source_file: str) -> int:
    """
    根据 source_file 删除 Qdrant 中某个文件对应的所有 points。

    用途：
    - 某个 Excel 文件更新后，需要重建该文件的数据
    - 先删除旧 points，再重新导入新 points
    - 避免旧 chunk 残留

    注意：
    Qdrant delete 不一定直接返回删除数量。
    所以这里先 scroll 统计匹配数量，再执行删除。
    """
    if not source_file:
        return 0

    client = get_qdrant_client()
    collection_name = get_collection_name()

    try:
        if not client.collection_exists(collection_name=collection_name):
            print(f"collection 不存在，无需删除：{collection_name}")
            return 0

        delete_filter = Filter(
            must=[
                FieldCondition(
                    key="source_file",
                    match=MatchValue(value=source_file),
                )
            ]
        )

        # 先统计将要删除多少条
        matched_count = 0
        next_page_offset = None

        while True:
            points, next_page_offset = client.scroll(
                collection_name=collection_name,
                scroll_filter=delete_filter,
                limit=100,
                offset=next_page_offset,
                with_payload=False,
                with_vectors=False,
            )

            matched_count += len(points)

            if next_page_offset is None:
                break

        if matched_count == 0:
            print(f"未找到需要删除的数据：source_file={source_file}")
            return 0

        client.delete(
            collection_name=collection_name,
            points_selector=FilterSelector(
                filter=delete_filter,
            ),
        )

        print(f"已删除 source_file={source_file} 的旧数据，共 {matched_count} 条")

        return matched_count

    finally:
        client.close()

def get_chunks_by_text_block_id(text_block_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    根据 text_block_id 取回同一个原始文本块下的所有 chunk。

    用途：
    - 向量检索可能只命中一个 chunk
    - 但这个 chunk 可能只是长文本的一部分
    - 通过 text_block_id 可以把同一条原始 RAG 文本块的其他 chunk 一起取回
    """
    if not text_block_id:
        return []

    client = get_qdrant_client()
    collection_name = get_collection_name()

    try:
        scroll_filter = Filter(
            must=[
                FieldCondition(
                    key="text_block_id",
                    match=MatchValue(value=text_block_id),
                )
            ]
        )

        points, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=scroll_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        hits = []

        for point in points:
            payload = point.payload or {}
            document = payload.get("document", "")

            metadata = {
                key: value
                for key, value in payload.items()
                if key != "document"
            }

            hits.append(
                {
                    "document": document,
                    "metadata": metadata,
                    "score": None,
                }
            )

        # 按 chunk_index 排序，尽量恢复原文顺序
        hits.sort(
            key=lambda x: (
                x.get("metadata", {}).get("chunk_index", 0)
            )
        )

        return hits

    finally:
        client.close()        