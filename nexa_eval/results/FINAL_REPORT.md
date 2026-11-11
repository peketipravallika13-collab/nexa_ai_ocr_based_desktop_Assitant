# Nexa AI Evaluation Report

## Experimental Scope

This run provides measured EasyOCR results on a locally generated, synthetic screenshot dataset. It does **not** provide Gemini vision accuracy, model latency, or live tool-selection results: `config/.env` is absent, and the app's local settings select Groq (`openai/gpt-oss-20b`). No cloud requests or tool calls were made. Do not present the unavailable model metrics as experimental findings.

Evaluation scripts used Python 3.11.9. The dataset source strings and image layouts are deterministic and stored in [generate_dataset.py](../generate_dataset.py); all captured OCR text, metadata, per-image measurements, and timing outputs are retained under `results/`.

## Hardware And Runtime

| Item | Observed value |
| --- | --- |
| CPU | AMD Ryzen 5 7520U with Radeon Graphics |
| RAM | 15.28 GiB visible memory |
| GPU | AMD Radeon(TM) Graphics, driver 32.0.21030.31; EasyOCR selected CPU (`torch.cuda.is_available() == False`) |
| OS | Microsoft Windows 11 Home Single Language, version 10.0.26300 |
| Python used for evaluation | 3.11.9 |
| Network adapter | Wi-Fi, MediaTek Wi-Fi 6E MT7902 Wireless LAN Card, Native 802.11, 58.5 Mbps link speed |

These are local system/runtime observations captured during this run. The active Wi-Fi adapter was up; no independent internet throughput test was performed.

## Dataset

Forty synthetic 1920×1080 screenshots were rendered from known source strings; each has a matching exact-visible-text `.txt` ground truth and a `.json` file with two short-answer questions and a reference summary. Every category includes a layout/visual question. Preview: [dataset_preview.png](../dataset_preview.png).

| Category | Images |
| --- | ---: |
| IDE code | 8 |
| Terminal error output | 8 |
| Webpage | 8 |
| PDF/document page | 8 |
| Spreadsheet | 8 |
| Total | 40 |

## OCR Results

The following table is copied from [summary.txt](summary.txt). CER/WER use case-folded, whitespace-normalized text and edit distance; exact OCR means CER is zero.

Category | Images | OCR exact | Mean CER | Mean WER | QA exact | QA total | Exact match | Mean summary token-F1
--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---:
PDF/document page | 8 | 0 | 0.0990 | 0.2029 | 0 | 0 | N/A | N/A
IDE code | 8 | 0 | 0.3087 | 0.4110 | 0 | 0 | N/A | N/A
Spreadsheet | 8 | 0 | 0.2993 | 0.4394 | 0 | 0 | N/A | N/A
Terminal error output | 8 | 0 | 0.2651 | 0.4253 | 0 | 0 | N/A | N/A
Webpage | 8 | 0 | 0.3331 | 0.3971 | 0 | 0 | N/A | N/A
Overall | 40 | 0 | 0.2611 | 0.3751 | 0 | 0 | N/A | N/A

QA and summary scores are `N/A` because no model responses were generated. All 40 EasyOCR runs completed without an OCR exception; none exactly matched the full visible-text ground truth.

## Latency

The table below is copied from [latency_summary.txt](latency_summary.txt).

Stage | N | Mean seconds | Median seconds | P95 seconds
--- | ---: | ---: | ---: | ---:
App preprocessing + EasyOCR | 40 | 6.105 | 5.886 | 7.607
Gemini request | 0 | N/A | N/A | N/A

## Tool Calling

The authored test file contains 12 prompts: eight for the real `calculator` plugin and four draft-only cases for `email_manager`. All 12 rows in [tool_results.csv](tool_results.csv) are `blocked_missing_api_key`; selected tool, execution, and latency are blank. No email was opened or sent.

The [tool_summary.txt](tool_summary.txt) confusion-table result is copied exactly:

> No tool-selection observations; the API key is unavailable.

Tool-selection accuracy: N/A (no API calls). Execution success rate: N/A (no tools executed).

## Robustness

The case outcomes below are summarized from [robustness.csv](robustness.csv). Model status and tool-trigger status are separate because local ingestion may succeed while the cloud step is blocked.

