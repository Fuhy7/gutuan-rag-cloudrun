import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.excel_loader import load_excel_as_documents
# from app.rag.qdrant_store import add_documents_to_qdrant
from app.rag.qdrant_store import add_documents_to_qdrant, delete_points_by_source_file
from app.rag.splitter import split_documents


def load_ingest_config(config_path: str | Path) -> List[Dict[str, Any]]:
    """
    读取批量导入配置文件。

    配置文件是 JSON 数组，每个元素代表一个要导入的 Excel。
    """
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在：{path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("导入配置必须是 JSON 数组")

    return data


def ingest_one_file(config: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """
    导入单个文件。

    dry_run=True 时只打印计划，不真正入库。
    """
    file_path = config.get("file")
    source_type = config.get("source_type", "谷团知识库")
    knowledge_type = config.get("knowledge_type", "general")
    sheets = config.get("sheets")
    chunk_size = int(config.get("chunk_size", 600))
    chunk_overlap = int(config.get("chunk_overlap", 80))
    enabled = bool(config.get("enabled", True))
    rebuild = bool(config.get("rebuild", False))

    if not enabled:
        print(f"跳过未启用文件：{file_path}")
        return {
            "file": file_path,
            "status": "skipped",
            "reason": "enabled=false",
            "documents": 0,
            "chunks": 0,
            "written": 0,
            "deleted": 0,
        }

    if not file_path:
        raise ValueError(f"配置缺少 file 字段：{config}")

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{path}")

    print("=" * 100)
    print(f"准备导入：{file_path}")
    print(f"source_type：{source_type}")
    print(f"knowledge_type：{knowledge_type}")
    print(f"sheets：{sheets}")
    print(f"chunk_size：{chunk_size}")
    print(f"chunk_overlap：{chunk_overlap}")
    print(f"rebuild：{rebuild}")

    if dry_run:
        print("dry-run 模式：不实际读取和写入")
        return {
            "file": file_path,
            "status": "dry_run",
            "documents": 0,
            "chunks": 0,
            "written": 0,
            "deleted": 0,
        }
    
    deleted = 0

    if rebuild:
        deleted = delete_points_by_source_file(path.name)

    docs = load_excel_as_documents(
        file_path=file_path,
        source_type=source_type,
        sheet_names=sheets,
        knowledge_type=knowledge_type,
    )

    print(f"读取到 {len(docs)} 条原始 Document")

    chunks = split_documents(
        documents=docs,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    print(f"切分后得到 {len(chunks)} 个 Chunk")

    written = add_documents_to_qdrant(chunks)

    print(f"导入完成：写入 {written} 条")

    return {
        "file": file_path,
        "status": "success",
        "documents": len(docs),
        "chunks": len(chunks),
        "written": written,
        "deleted": deleted,
    }

def run_ingest_from_config(
    config_path: str | Path = "config/ingest_files.json",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    从配置文件批量导入多个 Excel。

    这个函数既给命令行脚本使用，也给 Flask admin API 使用。
    """
    configs = load_ingest_config(config_path)

    print(f"读取到 {len(configs)} 个导入配置")
    print(f"配置文件：{config_path}")

    results = []

    for config in configs:
        try:
            result = ingest_one_file(config=config, dry_run=dry_run)
        except Exception as exc:
            file_path = config.get("file", "未知文件")
            print("=" * 100)
            print(f"导入失败：{file_path}")
            print(f"错误：{exc}")

            result = {
                "file": file_path,
                "status": "failed",
                "error": str(exc),
                "documents": 0,
                "chunks": 0,
                "written": 0,
                "deleted": 0,
            }

        results.append(result)

    success_count = sum(1 for item in results if item["status"] == "success")
    skipped_count = sum(1 for item in results if item["status"] == "skipped")
    failed_count = sum(1 for item in results if item["status"] == "failed")
    dry_run_count = sum(1 for item in results if item["status"] == "dry_run")
    total_written = sum(item.get("written", 0) for item in results)
    total_deleted = sum(item.get("deleted", 0) for item in results)

    summary = {
        "success_count": success_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "dry_run_count": dry_run_count,
        "total_written": total_written,
        "total_deleted": total_deleted,
    }

    return {
        "config": str(config_path),
        "dry_run": dry_run,
        "results": results,
        "summary": summary,
    }


# def main():
#     parser = argparse.ArgumentParser(description="批量导入多个 Excel 到 Qdrant")

#     parser.add_argument(
#         "--config",
#         default="config/ingest_files.json",
#         help="导入配置文件路径，默认 config/ingest_files.json",
#     )

#     parser.add_argument(
#         "--dry-run",
#         action="store_true",
#         help="只检查配置和打印导入计划，不实际写入 Qdrant",
#     )

#     args = parser.parse_args()

#     configs = load_ingest_config(args.config)

#     print(f"读取到 {len(configs)} 个导入配置")
#     print(f"配置文件：{args.config}")

#     results = []

#     for config in configs:
#         try:
#             result = ingest_one_file(config=config, dry_run=args.dry_run)
#         except Exception as exc:
#             file_path = config.get("file", "未知文件")
#             print("=" * 100)
#             print(f"导入失败：{file_path}")
#             print(f"错误：{exc}")

#             result = {
#                 "file": file_path,
#                 "status": "failed",
#                 "error": str(exc),
#                 "documents": 0,
#                 "chunks": 0,
#                 "written": 0,
#                 "deleted": 0,
#             }

#         results.append(result)

#     print("=" * 100)
#     print("批量导入完成")

#     success_count = sum(1 for item in results if item["status"] == "success")
#     skipped_count = sum(1 for item in results if item["status"] == "skipped")
#     failed_count = sum(1 for item in results if item["status"] == "failed")
#     total_written = sum(item.get("written", 0) for item in results)
#     total_deleted = sum(item.get("deleted", 0) for item in results)

#     print(f"成功：{success_count}")
#     print(f"跳过：{skipped_count}")
#     print(f"失败：{failed_count}")
#     print(f"总删除：{total_deleted}")
#     print(f"总写入：{total_written}")

#     print("\n详细结果：")
#     for item in results:
#         print(
#             f"- {item['status']} | {item['file']} | "
#             f"deleted={item.get('deleted', 0)} | "
#             f"docs={item.get('documents', 0)} | "
#             f"chunks={item.get('chunks', 0)} | "
#             f"written={item.get('written', 0)}"
            
#         )

def main():
    parser = argparse.ArgumentParser(description="批量导入多个 Excel 到 Qdrant")

    parser.add_argument(
        "--config",
        default="config/ingest_files.json",
        help="导入配置文件路径，默认 config/ingest_files.json",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只检查配置和打印导入计划，不实际写入 Qdrant",
    )

    args = parser.parse_args()

    output = run_ingest_from_config(
        config_path=args.config,
        dry_run=args.dry_run,
    )

    print("=" * 100)
    print("批量导入完成")

    summary = output["summary"]

    print(f"成功：{summary['success_count']}")
    print(f"跳过：{summary['skipped_count']}")
    print(f"失败：{summary['failed_count']}")
    print(f"dry-run：{summary['dry_run_count']}")
    print(f"总删除：{summary['total_deleted']}")
    print(f"总写入：{summary['total_written']}")

    print("\n详细结果：")
    for item in output["results"]:
        print(
            f"- {item['status']} | {item['file']} | "
            f"deleted={item.get('deleted', 0)} | "
            f"docs={item.get('documents', 0)} | "
            f"chunks={item.get('chunks', 0)} | "
            f"written={item.get('written', 0)}"
        )


if __name__ == "__main__":
    main()