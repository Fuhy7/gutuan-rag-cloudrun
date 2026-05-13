import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.qdrant_store import delete_points_by_source_file


def main():
    parser = argparse.ArgumentParser(description="按 source_file 删除 Qdrant 数据")

    parser.add_argument(
        "source_file",
        help="source_file 文件名，例如 团规知识库.xlsx",
    )

    args = parser.parse_args()

    deleted = delete_points_by_source_file(args.source_file)

    print(f"删除完成：{args.source_file}，删除 {deleted} 条")


if __name__ == "__main__":
    main()