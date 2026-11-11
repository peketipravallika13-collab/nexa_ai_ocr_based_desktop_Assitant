import argparse
import csv
import importlib.util
import json
import sys
import time
import webbrowser
from collections import Counter
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
TESTS = ROOT / "tool_calling_tests.csv"
sys.path.insert(0, str(PROJECT_ROOT))

runner_spec = importlib.util.spec_from_file_location("nexa_eval_runner", ROOT / "nexa_eval.py")
runner = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(runner)
MODEL = runner.MODEL
load_api_key = runner.load_api_key
redact = runner.redact


def load_tests():
    with TESTS.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def confusion_table(rows):
    expected_tools = sorted({row["expected_tool"] for row in rows})
    actual_tools = sorted({row.get("selected_tool") or "none" for row in rows})
    header = "Expected \\ Actual | " + " | ".join(actual_tools)
    lines = [header, "--- | " + " | ".join("---:" for _ in actual_tools)]
    for expected in expected_tools:
        values = [sum(row["expected_tool"] == expected and (row.get("selected_tool") or "none") == actual for row in rows) for actual in actual_tools]
        lines.append(expected + " | " + " | ".join(str(value) for value in values))
    if not rows:
        return "No tool-selection observations; the API key is unavailable."
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Evaluate Nexa's Gemini plugin dispatch on a dry-run test set.")
    parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    tests = load_tests()
    api_key, missing_message = load_api_key()
    if not api_key:
        rows = [{
            "test_id": test["test_id"],
            "expected_tool": test["expected_tool"],
            "selected_tool": "",
            "selection_correct": "",
            "executed_without_error": "",
            "latency_seconds": "",
            "status": "blocked_missing_api_key",
            "error": missing_message,
        } for test in tests]
    else:
        import ai_client
        import plugin_manager

        rows = []
        for test in tests:
            prompt = test["prompt"]
            calls = []
            original_dispatch = plugin_manager.execute_tool_call

            def guarded_dispatch(name, arguments):
                started = time.perf_counter()
                if not calls:
                    calls.append({"name": name, "execution": "blocked", "latency_seconds": None})
                call = calls[-1] if calls[-1]["name"] == name and calls[-1]["execution"] == "pending" else calls[-1]
                safe_arguments = dict(arguments)
                if name not in {"calculator", "calculate_expression", "email_manager"}:
                    call.update({"execution": "blocked", "error": "Side-effecting tool blocked by evaluation safety policy."})
                    return {"error": call["error"]}
                if name == "email_manager":
                    safe_arguments["action"] = "draft"
                    with patch.object(webbrowser, "open", return_value=True):
                        result = original_dispatch(name, safe_arguments)
                else:
                    result = original_dispatch(name, safe_arguments)
                call["execution"] = "error" if isinstance(result, dict) and result.get("error") else "success"
                call["latency_seconds"] = time.perf_counter() - started
                return result

            def record_dispatch(name, arguments):
                calls.append({"name": name, "execution": "pending", "latency_seconds": None})
                return guarded_dispatch(name, arguments)

            plugin_manager.execute_tool_call = record_dispatch
            start = time.perf_counter()
            try:
                response = ai_client.query_gemini(
                    api_key,
                    MODEL,
                    [{"role": "user", "text": prompt}],
                    retry_fallback=False,
                )
                error = response if str(response).startswith(("Error:", "**Gemini API Error", "**Network Error")) else ""
            except Exception as exc:
                response = ""
                error = redact(exc, api_key)
            finally:
                plugin_manager.execute_tool_call = original_dispatch
            selected = calls[0]["name"] if calls else ""
            row = {
                "test_id": test["test_id"],
                "expected_tool": test["expected_tool"],
                "selected_tool": selected,
                "selection_correct": str(selected == test["expected_tool"]).lower() if selected else "false",
                "executed_without_error": str(bool(calls) and all(call["execution"] == "success" for call in calls)).lower(),
                "latency_seconds": f"{time.perf_counter() - start:.6f}",
                "status": "complete" if not error else "error",
                "error": redact(error, api_key),
                "tool_response": redact(response, api_key),
                "tool_calls": calls,
            }
            rows.append(row)

    csv_path = RESULTS / "tool_results.csv"
    fields = ["test_id", "expected_tool", "selected_tool", "selection_correct", "executed_without_error", "latency_seconds", "status", "error"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
    with (RESULTS / "tool_raw_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    observed = [row for row in rows if row.get("selection_correct") in ("true", "false")]
    executions = [row for row in rows if row.get("executed_without_error") in ("true", "false")]
    accuracy = f"{100 * sum(row['selection_correct'] == 'true' for row in observed) / len(observed):.2f}%" if observed else "N/A (no API calls)"
    success = f"{100 * sum(row['executed_without_error'] == 'true' for row in executions) / len(executions):.2f}%" if executions else "N/A (no tools executed)"
    table = confusion_table([row for row in rows if row.get("selection_correct") in ("true", "false")])
    report_lines = [
        f"Model: {MODEL}",
        f"Test prompts: {len(tests)}",
        f"Tool-selection accuracy: {accuracy}",
        f"Execution success rate: {success}",
        "",
        "Confusion table (expected tool by selected tool):",
        table,
    ]
    if not api_key:
        report_lines.extend(["", f"Evaluation blocked: {missing_message}", "No prompts were sent, no tools were selected, and no functions were executed."])
    report = "\n".join(report_lines) + "\n"
    (RESULTS / "tool_summary.txt").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()