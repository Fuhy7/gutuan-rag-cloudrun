import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.qdrant_store import search_qdrant


def main():
    parser = argparse.ArgumentParser(description="测试 Qdrant 向量检索")

    parser.add_argument(
        "question",
        help="要检索的问题，例如：蕾塞篇场面写B盒有哪些角色？",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="返回多少条相关 chunk，默认 5",
    )

    args = parser.parse_args()

    hits = search_qdrant(args.question, top_k=args.top_k)

    print(f"\n问题：{args.question}")
    print(f"检索到 {len(hits)} 条结果\n")

    for i, hit in enumerate(hits, start=1):
        metadata = hit["metadata"]
        document = hit["document"]
        score = hit["score"]

        print("=" * 80)
        print(f"结果 {i}")
        print(f"相似度 score：{score}")
        print(f"标题：{metadata.get('title')}")
        print(f"文档类型：{metadata.get('document_type')}")
        print(f"来源文件：{metadata.get('source_file')}")
        print(f"Sheet：{metadata.get('sheet_name')}")
        print(f"行号：{metadata.get('row_index')}")
        print(f"text_block_id：{metadata.get('text_block_id')}")
        print("-" * 80)
        print(document[:1000])
        print()


if __name__ == "__main__":
    main()