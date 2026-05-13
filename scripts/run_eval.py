import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.qa_chain_qdrant import answer_question_with_qdrant


def load_eval_cases(file_path: str | Path) -> List[Dict[str, Any]]:
    """
    读取 JSONL 格式的评测用例。

    JSONL：一行一个 JSON。
    好处是后续追加测试用例很方便。
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"评测文件不存在：{path}")

    cases = []

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"第 {line_no} 行不是合法 JSON：{line}") from exc

            if "question" not in case:
                raise ValueError(f"第 {line_no} 行缺少 question 字段")

            cases.append(case)

    return cases


def check_case(case: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查单条测试是否通过。

    当前 v1 检查：
    1. intent 是否符合 expected_intent
    2. answer 是否包含 must_contain 里的关键词
    3. 如果 source_required=true，则 sources 不能为空
    """
    question = case.get("question", "")
    expected_intent = case.get("expected_intent")
    must_contain = case.get("must_contain", [])
    source_required = bool(case.get("source_required", False))

    answer = result.get("answer", "") or ""
    actual_intent = result.get("intent")
    sources = result.get("sources", []) or []

    errors = []

    if expected_intent and actual_intent != expected_intent:
        errors.append(
            f"intent 不匹配：expected={expected_intent}, actual={actual_intent}"
        )

    for keyword in must_contain:
        if keyword not in answer:
            errors.append(f"答案缺少关键词：{keyword}")

    if source_required and not sources:
        errors.append("要求有来源，但 sources 为空")

    passed = len(errors) == 0

    return {
        "passed": passed,
        "question": question,
        "expected_intent": expected_intent,
        "actual_intent": actual_intent,
        "errors": errors,
        "answer": answer,
        "sources_count": len(sources),
        "route_source": result.get("route_source"),
        "route_confidence": result.get("route_confidence"),
    }


def print_case_result(index: int, total: int, report: Dict[str, Any]) -> None:
    """
    打印单条测试结果。
    """
    status = "PASS" if report["passed"] else "FAIL"

    print("=" * 100)
    print(f"[{index}/{total}] {status}")
    print(f"问题：{report['question']}")
    print(f"期望 intent：{report.get('expected_intent')}")
    print(f"实际 intent：{report.get('actual_intent')}")
    print(f"route_source：{report.get('route_source')}")
    print(f"route_confidence：{report.get('route_confidence')}")
    print(f"sources_count：{report.get('sources_count')}")

    if report["errors"]:
        print("错误：")
        for error in report["errors"]:
            print(f"- {error}")

    print("答案预览：")
    preview = report["answer"][:500]
    print(preview)
    if len(report["answer"]) > 500:
        print("...")


def main():
    parser = argparse.ArgumentParser(description="运行谷团 RAG Eval 测试集")

    parser.add_argument(
        "--file",
        default="data/eval/questions.jsonl",
        help="评测文件路径，默认 data/eval/questions.jsonl",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=12,
        help="RAG 检索 top_k，默认 12",
    )

    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="遇到第一条失败就停止",
    )

    parser.add_argument(
        "--output",
        default="data/eval/latest_report.json",
        help="保存完整评测报告的 JSON 文件路径",
    )

    args = parser.parse_args()

    cases = load_eval_cases(args.file)

    print(f"读取到 {len(cases)} 条评测用例")
    print(f"评测文件：{args.file}")

    reports = []
    passed_count = 0

    for index, case in enumerate(cases, start=1):
        question = case["question"]

        try:
            result = answer_question_with_qdrant(
                question=question,
                top_k=args.top_k,
            )
        except Exception as exc:
            report = {
                "passed": False,
                "question": question,
                "expected_intent": case.get("expected_intent"),
                "actual_intent": None,
                "errors": [f"运行异常：{exc}"],
                "answer": "",
                "sources_count": 0,
                "route_source": None,
                "route_confidence": None,
            }
        else:
            report = check_case(case, result)

        reports.append(report)

        if report["passed"]:
            passed_count += 1

        print_case_result(index, len(cases), report)

        if args.fail_fast and not report["passed"]:
            break

    total = len(reports)
    failed_count = total - passed_count

    print("=" * 100)
    print("评测完成")
    print(f"总计：{total}")
    print(f"通过：{passed_count}")
    print(f"失败：{failed_count}")
    if total:
        print(f"通过率：{passed_count / total:.2%}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    full_report = {
        "total": total,
        "passed": passed_count,
        "failed": failed_count,
        "pass_rate": passed_count / total if total else 0,
        "reports": reports,
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(full_report, f, ensure_ascii=False, indent=2)

    print(f"完整报告已保存：{output_path}")


if __name__ == "__main__":
    main()