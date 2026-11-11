import argparse
import csv
import json
import logging
import math
import os
import re
import sqlite3
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

from dotenv import dotenv_values
from PIL import Image


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))
DATASET = ROOT / "dataset"
RESULTS = ROOT / "results"
ENV_FILE = PROJECT_ROOT / "config" / ".env"
MODEL = "gemini-3.5-flash-lite"
RETRY_DELAY_SECONDS = 60
CSV_FIELDS = [
    "image",
    "category",
    "ocr_status",
    "ocr_latency_seconds",
    "model_status",
    "model_latency_seconds",
    "qa_exact",
    "qa_total",
    "summary_token_f1",
    "character_error_rate",
    "word_error_rate",
    "ocr_text",
    "model_response",
    "error",
]


def load_api_key():
    if not ENV_FILE.is_file():
        return "", f"Required configuration file is missing: {ENV_FILE.relative_to(PROJECT_ROOT)}"
    values = dotenv_values(ENV_FILE)
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "API_KEY"):
        value = values.get(name)
        if value and str(value).strip():
            return str(value).strip(), ""
    return "", "No GEMINI_API_KEY, GOOGLE_API_KEY, or API_KEY value was found in config/.env."


def get_app_config_without_secrets():
    database_path = Path(os.environ.get("NEXA_DB_PATH", Path.home() / ".nexa_ai" / "nexa_history.db"))
    if not database_path.is_file():
        return {"provider": "unknown", "stored_model": "unknown"}
    try:
        uri = f"file:{database_path.as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            settings = dict(connection.execute(
                "SELECT key, value FROM settings WHERE key IN ('api_provider', 'model_name')"
            ))
        return {
            "provider": settings.get("api_provider", "gemini"),
            "stored_model": settings.get("model_name", ""),
        }
    except (sqlite3.Error, OSError):
        return {"provider": "unknown", "stored_model": "unknown"}


def preprocess(image):
    import ocr_engine

    return ocr_engine.preprocess_image(image)


def extract_ocr_text(image_path):
    import ocr_engine

    with Image.open(image_path) as image:
        processed = preprocess(image)
    reader = ocr_engine.get_ocr_reader()
    results = reader.readtext(processed, canvas_size=1024, batch_size=32)
    results.sort(key=lambda result: (result[0][0][1], result[0][0][0]))
    visible_text = " ".join(text for _, text, confidence in results if confidence > 0.15)
    return ocr_engine.clean_extracted_text(visible_text)


