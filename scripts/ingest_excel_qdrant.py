import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.excel_loader import load_excel_as_documents
from app.rag.qdrant_store import add_documents_to_qdrant
from app.rag.splitter import split_documents


def main():
    parser = argparse.ArgumentParser(description="导入 Excel 到 Qdrant 向量库")

    parser.add_argument(
        "--file",
        required=True,
        help="Excel 文件路径，例如 data/raw/排表知识库_movic系列.xlsx",
    )

    parser.add_argument(
        "--source-type",
        default="谷团知识库",
        help="资料类型，例如 谷圈术语、拼谷团排表、商品资料",
    )

    parser.add_argument(
    "--knowledge-type",
    default="general",
    choices=["schedule", "terms", "product_info", "group_rules", "general"],
    help="知识库类型，例如 schedule、terms、product_info、group_rules、general",
)


    parser.add_argument(
        "--sheet",
        action="append",
        help="指定读取的 sheet 名。可以传多次，例如 --sheet 06_RAG文本块",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=600,
        help="chunk 大小，默认 600",
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=80,
        help="chunk 重叠大小，默认 80",
    )

    args = parser.parse_args()

    print(f"正在读取 Excel：{args.file}")

    docs = load_excel_as_documents(
        file_path=args.file,
        source_type=args.source_type,
        sheet_names=args.sheet,
        knowledge_type=args.knowledge_type,
        )

    print(f"读取到 {len(docs)} 条原始 Document")

    chunks = split_documents(
        documents=docs,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    print(f"切分后得到 {len(chunks)} 个 Chunk")

    count = add_documents_to_qdrant(chunks)

    print(f"导入完成，共写入 {count} 条数据到 Qdrant")


if __name__ == "__main__":
    main()