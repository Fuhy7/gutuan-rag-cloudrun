from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

import re


DETAIL_SHEET_NAME = "04_排表明细"


def _clean_value(value: Any) -> str:
    """
    把 Excel 单元格值转成干净字符串。
    """
    if pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_text(value: Any) -> str:
    """
    用于比较的文本标准化。
    当前先做基础处理：转字符串、去空格。
    """
    return _clean_value(value).replace(" ", "").replace("\n", "")


def load_schedule_details(raw_dir: str | Path = "./data/raw") -> pd.DataFrame:
    """
    读取 data/raw 下所有 Excel 文件中的 04_排表明细。

    返回一个合并后的 DataFrame。

    为什么读取所有 Excel？
    因为后续会有多个系列文件，例如：
    - 排表知识库_movic系列.xlsx
    - 排表知识库_AJ2026.xlsx
    - 排表知识库_xxx系列.xlsx

    用户问某个人排了什么时，应该能跨系列查询。
    """
    raw_path = Path(raw_dir)

    if not raw_path.exists():
        raise FileNotFoundError(f"数据目录不存在：{raw_path}")

    excel_files = [
        path
        for path in raw_path.glob("*.xlsx")
        if not path.name.startswith("~$")
    ]

    frames = []

    for file_path in excel_files:
        excel = pd.ExcelFile(file_path)

        if DETAIL_SHEET_NAME not in excel.sheet_names:
            continue

        df = pd.read_excel(file_path, sheet_name=DETAIL_SHEET_NAME)
        df = df.dropna(how="all")

        # 补充来源文件，方便后面展示引用来源
        df["知识库文件"] = file_path.name
        df["知识库路径"] = str(file_path)

        frames.append(df)

    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True)

    # 把所有 NaN 先转成空字符串，后续筛选更稳定
    merged = merged.fillna("")

    return merged


def _unique_values(df: pd.DataFrame, column: str) -> List[str]:
    """
    取某一列的唯一非空值。
    """
    if column not in df.columns:
        return []

    values = []

    for value in df[column].tolist():
        clean = _clean_value(value)
        if clean:
            values.append(clean)

    return sorted(set(values), key=len, reverse=True)


def _exact_or_contains_match(question: str, candidates: List[str]) -> Optional[str]:
    """
    优先做包含匹配。

    例如：
    question = "探幽在蕾塞篇场面写B盒中买的炸弹排第几？"
    candidates 里有 "探幽"、"B盒"、"炸弹"
    就能直接识别。
    """
    q = _normalize_text(question)

    for candidate in candidates:
        c = _normalize_text(candidate)
        if not c:
            continue

        if c in q:
            return candidate

    return None


def _fuzzy_match(question: str, candidates: List[str], threshold: float = 0.35) -> Optional[str]:
    """
    简单模糊匹配。

    用途：
    有些谷子种类在表里是“蕾塞篇场面写吧唧”，
    用户可能只问“蕾塞篇场面写B盒”。

    这时完整字符串不一定包含，但相似度较高。
    """
    q = _normalize_text(question)

    best_candidate = None
    best_score = 0.0

    for candidate in candidates:
        c = _normalize_text(candidate)
        if not c:
            continue

        # 包含关系优先
        if c in q or q in c:
            return candidate

        score = SequenceMatcher(None, q, c).ratio()

        if score > best_score:
            best_score = score
            best_candidate = candidate

    if best_score >= threshold:
        return best_candidate

    return None

def _extract_variant_from_question(
    question: str,
    candidates: List[str],
) -> Optional[str]:
    """
    从问题中更精确地抽取角色/款式。

    解决的问题：
    “探幽在蕾塞篇场面写B盒中买的炸弹排第几？”
    这里“蕾塞篇场面写”里的“蕾塞”是谷子种类的一部分，
    真正的角色/款式是“炸弹”。

    所以不能只用简单包含匹配。
    """

    q = _normalize_text(question)

    # 常见句式：
    # xxx买的炸弹排第几
    # xxx中的炸弹排第几
    # 炸弹在xxx排第几
    patterns = [
        r"买的(.+?)排",
        r"中的(.+?)排",
        r"中(.+?)排",
        r"(.+?)在.+?排第几",
        r"(.+?)在.+?第几",
    ]

    extracted_parts = []

    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            extracted_parts.append(match.group(1))

    # 先用句式抽取出的片段匹配候选角色
    for part in extracted_parts:
        for candidate in candidates:
            c = _normalize_text(candidate)
            if not c:
                continue

            if c in part or part in c:
                return candidate

    # 如果句式没有命中，再退回普通包含匹配
    return _exact_or_contains_match(question, candidates)


