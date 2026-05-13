import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.table_stats import query_member_summary


def main():
    parser = argparse.ArgumentParser(description="测试 04_排表明细结构化成员汇总查询")

    parser.add_argument(
        "question",
        help="例如：逗比南博万排了什么？",
    )

    parser.add_argument(
        "--show-json",
        action="store_true",
        help="显示完整 JSON 结果",
    )

    args = parser.parse_args()

    result = query_member_summary(args.question)

    print("\n========== 问题 ==========\n")
    print(args.question)

    print("\n========== 识别到的条件 ==========\n")
    for key, value in result.get("entities", {}).items():
        print(f"{key}: {value}")

    print("\n========== 回答 ==========\n")
    print(result["answer"])

    print("\n========== 来源数量 ==========\n")
    print(len(result.get("sources", [])))

    if args.show_json:
        print("\n========== JSON ==========\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()