| Input | Ingestion/outcome | Model status | Tool trigger |
| --- | --- | --- | --- |
| TXT renamed to PDF | Handled gracefully; PDF parser reported no extractable text | Blocked: missing API key | Unknown |
| Zero-byte image | **Crash:** app router accepts the path, but the app's EasyOCR preprocessing raises `UnidentifiedImageError` | Not sent after OCR crash | Not tested |
| Fully black screenshot | OCR completed; no text detected | Blocked: missing API key | Unknown |
| Blurred low-resolution screenshot | OCR completed; no text detected | Blocked: missing API key | Unknown |
| Screenshot with 8px text | OCR completed; no text detected | Blocked: missing API key | Unknown |
| Empty prompt | Handled gracefully; app validation returns without sending | Not sent by app validation | False |
| Nonsense prompt | Model check blocked before request | Blocked: missing API key | Unknown |
| Prompt-injection screenshot | OCR extracted the injected sentence | Blocked: missing API key | Unknown |
| 201-page PDF | Parsed; app returned pages 1-30 and reported 201 total pages | Blocked: missing API key | Unknown |
| `.exe` content renamed to `.xyz` | Read through generic text/code fallback | Blocked: missing API key | Unknown |

Three evidence composites are saved: [blurred_low_resolution_result.png](robustness_screenshots/blurred_low_resolution_result.png), [small_8px_text_result.png](robustness_screenshots/small_8px_text_result.png), and [prompt_injection_screenshot_result.png](robustness_screenshots/prompt_injection_screenshot_result.png).

## Security Facts

- API keys are stored in the app's SQLite `settings.value` text column; the settings UI masks the field, but code shows no encryption. The app reads SQLite settings, not `config/.env`. See [security_facts.md](security_facts.md) for line-level evidence.
- Screen captures are stored under the user's `.nexa_ai/screenshots` directory and are not deleted by the capture flow. OCR text plus the screenshot image can be sent to the configured model.
- File contents are parsed locally into text; image attachments are encoded as image data. Audio transcription uses Google's speech-recognition service; URL attachments are fetched and extracted text is passed to the LLM.
- The capture dialog approves capture, not review of the captured content before upload. After OCR, the app immediately requests an AI response.
- Gemini function calls are executed without a user confirmation step. The email plugin has a draft action and a direct SMTP send action.
- No explicit prompt-injection defense was found in the inspected system prompt or tool-dispatch path. The injected-image tool result is unknown because the model was not called.

## Failures And Limitations

- **Gemini evaluation blocked:** `config/.env` does not exist in this workspace. The evaluation did not search for or print keys elsewhere. The app's local stored provider/model are Groq and `openai/gpt-oss-20b`, not Gemini.
- **Tool-selection evaluation blocked:** all 12 prompts were saved as blocked; there is no accuracy, confusion count, execution rate, or latency result to report.
- **Prompt-injection safety outcome unknown:** the screenshot OCR text was captured, but no model request or tool-selection decision occurred.
- **OCR mismatch:** no screenshot had an exact full-text OCR match. The blurred, low-resolution, and 8px samples yielded no recognized text.
- **Malformed file behavior:** a text file renamed `.pdf` was handled with a no-extractable-text notice; a zero-byte PNG caused the app's OCR preprocessing to raise `UnidentifiedImageError`; `.xyz` was accepted by the generic text/code fallback rather than rejected as unsupported.
- **Large PDF behavior:** the 201-page fixture was accepted, but the app intentionally extracts only the first 30 pages.
- **Interpreter setup:** the Python 3.12.0a3 interpreter exited with native access violation `3221225477` during dataset rendering. Evaluation was performed with Python 3.11.9. The workspace's selected Python 3.15.1 environment did not contain the OCR dependencies used by the app.

Raw auditable outputs: [evaluation.csv](evaluation.csv), [raw_results.jsonl](raw_results.jsonl), [cache.json](cache.json), [environment.json](environment.json), [tool_results.csv](tool_results.csv), [tool_raw_results.jsonl](tool_raw_results.jsonl), [robustness.csv](robustness.csv), [robustness_raw.jsonl](robustness_raw.jsonl), and [robustness.log](robustness.log).