def extract_position_entities(question: str, df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    从用户问题中抽取排位查询需要的实体。

    当前 v1 从 04_排表明细 的已有字段里反向匹配：
    - CN
    - 谷子种类
    - 盒型/子分类
    - 角色/款式

    好处：
    不需要一开始就做复杂 NLP。
    """
    member_candidates = _unique_values(df, "CN")
    item_candidates = _unique_values(df, "谷子种类")
    box_candidates = _unique_values(df, "盒型/子分类")
    variant_candidates = _unique_values(df, "角色/款式")
    series_candidates = _unique_values(df, "系列")

    # member_name = _exact_or_contains_match(question, member_candidates)
    # box_name = _exact_or_contains_match(question, box_candidates)
    # variant_name = _exact_or_contains_match(question, variant_candidates)
    # series_name = _exact_or_contains_match(question, series_candidates)
    member_name = _exact_or_contains_match(question, member_candidates)
    box_name = _exact_or_contains_match(question, box_candidates)
    variant_name = _extract_variant_from_question(question, variant_candidates)
    series_name = _exact_or_contains_match(question, series_candidates)

    # 谷子种类经常用户只说一部分，所以用模糊匹配兜底
    item_name = _exact_or_contains_match(question, item_candidates)
    if not item_name:
        item_name = _fuzzy_match(question, item_candidates, threshold=0.35)

    return {
        "member_name": member_name,
        "series_name": series_name,
        "item_name": item_name,
        "box_name": box_name,
        "variant_name": variant_name,
    }

def extract_member_summary_entities(question: str, df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    从用户问题中抽取团员汇总需要的实体。

    主要识别：
    - member_name：成员 CN
    - series_name：系列，可选
    - item_name：谷子种类，可选
    - box_name：盒型/子分类，可选
    - variant_name：角色/款式，可选

    为什么除了成员名还要识别其他字段？
    因为用户可能问：
    - 探幽排了什么？
    - 探幽在 movic 系列排了什么？
    - 探幽买了几个 B盒？
    - 探幽买了几个炸弹？
    """
    member_candidates = _unique_values(df, "CN")
    series_candidates = _unique_values(df, "系列")
    item_candidates = _unique_values(df, "谷子种类")
    box_candidates = _unique_values(df, "盒型/子分类")
    variant_candidates = _unique_values(df, "角色/款式")

    member_name = _exact_or_contains_match(question, member_candidates)
    series_name = _exact_or_contains_match(question, series_candidates)
    box_name = _exact_or_contains_match(question, box_candidates)

    item_name = _exact_or_contains_match(question, item_candidates)
    if not item_name:
        item_name = _fuzzy_match(question, item_candidates, threshold=0.35)

    # 成员汇总问题里，角色/款式可以先用普通匹配。
    # 如果后续发现“蕾塞篇”误识别成“蕾塞”，再复用 position 的专用抽取逻辑。
    variant_name = _exact_or_contains_match(question, variant_candidates)

    return {
        "member_name": member_name,
        "series_name": series_name,
        "item_name": item_name,
        "box_name": box_name,
        "variant_name": variant_name,
    }


def _contains_filter(series: pd.Series, value: Optional[str]) -> pd.Series:
    """
    对 pandas Series 做包含筛选。
    """
    if not value:
        return pd.Series([True] * len(series), index=series.index)

    target = _normalize_text(value)

    return series.astype(str).map(
        lambda x: target in _normalize_text(x) or _normalize_text(x) in target
    )

def _exact_filter(series: pd.Series, value: Optional[str]) -> pd.Series:
    """
    对 pandas Series 做精确筛选。

    适合：
    - CN
    - 盒型/子分类
    - 状态
    - 成员ID

    为什么需要？
    因为像“B盒”这种短字段，如果用包含匹配，可能误匹配到“小卡套装B”等不应该匹配的内容。
    """
    if not value:
        return pd.Series([True] * len(series), index=series.index)

    target = _normalize_text(value)

    return series.astype(str).map(
        lambda x: _normalize_text(x) == target
    )

def query_position_lookup(
    question: str,
    raw_dir: str | Path = "./data/raw",
) -> Dict[str, Any]:
    """
    结构化排位查询。

    适合问题：
    - 探幽在蕾塞篇场面写B盒中买的炸弹排第几？
    - 炸弹在B盒排第几？
    - 某某买的某款排在哪？
    """
    df = load_schedule_details(raw_dir=raw_dir)

    if df.empty:
        return {
            "found": False,
            "answer": "没有找到可用的 04_排表明细 数据。",
            "entities": {},
            "rows": [],
            "sources": [],
        }

    entities = extract_position_entities(question, df)

    filtered = df.copy()

    # 逐步应用筛选条件
    if entities["member_name"] and "CN" in filtered.columns:
        filtered = filtered[_contains_filter(filtered["CN"], entities["member_name"])]

    if entities["series_name"] and "系列" in filtered.columns:
        filtered = filtered[_contains_filter(filtered["系列"], entities["series_name"])]

    if entities["item_name"] and "谷子种类" in filtered.columns:
        filtered = filtered[_contains_filter(filtered["谷子种类"], entities["item_name"])]

    # if entities["box_name"] and "盒型/子分类" in filtered.columns:
    #     filtered = filtered[_contains_filter(filtered["盒型/子分类"], entities["box_name"])]
    if entities["box_name"] and "盒型/子分类" in filtered.columns:
        filtered = filtered[_exact_filter(filtered["盒型/子分类"], entities["box_name"])]

    if entities["variant_name"] and "角色/款式" in filtered.columns:
        filtered = filtered[_contains_filter(filtered["角色/款式"], entities["variant_name"])]

    rows = []

    wanted_columns = [
        "记录ID",
        "系列",
        "谷子种类",
        "大类",
        "盒型/子分类",
        "角色/款式",
        "排位",
        "成员ID",
        "CN",
        "状态",
        "来源文件",
        "来源Sheet",
        "来源单元格",
        "备注",
        "知识库文件",
    ]

    for _, row in filtered.iterrows():
        item = {}

        for col in wanted_columns:
            if col in filtered.columns:
                item[col] = _clean_value(row.get(col, ""))

        rows.append(item)

    if not rows:
        missing_hint = []

        if not entities["member_name"]:
            missing_hint.append("成员名")
        if not entities["item_name"]:
            missing_hint.append("谷子种类")
        if not entities["box_name"]:
            missing_hint.append("盒型/子分类")
        if not entities["variant_name"]:
            missing_hint.append("角色/款式")

        hint_text = ""
        if missing_hint:
            hint_text = f"。另外，问题中有些条件未能识别：{', '.join(missing_hint)}"

        return {
            "found": False,
            "answer": f"知识库中没有找到完全匹配的排位记录{hint_text}。",
            "entities": entities,
            "rows": [],
            "sources": [],
        }

    answer = format_position_lookup_answer(question, entities, rows)
    sources = build_table_sources(rows)

    return {
        "found": True,
        "answer": answer,
        "entities": entities,
        "rows": rows,
        "sources": sources,
    }


def format_position_lookup_answer(
    question: str,
    entities: Dict[str, Optional[str]],
    rows: List[Dict[str, str]],
) -> str:
    """
    把结构化查询结果格式化成用户可读答案。
    """
    member_name = entities.get("member_name")
    item_name = entities.get("item_name")
    box_name = entities.get("box_name")
    variant_name = entities.get("variant_name")

    header_parts = []

    if member_name:
        header_parts.append(f"成员：{member_name}")
    if item_name:
        header_parts.append(f"谷子种类：{item_name}")
    if box_name:
        header_parts.append(f"盒型/子分类：{box_name}")
    if variant_name:
        header_parts.append(f"角色/款式：{variant_name}")

    header = "，".join(header_parts) if header_parts else "根据结构化排表"

    lines = [
        f"根据 04_排表明细，找到 {len(rows)} 条匹配记录。",
        "",
        f"查询条件：{header}",
        "",
        "匹配结果：",
    ]

    for i, row in enumerate(rows, start=1):
        series = row.get("系列", "")
        item = row.get("谷子种类", "")
        box = row.get("盒型/子分类", "")
        variant = row.get("角色/款式", "")
        position = row.get("排位", "")
        cn = row.get("CN", "")
        status = row.get("状态", "")

        parts = []

        if series:
            parts.append(series)
        if item:
            parts.append(item)
        if box:
            parts.append(box)
        if variant:
            parts.append(variant)
        if position:
            parts.append(f"第{position}位" if str(position).isdigit() else str(position))
        if cn:
            parts.append(f"成员：{cn}")
        if status:
            parts.append(f"状态：{status}")

        lines.append(f"{i}. " + " / ".join(parts))

    return "\n".join(lines)


def build_table_sources(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    从结构化表格结果生成来源信息。
    """
    sources = []

    for row in rows:
        sources.append(
            {
                "source_type": "structured_table",
                "source_file": row.get("知识库文件") or row.get("来源文件"),
                "source_sheet": row.get("来源Sheet"),
                "source_cell": row.get("来源单元格"),
                "record_id": row.get("记录ID"),
                "series": row.get("系列"),
                "item": row.get("谷子种类"),
                "box": row.get("盒型/子分类"),
                "variant": row.get("角色/款式"),
                "position": row.get("排位"),
                "member": row.get("CN"),
                "status": row.get("状态"),
            }
        )

    return sources

def _filter_valid_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    默认只保留有效记录。

    如果没有“状态”列，就不做过滤。
    如果有“状态”列，优先保留：
    - 有效
    - 已确认
    - 已付款
    - 空字符串

    这里先按你的当前数据使用“有效”。
    后续如果状态体系更复杂，可以在这里集中调整。
    """
    if "状态" not in df.columns:
        return df

    valid_statuses = {"有效", "已确认", "已付款", ""}

    return df[df["状态"].astype(str).map(lambda x: x.strip() in valid_statuses)]

def _group_count_rows(df: pd.DataFrame, group_columns: List[str]) -> List[Dict[str, Any]]:
    """
    按指定列 groupby 统计数量。

    例如：
    group_columns = ["系列", "谷子种类", "盒型/子分类"]
    返回：
    [
      {"系列": "movic系列", "谷子种类": "pld拥", "盒型/子分类": "拥", "数量": 20}
    ]
    """
    existing_columns = [col for col in group_columns if col in df.columns]

    if not existing_columns or df.empty:
        return []

    grouped = (
        df.groupby(existing_columns, dropna=False)
        .size()
        .reset_index(name="数量")
        .sort_values("数量", ascending=False)
    )

    results = []

    for _, row in grouped.iterrows():
        item = {}

        for col in existing_columns:
            item[col] = _clean_value(row.get(col, ""))

        item["数量"] = int(row.get("数量", 0))
        results.append(item)

    return results

def query_member_summary(
    question: str,
    raw_dir: str | Path = "./data/raw",
) -> Dict[str, Any]:
    """
    结构化团员排谷汇总查询。

    适合问题：
    - 逗比南博万排了什么？
    - 探幽买了哪些？
    - 某某一共买了多少？
    - 某某买了几个 B盒？
    - 某某在 movic 系列里排了什么？
    """
    df = load_schedule_details(raw_dir=raw_dir)

    if df.empty:
        return {
            "found": False,
            "answer": "没有找到可用的 04_排表明细 数据。",
            "entities": {},
            "summary": {},
            "rows": [],
            "sources": [],
        }

    entities = extract_member_summary_entities(question, df)

    member_name = entities.get("member_name")

    if not member_name:
        return {
            "found": False,
            "answer": "没有识别到要查询的团员/CN，请补充团员名。",
            "entities": entities,
            "summary": {},
            "rows": [],
            "sources": [],
        }

    filtered = df.copy()

    # 1. 先按成员过滤
    if "CN" in filtered.columns:
        filtered = filtered[_contains_filter(filtered["CN"], member_name)]

    # 2. 默认只统计有效记录
    filtered = _filter_valid_rows(filtered)

    # 3. 如果问题里有额外条件，就继续过滤
    if entities.get("series_name") and "系列" in filtered.columns:
        filtered = filtered[_contains_filter(filtered["系列"], entities["series_name"])]

    if entities.get("item_name") and "谷子种类" in filtered.columns:
        filtered = filtered[_contains_filter(filtered["谷子种类"], entities["item_name"])]

    # if entities.get("box_name") and "盒型/子分类" in filtered.columns:
    #     filtered = filtered[_contains_filter(filtered["盒型/子分类"], entities["box_name"])]
    if entities.get("box_name") and "盒型/子分类" in filtered.columns:
        filtered = filtered[_exact_filter(filtered["盒型/子分类"], entities["box_name"])]

    if entities.get("variant_name") and "角色/款式" in filtered.columns:
        filtered = filtered[_contains_filter(filtered["角色/款式"], entities["variant_name"])]

    if filtered.empty:
        return {
            "found": False,
            "answer": f"知识库中没有找到 {member_name} 的匹配排谷记录。",
            "entities": entities,
            "summary": {},
            "rows": [],
            "sources": [],
        }

    # 4. 生成明细 rows
    wanted_columns = [
        "记录ID",
        "系列",
        "谷子种类",
        "大类",
        "盒型/子分类",
        "角色/款式",
        "排位",
        "成员ID",
        "CN",
        "状态",
        "来源文件",
        "来源Sheet",
        "来源单元格",
        "备注",
        "知识库文件",
    ]

    rows = []

    for _, row in filtered.iterrows():
        item = {}

        for col in wanted_columns:
            if col in filtered.columns:
                item[col] = _clean_value(row.get(col, ""))

        rows.append(item)

    # 5. 生成各种统计
    summary = {
        "total_count": len(filtered),
        "by_series": _group_count_rows(filtered, ["系列"]),
        "by_item": _group_count_rows(filtered, ["系列", "谷子种类"]),
        "by_box": _group_count_rows(filtered, ["系列", "谷子种类", "盒型/子分类"]),
        "by_variant": _group_count_rows(
            filtered,
            ["系列", "谷子种类", "盒型/子分类", "角色/款式"],
        ),
    }

    answer = format_member_summary_answer(
        member_name=member_name,
        entities=entities,
        summary=summary,
        rows=rows,
    )

    sources = build_table_sources(rows)

    return {
        "found": True,
        "answer": answer,
        "entities": entities,
        "summary": summary,
        "rows": rows,
        "sources": sources,
    }


def _format_group_lines(
    groups: List[Dict[str, Any]],
    columns: List[str],
    max_items: int = 20,
) -> List[str]:
    """
    把 groupby 结果格式化成文本行。
    """
    lines = []

    for group in groups[:max_items]:
        parts = []

        for col in columns:
            value = group.get(col)
            if value:
                parts.append(str(value))

        name = " / ".join(parts) if parts else "未分类"
        count = group.get("数量", 0)

        lines.append(f"- {name}：{count} 个")

    if len(groups) > max_items:
        lines.append(f"- ……还有 {len(groups) - max_items} 项未展示")

    return lines


def format_member_summary_answer(
    member_name: str,
    entities: Dict[str, Optional[str]],
    summary: Dict[str, Any],
    rows: List[Dict[str, str]],
) -> str:
    """
    把成员汇总统计结果格式化成用户可读答案。
    """
    total_count = summary.get("total_count", 0)

    lines = [
        f"根据 04_排表明细，找到 {member_name} 的 {total_count} 条有效排谷记录。",
        "",
        "【总体概况】",
        f"- {member_name} 当前共排了 {total_count} 个。",
    ]

    # 如果用户问题里有额外筛选条件，就说明一下
    filter_parts = []

    if entities.get("series_name"):
        filter_parts.append(f"系列：{entities['series_name']}")
    if entities.get("item_name"):
        filter_parts.append(f"谷子种类：{entities['item_name']}")
    if entities.get("box_name"):
        filter_parts.append(f"盒型/子分类：{entities['box_name']}")
    if entities.get("variant_name"):
        filter_parts.append(f"角色/款式：{entities['variant_name']}")

    if filter_parts:
        lines.append(f"- 本次查询条件：{'，'.join(filter_parts)}")

    lines.append("")
    lines.append("【按系列汇总】")
    lines.extend(
        _format_group_lines(
            summary.get("by_series", []),
            ["系列"],
        )
    )

    lines.append("")
    lines.append("【按谷子种类汇总】")
    lines.extend(
        _format_group_lines(
            summary.get("by_item", []),
            ["系列", "谷子种类"],
        )
    )

    lines.append("")
    lines.append("【按盒型/子分类汇总】")
    lines.extend(
        _format_group_lines(
            summary.get("by_box", []),
            ["系列", "谷子种类", "盒型/子分类"],
        )
    )

    lines.append("")
    lines.append("【按角色/款式汇总】")
    lines.extend(
        _format_group_lines(
            summary.get("by_variant", []),
            ["系列", "谷子种类", "盒型/子分类", "角色/款式"],
        )
    )

    lines.append("")
    lines.append("【明细】")

    for i, row in enumerate(rows[:50], start=1):
        series = row.get("系列", "")
        item = row.get("谷子种类", "")
        box = row.get("盒型/子分类", "")
        variant = row.get("角色/款式", "")
        position = row.get("排位", "")
        status = row.get("状态", "")

        parts = []

        if series:
            parts.append(series)
        if item:
            parts.append(item)
        if box:
            parts.append(box)
        if variant:
            parts.append(variant)
        if position:
            parts.append(f"第{position}位" if str(position).isdigit() else str(position))
        if status:
            parts.append(f"状态：{status}")

        lines.append(f"{i}. " + " / ".join(parts))

    if len(rows) > 50:
        lines.append(f"... 还有 {len(rows) - 50} 条明细未展示。")

    return "\n".join(lines)