def normalize_answer(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def token_f1(reference, prediction):
    reference_tokens = re.findall(r"\w+", reference.lower())
    prediction_tokens = re.findall(r"\w+", prediction.lower())
    if not reference_tokens or not prediction_tokens:
        return 0.0
    overlap = sum((Counter(reference_tokens) & Counter(prediction_tokens)).values())
    if not overlap:
        return 0.0
    precision = overlap / len(prediction_tokens)
    recall = overlap / len(reference_tokens)
    return 2 * precision * recall / (precision + recall)


def edit_distance(left, right):
    if len(left) > len(right):
        left, right = right, left
    previous = list(range(len(left) + 1))
    for row_index, right_value in enumerate(right, 1):
        current = [row_index]
        for column_index, left_value in enumerate(left, 1):
            current.append(min(
                current[-1] + 1,
                previous[column_index] + 1,
                previous[column_index - 1] + (left_value != right_value),
            ))
        previous = current
    return previous[-1]


def normalized_text(text):
    return re.sub(r"\s+", " ", text.lower()).strip()


def word_tokens(text):
    return re.findall(r"\w+|[^\w\s]", text.lower())


def parse_model_response(response):
    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        parsed = json.loads(response[start:end])
        answers = parsed.get("answers", [])
        return {
            "answers": [str(answer) for answer in answers[:2]],
            "summary": str(parsed.get("summary", "")),
        }
    except (ValueError, json.JSONDecodeError, AttributeError):
        return {"answers": [], "summary": ""}


def redact(value, api_key):
    text = str(value)
    return text.replace(api_key, "[REDACTED]") if api_key else text


def query_app_gemini(api_key, image_path, ocr_text, questions):
    import ai_client
    import plugin_manager

    prompt = (
        "Analyze the attached screenshot. Use its visible layout as well as this OCR text:\n"
        f"{ocr_text}\n\n"
        "Answer the questions and provide a concise reference-style summary. "
        "Return only valid JSON with keys answers (an array with one short answer per question) "
        "and summary (2-3 sentences). Questions:\n"
        + "\n".join(f"{index}. {item['q']}" for index, item in enumerate(questions, 1))
    )
    original_dispatch = plugin_manager.execute_tool_call
    plugin_manager.execute_tool_call = lambda name, arguments: {
        "error": "Local tool execution is disabled for screenshot evaluation."
    }
    try:
        return ai_client.query_gemini(
            api_key,
            MODEL,
            [{"role": "user", "text": prompt, "screenshot_path": str(image_path)}],
            retry_fallback=False,
        )
    finally:
        plugin_manager.execute_tool_call = original_dispatch


def read_cache(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_cache(path, cache):
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_dataset():
    images = sorted(DATASET.glob("*.png"))
    if not images:
        raise FileNotFoundError(f"No dataset PNGs found in {DATASET}; run generate_dataset.py first.")
    return [(image, json.loads(image.with_suffix(".json").read_text(encoding="utf-8"))) for image in images]


def measure_row(image_path, metadata, api_key, missing_key_message, cache):
    import ocr_engine

    image_name = image_path.name
    previous = cache.get(image_name, {})
    record = dict(previous)
    record.update({"image": image_name, "category": metadata["category"], "model": MODEL})

    if record.get("ocr_status") != "complete":
        start = time.perf_counter()
        try:
            record["ocr_text"] = extract_ocr_text(image_path)
            record["ocr_status"] = "complete"
            record["ocr_error"] = ""
        except Exception as error:
            record["ocr_text"] = ""
            record["ocr_status"] = "error"
            record["ocr_error"] = str(error)
        record["ocr_latency_seconds"] = time.perf_counter() - start

    if record.get("model_status") != "complete":
        if not api_key:
            record.update({
                "model_status": "blocked_missing_api_key",
                "model_response": "",
                "model_latency_seconds": None,
                "error": missing_key_message,
            })
        else:
            start = time.perf_counter()
            try:
                response = query_app_gemini(api_key, image_path, record.get("ocr_text", ""), metadata["questions"])
                if "429" in response and ("Rate Limit" in response or "API Error" in response):
                    time.sleep(RETRY_DELAY_SECONDS)
                    response = query_app_gemini(api_key, image_path, record.get("ocr_text", ""), metadata["questions"])
                response = redact(response, api_key)
                record["model_response"] = response
                record["model_status"] = "error" if response.startswith(("Error:", "**Gemini API Error", "**Network Error")) else "complete"
                record["error"] = response if record["model_status"] == "error" else ""
            except Exception as error:
                record["model_response"] = ""
                record["model_status"] = "error"
                record["error"] = redact(error, api_key)
            record["model_latency_seconds"] = time.perf_counter() - start

    parsed = parse_model_response(record.get("model_response", ""))
    exact = 0
    if record.get("model_status") == "complete":
        for expected, actual in zip(metadata["questions"], parsed["answers"]):
            exact += normalize_answer(expected["a"]) == normalize_answer(actual)
    record["parsed_answers"] = parsed["answers"]
    record["parsed_summary"] = parsed["summary"]
    record["qa_exact"] = int(exact)
    record["qa_total"] = len(metadata["questions"]) if record.get("model_status") == "complete" else 0
    record["summary_token_f1"] = token_f1(metadata["summary"], parsed["summary"]) if parsed["summary"] else None
    record["reference_questions"] = metadata["questions"]
    record["reference_summary"] = metadata["summary"]
    reference_text = normalized_text((DATASET / image_name).with_suffix(".txt").read_text(encoding="utf-8"))
    actual_text = normalized_text(record.get("ocr_text", ""))
    reference_words = word_tokens(reference_text)
    actual_words = word_tokens(actual_text)
    record["character_error_rate"] = edit_distance(reference_text, actual_text) / max(1, len(reference_text))
    record["word_error_rate"] = edit_distance(reference_words, actual_words) / max(1, len(reference_words))
    cache[image_name] = record
    return record


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def category_metrics(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row["category"], []).append(row)
    groups["Overall"] = rows
    table = [
        "Category | Images | OCR exact | Mean CER | Mean WER | QA exact | QA total | Exact match | Mean summary token-F1",
        "--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---:",
    ]
    for category, group in groups.items():
        cer_values = [float(row["character_error_rate"]) for row in group if row.get("character_error_rate") is not None]
        wer_values = [float(row["word_error_rate"]) for row in group if row.get("word_error_rate") is not None]
        ocr_exact = sum(value == 0 for value in cer_values)
        completed = [row for row in group if row.get("model_status") == "complete"]
        exact = sum(int(row.get("qa_exact", 0)) for row in completed)
        total = sum(int(row.get("qa_total", 0)) for row in completed)
        scores = [row["summary_token_f1"] for row in completed if row.get("summary_token_f1") is not None]
        rate = f"{100 * exact / total:.2f}%" if total else "N/A"
        mean_score = f"{statistics.mean(scores):.4f}" if scores else "N/A"
        mean_cer = f"{statistics.mean(cer_values):.4f}" if cer_values else "N/A"
        mean_wer = f"{statistics.mean(wer_values):.4f}" if wer_values else "N/A"
        table.append(f"{category} | {len(group)} | {ocr_exact} | {mean_cer} | {mean_wer} | {exact} | {total} | {rate} | {mean_score}")
    return "\n".join(table)


def percentile(values, percentile_value):
    ordered = sorted(values)
    if not ordered:
        return None
    return ordered[max(0, math.ceil(percentile_value * len(ordered)) - 1)]


def write_latency_summary(path, rows, blocked_reason):
    ocr_values = [float(row["ocr_latency_seconds"]) for row in rows if row.get("ocr_latency_seconds") is not None]
    model_values = [float(row["model_latency_seconds"]) for row in rows if row.get("model_latency_seconds") is not None]
    lines = [
        "Nexa AI evaluation latency",
        f"Model: {MODEL}",
        "Times are wall-clock measurements from this run or reused completed cache entries.",
        "",
        "Stage | N | Mean seconds | Median seconds | P95 seconds",
        "--- | ---: | ---: | ---: | ---:",
    ]
    for name, values in (("App preprocessing + EasyOCR", ocr_values), ("Gemini request", model_values)):
        if values:
            lines.append(f"{name} | {len(values)} | {statistics.mean(values):.3f} | {statistics.median(values):.3f} | {percentile(values, 0.95):.3f}")
        else:
            lines.append(f"{name} | 0 | N/A | N/A | N/A")
    if blocked_reason:
        lines.extend(["", f"Gemini latency unavailable: {blocked_reason}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run Nexa screenshot OCR and Gemini evaluation.")
    parser.add_argument("--latency", action="store_true", help="Write latency_summary.txt using measured/cached stage timings.")
    args = parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    logging.disable(logging.CRITICAL)
    api_key, missing_key_message = load_api_key()
    app_config = get_app_config_without_secrets()
    (RESULTS / "environment.json").write_text(json.dumps({
        "python_version": sys.version.split()[0],
        "configured_model": MODEL,
        "configured_model_source": "ai_client.get_ai_client_config Gemini fallback",
        "app_provider_in_local_settings": app_config["provider"],
        "app_model_in_local_settings": app_config["stored_model"],
        "required_env_file_exists": ENV_FILE.is_file(),
        "api_key_value_loaded": bool(api_key),
    }, indent=2) + "\n", encoding="utf-8")

    cache_path = RESULTS / "cache.json"
    cache = read_cache(cache_path)
    rows = []
    jsonl_path = RESULTS / "raw_results.jsonl"
    jsonl_path.write_text("", encoding="utf-8")
    for image_path, metadata in load_dataset():
        row = measure_row(image_path, metadata, api_key, missing_key_message, cache)
        rows.append(row)
        write_cache(cache_path, cache)
        with jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    write_csv(RESULTS / "evaluation.csv", rows)
    completed = sum(row.get("model_status") == "complete" for row in rows)
    failures = sum(row.get("model_status") == "error" or row.get("ocr_status") == "error" for row in rows)
    lines = [
        "Nexa AI screenshot evaluation",
        f"Configured Gemini model: {MODEL}",
        f"Images in dataset: {len(rows)}",
        f"Images with completed Gemini responses: {completed}",
        f"Rows with OCR/model errors: {failures}",
        "",
        category_metrics(rows),
        "",
        "Raw outputs: raw_results.jsonl; resumable cache: cache.json; row data: evaluation.csv.",
    ]
    if not api_key:
        lines.extend([
            "",
            "STATUS: BLOCKED for Gemini evaluation.",
            missing_key_message,
            f"The app's local settings currently identify provider={app_config['provider']!r} and model={app_config['stored_model']!r}; the mandated config/.env key was not available, so no cloud request was made.",
            "EasyOCR was still run locally on the dataset and its text and measured timings were saved.",
        ])
    elif completed < len(rows):
        lines.extend(["", "STATUS: PARTIAL; inspect per-image errors in evaluation.csv and raw_results.jsonl."])
    else:
        lines.extend(["", "STATUS: COMPLETE."])
    (RESULTS / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_latency_summary(RESULTS / "latency_summary.txt", rows, missing_key_message if not api_key else "")
    print((RESULTS / "summary.txt").read_text(encoding="utf-8"))
    if args.latency:
        print((RESULTS / "latency_summary.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()