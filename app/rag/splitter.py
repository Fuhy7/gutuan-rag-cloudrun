from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_documents(
    documents: List[Document],
    chunk_size: int = 600,
    chunk_overlap: int = 80,
) -> List[Document]:
    """
    把 Document 切分成更小的 chunk。

    参数说明：
    - documents：原始 Document 列表
    - chunk_size：每个 chunk 的目标长度
    - chunk_overlap：相邻 chunk 之间的重叠长度

    返回：
    - 切分后的 Document 列表

    注意：
    切分后返回的仍然是 Document。
    page_content 会变成切分后的文本片段；
    metadata 会尽量继承原始 Document 的来源信息。
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n\n",
            "\n",
            "。",
            "！",
            "？",
            "；",
            "，",
            " ",
            "",
        ],
    )

    chunks = splitter.split_documents(documents)

    # 给每个 chunk 增加 chunk_index，方便以后调试和引用
    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = index

    return chunks