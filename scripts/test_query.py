import sys
from pathlib import Path

# 把项目根目录加入 Python 模块搜索路径
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.excel_loader import load_excel_as_documents
from app.rag.splitter import split_documents


# docs = load_excel_as_documents(
#     file_path="data/raw/谷圈术语.xlsx",
#     source_type="谷圈术语",
# )
docs = load_excel_as_documents(
    file_path="data/raw/排表知识库_movic系列.xlsx",
    source_type="拼谷团排表",
    sheet_names=["06_RAG文本块"],
)

print(f"读取到 {len(docs)} 条原始 Document")

chunks = split_documents(
    documents=docs,
    chunk_size=600,
    chunk_overlap=80,
)

print(f"切分后得到 {len(chunks)} 个 Chunk")

for chunk in chunks:
    print("=" * 40)
    print(chunk.page_content)
    print(chunk.metadata)