import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.qa_chain_qdrant import answer_question_with_qdrant


def main():
    parser = argparse.ArgumentParser(description="谷团知识库 Qdrant RAG 问答测试")

    parser.add_argument(
        "question",
        help="用户问题，例如：蕾塞篇场面写B盒有哪些角色？",
    )

    # parser.add_argument(
    #     "--top-k",
    #     type=int,
    #     default=5,
    #     help="检索多少条相关资料，默认 5",
    # )
    parser.add_argument(
    "--top-k",
    type=int,
    default=12,
    help="检索多少条相关资料，默认 12",
)

    parser.add_argument(
        "--show-raw",
        action="store_true",
        help="是否显示原始检索结果",
    )

    args = parser.parse_args()

    result = answer_question_with_qdrant(
        question=args.question,
        top_k=args.top_k,
    )

    # print("\n========== 问题 ==========\n")
    # print(args.question)

    # print("\n========== 回答 ==========\n")
    # print(result["answer"])
    print("\n========== 问题 ==========\n")
    print(args.question)

    # print("\n========== 问题类型 ==========\n")
    # print(f"intent：{result.get('intent')}")
    # print(f"description：{result.get('route_description')}")
    # print(f"preferred_document_type：{result.get('preferred_document_type')})")
    # print("\n========== 问题类型 ==========\n")
    # print(f"intent：{result.get('intent')}")
    # print(f"description：{result.get('route_description')}")
    # print(f"route_source：{result.get('route_source')}")
    # print(f"confidence：{result.get('route_confidence')}")
    # print(f"preferred_document_type：{result.get('preferred_document_type')}")
    # print(f"entities：{result.get('route_entities')}")
    print("\n========== 问题类型 ==========\n")
    print(f"intent：{result.get('intent')}")
    print(f"answer_type：{result.get('answer_type')}")
    print(f"description：{result.get('route_description')}")
    print(f"route_source：{result.get('route_source')}")
    print(f"confidence：{result.get('route_confidence')}")
    print(f"preferred_knowledge_type：{result.get('preferred_knowledge_type')}")
    print(f"preferred_document_type：{result.get('preferred_document_type')}")
    print(f"entities：{result.get('route_entities')}")




    print("\n========== 回答 ==========\n")
    print(result["answer"])

    print("\n========== 来源 ==========\n")

    for i, source in enumerate(result["sources"], start=1):
        print("-" * 80)
        print(f"来源 {i}")
        print(f"标题：{source.get('title')}")
        print(f"文档类型：{source.get('document_type')}")
        print(f"来源文件：{source.get('source_file')}")
        print(f"Sheet：{source.get('sheet_name')}")
        print(f"行号：{source.get('row_index')}")
        print(f"text_block_id：{source.get('text_block_id')}")
        print(f"相似度 score：{source.get('score')}")
        print("内容预览：")
        print(source.get("content_preview"))

    if args.show_raw:
        print("\n========== 原始结果 JSON ==========\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()