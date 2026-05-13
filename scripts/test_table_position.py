import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.table_stats import query_position_lookup


def main():
    parser = argparse.ArgumentParser(description="测试 04_排表明细结构化排位查询")

    parser.add_argument(
        "question",
        help="例如：探幽在蕾塞篇场面写B盒中买的炸弹排第几？",
    )

    parser.add_argument(
        "--show-json",
        action="store_true",
        help="显示完整 JSON 结果",
    )

    args = parser.parse_args()

    result = query_position_lookup(args.question)

    print("\n========== 问题 ==========\n")
    print(args.question)

    print("\n========== 识别到的条件 ==========\n")
    for key, value in result.get("entities", {}).items():
        print(f"{key}: {value}")

    print("\n========== 回答 ==========\n")
    print(result["answer"])

    print("\n========== 来源 ==========\n")
    for i, source in enumerate(result.get("sources", []), start=1):
        print("-" * 80)
        print(f"来源 {i}")
        print(f"知识库文件：{source.get('source_file')}")
        print(f"来源Sheet：{source.get('source_sheet')}")
        print(f"来源单元格：{source.get('source_cell')}")
        print(f"记录ID：{source.get('record_id')}")
        print(f"系列：{source.get('series')}")
        print(f"谷子种类：{source.get('item')}")
        print(f"盒型/子分类：{source.get('box')}")
        print(f"角色/款式：{source.get('variant')}")
        print(f"排位：{source.get('position')}")
        print(f"成员：{source.get('member')}")
        print(f"状态：{source.get('status')}")

    if args.show_json:
        print("\n========== JSON ==========\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()