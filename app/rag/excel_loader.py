from pathlib import Path
from typing import Any, List, Optional

import pandas as pd
from langchain_core.documents import Document


def _clean_value(value: Any) -> str:
    """
    把 Excel 单元格的值转成干净字符串。
    """
    if pd.isna(value):
        return ""
    return str(value).strip()


def _row_to_text(row: pd.Series, source_type: str) -> str:
    """
    通用行转文本逻辑。
    适合普通 Excel，比如术语表。
    """
    lines = [f"【资料类型】{source_type}"]

    for col, value in row.items():
        clean = _clean_value(value)
        if clean:
            lines.append(f"{col}：{clean}")

    return "\n".join(lines)


def _rag_block_row_to_text(row: pd.Series, source_type: str) -> str:
    """
    专门处理 06_RAG文本块 sheet。

    这个 sheet 里已经有 标题 + 正文，
    所以不需要把所有列都机械拼进去。
    """
    doc_type = _clean_value(row.get("文档类型", ""))
    title = _clean_value(row.get("标题", ""))
    body = _clean_value(row.get("正文", ""))

    lines = [f"【资料类型】{source_type}"]

    if doc_type:
        lines.append(f"【文档类型】{doc_type}")

    if title:
        lines.append(f"【标题】{title}")

    if body:
        lines.append("")
        lines.append(body)

    # 关联 ID 对回答不一定直接有用，但对定位来源有帮助
    relation_lines = []

    for col in ["开团批次ID", "谷子种类ID", "角色款式ID", "成员ID"]:
        value = _clean_value(row.get(col, ""))
        if value:
            relation_lines.append(f"{col}：{value}")

    if relation_lines:
        lines.append("")
        lines.append("【关联信息】")
        lines.extend(relation_lines)

    return "\n".join(lines)


def load_excel_as_documents(
    file_path: str | Path,
    source_type: str = "谷团知识库",
    sheet_names: Optional[List[str]] = None,
    knowledge_type: str = "general",
) -> List[Document]:
    """
    读取 Excel，把每一行转成一个 LangChain Document。

    参数：
    - file_path：Excel 文件路径
    - source_type：资料类型，比如 谷圈术语、拼谷团排表
    - sheet_names：指定读取哪些 sheet；如果不传，就读取所有 sheet
    - knowledge_type：知识类型，比如 general、structured
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{path}")

    if path.suffix.lower() not in [".xlsx", ".xls"]:
        raise ValueError(f"目前只支持 Excel 文件：{path}")

    excel = pd.ExcelFile(path)

    if sheet_names is None:
        target_sheets = excel.sheet_names
    else:
        missing_sheets = [s for s in sheet_names if s not in excel.sheet_names]
        if missing_sheets:
            raise ValueError(
                f"Excel 中找不到这些 sheet：{missing_sheets}。"
                f"当前文件包含：{excel.sheet_names}"
            )
        target_sheets = sheet_names

    documents: List[Document] = []

    for sheet_name in target_sheets:
        df = pd.read_excel(path, sheet_name=sheet_name)
        df = df.dropna(how="all")

        for index, row in df.iterrows():
            if sheet_name == "06_RAG文本块":
                text = _rag_block_row_to_text(row, source_type=source_type)
            else:
                text = _row_to_text(row, source_type=source_type)

            if not text.strip():
                continue

            metadata = {
                "source_file": path.name,
                "source_path": str(path),
                "sheet_name": sheet_name,
                "row_index": int(index) + 2,
                "source_type": source_type,
                "knowledge_type": knowledge_type,
            }

            # 如果是 06_RAG文本块，把关键字段放进 metadata
            if sheet_name == "06_RAG文本块":
                metadata.update(
                    {
                        "text_block_id": _clean_value(row.get("文本块ID", "")),
                        "document_type": _clean_value(row.get("文档类型", "")),
                        "title": _clean_value(row.get("标题", "")),
                        "series_id": _clean_value(row.get("开团批次ID", "")),
                        "item_id": _clean_value(row.get("谷子种类ID", "")),
                        "variant_id": _clean_value(row.get("角色款式ID", "")),
                        "member_id": _clean_value(row.get("成员ID", "")),
                        "updated_at": _clean_value(row.get("更新时间", "")),
                    }
                )

            doc = Document(
                page_content=text,
                metadata=metadata,
            )
            documents.append(doc)

    return documents


# from pathlib import Path
# from typing import Any, List

# import pandas as pd
# from langchain_core.documents import Document


# def _clean_value(value: Any) -> str:
#     """
#     把 Excel 单元格的值转成干净字符串。
#     """
#     if pd.isna(value):
#         return ""
#     return str(value).strip()


# def _row_to_text(row: pd.Series, source_type: str) -> str:
#     """
#     把 Excel 的一行转成适合做 embedding 的文本。
#     """
#     lines = [f"【资料类型】{source_type}"]

#     for col, value in row.items():
#         clean = _clean_value(value)
#         if clean:
#             lines.append(f"{col}：{clean}")

#     return "\n".join(lines)


# def load_excel_as_documents(
#     file_path: str | Path,
#     source_type: str = "谷团知识库",
# ) -> List[Document]:
#     """
#     读取 Excel，把每一行转成一个 LangChain Document。
#     """
#     path = Path(file_path)

#     if not path.exists():
#         raise FileNotFoundError(f"文件不存在：{path}")

#     if path.suffix.lower() not in [".xlsx", ".xls"]:
#         raise ValueError(f"目前只支持 Excel 文件：{path}")

#     excel = pd.ExcelFile(path)
#     documents: List[Document] = []

#     for sheet_name in excel.sheet_names:
#         df = pd.read_excel(path, sheet_name=sheet_name)

#         # 删除整行为空的行
#         df = df.dropna(how="all")

#         for index, row in df.iterrows():
#             text = _row_to_text(row, source_type=source_type)

#             if len(text.strip()) <= len(f"【资料类型】{source_type}"):
#                 continue

#             doc = Document(
#                 page_content=text,
#                 metadata={
#                     "source_file": path.name,
#                     "source_path": str(path),
#                     "sheet_name": sheet_name,
#                     "row_index": int(index) + 2,
#                     "source_type": source_type,
#                 },
#             )
#             documents.append(doc)

#     return documents