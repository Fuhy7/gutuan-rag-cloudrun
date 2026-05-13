import os

from dotenv import load_dotenv
from langchain_community.embeddings import DashScopeEmbeddings


def get_embedding_model() -> DashScopeEmbeddings:
    """
    创建通义千问 / DashScope embedding 模型。

    embedding 模型负责把文本转成向量。
    """
    load_dotenv()

    api_key = os.getenv("DASHSCOPE_API_KEY")
    model_name = os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v2")

    if not api_key:
        raise ValueError("缺少 DASHSCOPE_API_KEY，请检查项目根目录下的 .env 文件")

    return DashScopeEmbeddings(
        model=model_name,
        dashscope_api_key=api_key,
    )