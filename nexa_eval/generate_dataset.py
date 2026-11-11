import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "dataset"
PREVIEW = ROOT / "dataset_preview.png"
WIDTH, HEIGHT = 1920, 1080
FONT_DIR = Path("C:/Windows/Fonts")

CATEGORIES = {
    "ide_code": "IDE code",
    "terminal_error": "Terminal error output",
    "webpage": "Webpage",
    "document": "PDF/document page",
    "spreadsheet": "Spreadsheet",
}

IDE_SAMPLES = [
    ("cache_store.py", ["from dataclasses import dataclass", "from typing import Optional", "", "@dataclass", "class CacheEntry:", "    key: str", "    value: str", "    expires_at: int", "", "def is_fresh(entry: CacheEntry, now: int) -> bool:", "    return now < entry.expires_at", "", "def get_value(entry: Optional[CacheEntry]) -> str:", "    if entry is None:", "        return \"missing\"", "    return entry.value"]),
    ("batch_job.py", ["import logging", "from pathlib import Path", "", "logger = logging.getLogger(__name__)", "", "def count_records(folder: Path) -> int:", "    total = 0", "    for path in folder.glob(\"*.json\"):", "        total += 1", "    logger.info(\"records=%s\", total)", "    return total", "", "if __name__ == \"__main__\":", "    print(count_records(Path(\"data\")))"]),
    ("retry_policy.ts", ["type RetryOptions = {", "  attempts: number;", "  delayMs: number;", "};", "", "export function nextDelay(options: RetryOptions, retry: number): number {", "  const capped = Math.min(retry, options.attempts);", "  return options.delayMs * 2 ** capped;", "}", "", "export function canRetry(retry: number, limit: number): boolean {", "  return retry < limit;", "}"]),
    ("invoice_total.py", ["from decimal import Decimal", "", "def invoice_total(lines: list[tuple[int, Decimal]]) -> Decimal:", "    subtotal = Decimal(\"0.00\")", "    for quantity, unit_price in lines:", "        subtotal += quantity * unit_price", "    tax = subtotal * Decimal(\"0.08\")", "    return (subtotal + tax).quantize(Decimal(\"0.01\"))", "", "items = [(2, Decimal(\"14.50\")), (1, Decimal(\"8.00\"))]", "print(invoice_total(items))"]),
    ("queue_worker.js", ["const queue = [];", "", "export function enqueue(task) {", "  if (!task || !task.id) {", "    throw new Error(\"task id required\");", "  }", "  queue.push(task);", "  return queue.length;", "}", "", "export function takeNext() {", "  return queue.shift() ?? null;", "}"]),
    ("schema.sql", ["CREATE TABLE shipments (", "    shipment_id INTEGER PRIMARY KEY,", "    order_id INTEGER NOT NULL,", "    status TEXT NOT NULL,", "    updated_at TIMESTAMP NOT NULL", ");", "", "CREATE INDEX idx_shipments_status", "    ON shipments(status);", "", "SELECT status, COUNT(*) AS total", "FROM shipments", "GROUP BY status", "ORDER BY total DESC;"]),
    ("tile_map.rs", ["#[derive(Clone, Copy)]", "struct Point { x: i32, y: i32 }", "", "fn manhattan(a: Point, b: Point) -> i32 {", "    (a.x - b.x).abs() + (a.y - b.y).abs()", "}", "", "fn inside_grid(point: Point, width: i32, height: i32) -> bool {", "    point.x >= 0 && point.y >= 0", "        && point.x < width && point.y < height", "}", "", "fn main() {", "    println!(\"distance={}\", manhattan(Point { x: 2, y: 1 }, Point { x: 7, y: 4 }));", "}"]),
    ("status_view.jsx", ["import React from \"react\";", "", "export function StatusView({ state }) {", "  const label = state.ready ? \"Ready\" : \"Waiting\";", "  return (", "    <section className=\"status\">", "      <h2>{label}</h2>", "      <p>Updated {state.updatedAt}</p>", "    </section>", "  );", "}"]),
]

TERMINAL_SAMPLES = [
    ("build 01", ["$ npm run build", "> atlas-ui@2.4.0 build", "> vite build", "", "vite v5.4.8 building for production...", "✓ 184 modules transformed.", "✗ Build failed in 1.28s", "error: Could not resolve \"./theme.css\"", "  src/views/Dashboard.tsx:4:7", "", "4 | import \"./theme.css\";", "  |        ^^^^^^^^^^^^^", "", "Process exited with code 1"]),
    ("deploy api", ["$ deployctl release --service api", "Reading deployment manifest...", "Target: staging-eu", "Uploading 28 files", "Upload complete", "Waiting for health check", "", "ERROR: health check timed out", "GET /health returned 503", "Last response: database unavailable", "", "Release remains paused", "Use deployctl logs api --tail"]),
    ("pytest run", ["$ pytest tests/test_catalog.py -q", "============================= test session starts =============================", "platform win32 -- Python 3.12.0", "collected 12 items", "", "tests/test_catalog.py .......F....", "", "AssertionError: expected 4, got 3", "tests/test_catalog.py:88", "", "=========================== short test summary info ===========================", "FAILED tests/test_catalog.py::test_active_count", "1 failed, 11 passed", "============================== 1 failed in 0.41s =============================="]),
    ("sync worker", ["$ python worker.py --once", "2026-03-14 08:42:11 INFO  worker started", "2026-03-14 08:42:11 INFO  batch=delta-17", "2026-03-14 08:42:12 INFO  records=240", "2026-03-14 08:42:14 WARN  retry=1 endpoint=/v2/sync", "2026-03-14 08:42:18 ERROR request failed: connection reset", "2026-03-14 08:42:18 INFO  retry scheduled in 8s", "", "worker status: retrying", "exit code: 0"]),
    ("database migration", ["$ python manage.py migrate", "Applying inventory.0012_add_bin_code...", "Traceback (most recent call last):", "  File \"manage.py\", line 18, in <module>", "    run_migrations()", "  File \"db/migrate.py\", line 73, in run_migrations", "    cursor.execute(statement)", "sqlite3.OperationalError: no such table: inventory_bins", "", "Migration stopped; no changes committed", "Command failed with exit status 1"]),
    ("package audit", ["$ npm audit --omit=dev", "# npm audit report", "", "marked 4.1.0", "Severity: moderate", "Inefficient Regular Expression Complexity", "https://github.com/advisories/GHSA-xxx-1234", "fix available via npm audit fix", "", "found 1 moderate severity vulnerability", "audit completed in 2.3s"]),
    ("data export", ["$ python export_report.py --month 2026-02", "Opening read-only connection...", "Source rows: 1842", "Filtering month: 2026-02", "Writing output/report.csv", "", "ERROR: permission denied: output/report.csv", "Check folder access and retry.", "", "Rows exported: 0", "export status: failed"]),
    ("service startup", ["$ .\\service.exe --config staging.yml", "Loading configuration: staging.yml", "Listening on 127.0.0.1:8082", "Starting message consumer...", "", "FATAL: missing environment variable QUEUE_NAME", "Configuration key: queue.name", "File: config/staging.yml", "", "Startup aborted", "service state: stopped", "process exit code: 2"]),
]

WEB_SAMPLES = [
    ("Harbor Weather", "Local forecast", ["Current conditions", "Cloud cover 18%", "Wind from the west", "Sunrise at 06:24"]),
    ("Field Notes", "Observations from the coast", ["Tide window", "High tide 10:42", "Wind speed 12 km/h", "Water temperature 16 C"]),
    ("Northstar Library", "Find your next reference", ["Recently added", "Mapping Quiet Rivers", "The Practical Archive", "Light in Small Rooms"]),
    ("Morrow Coffee", "Small batches, careful roasting", ["This week's roast", "Cedar House Blend", "Origin: Guatemala", "Roast date: 18 May"]),
    ("Civic Garden", "A shared place to grow", ["Open hours", "Tuesday to Saturday", "Seed swap at 14:00", "Plot 12 needs watering"]),
    ("Transit Board", "Service information", ["Route 6", "Next departure 08:17", "Platform 2", "Service running normally"]),
    ("Blue Finch Studio", "Design and print", ["Paper guide", "Recycled matte", "Weight 240 gsm", "Available in three sizes"]),
    ("Orchard Lab", "Research update", ["Trial 08", "Sample count 64", "Median growth 3.2 cm", "Review date 22 June"]),
]

DOCUMENT_SAMPLES = [
    ("Quarterly Service Review", "Operations", ["Response time improved during the final review period.", "The support team closed 312 requests and carried 18 open items into the next cycle.", "Priority for June: reduce repeat incidents in the access queue."]),
    ("River Survey Memo", "Field Research", ["Water samples were collected at four marked points.", "The downstream reading showed elevated sediment after rainfall.", "Next visit: repeat collection after a dry interval."]),
    ("Community Room Plan", "Facilities", ["The east room will remain open during weekday renovations.", "Temporary seating is available beside the north entrance.", "Facilities will review access routes before the first event."]),
    ("Archive Index Update", "Records", ["The index now includes photographs from the 1980 to 1986 series.", "Box 14 contains the signed harbor plans.", "Unlabeled negatives remain in the conservation queue."]),
    ("Project Willow Brief", "Planning", ["The pilot connects three neighborhood collection points.", "Each location reports weight at the end of the day.", "The team will publish a revised schedule on Friday."]),
    ("Studio Safety Note", "Workshop", ["Keep the cutting mat clear before using the rotary tool.", "Store spare blades in the marked cabinet.", "Report damaged guards to the workshop lead."]),
    ("Library Access Report", "Public Services", ["Evening visits increased after the reading room opened later.", "The accessible entrance remains available from Pine Street.", "A second audio station is planned for the west desk."]),
    ("Supplier Review", "Procurement", ["Northline delivered all scheduled paper stock.", "Two cartons arrived with damaged corners and were replaced.", "The next order will use the same recycled finish."]),
]

SPREADSHEET_SAMPLES = [
    ("Regional_Sales", ["Region", "Orders", "Revenue"], [["North", "18", "$4,320"], ["South", "14", "$3,780"], ["West", "11", "$2,940"], ["East", "9", "$2,410"]]),
    ("Lab_Readings", ["Sample", "pH", "Temp C"], [["A-14", "7.2", "18.4"], ["B-09", "6.8", "17.9"], ["C-03", "7.0", "19.1"], ["D-21", "6.5", "18.0"]]),
    ("Support_Queue", ["Team", "Open", "Resolved"], [["Access", "6", "42"], ["Billing", "4", "37"], ["Devices", "9", "31"], ["Accounts", "3", "28"]]),
    ("Garden_Plots", ["Plot", "Crop", "Water L"], [["12", "Tomato", "8"], ["08", "Kale", "5"], ["19", "Beans", "7"], ["04", "Mint", "3"]]),
    ("Transit_Times", ["Route", "On time", "Delay min"], [["6", "92%", "3"], ["11", "88%", "5"], ["4", "96%", "1"], ["15", "84%", "7"]]),
    ("Print_Stock", ["Paper", "Sheets", "Cost"], [["Matte", "1200", "$84"], ["Recycled", "950", "$73"], ["Gloss", "720", "$61"], ["Card", "430", "$58"]]),
    ("Reading_Log", ["Title", "Pages", "Rating"], [["River Atlas", "224", "5"], ["Quiet Rooms", "186", "4"], ["Field Guide", "302", "5"], ["Small Maps", "148", "3"]]),
    ("Orchard_Trial", ["Tree", "Growth cm", "Water ml"], [["O-03", "3.2", "450"], ["O-07", "2.8", "400"], ["O-11", "3.5", "475"], ["O-15", "2.9", "425"]]),
]


def load_font(names, size):
    for name in names:
        candidate = FONT_DIR / name
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


class Screen:
    def __init__(self, background, font_names):
        self.image = Image.new("RGB", (WIDTH, HEIGHT), background)
        self.draw = ImageDraw.Draw(self.image)
        self.font_names = font_names
        self.entries = []

    def text(self, x, y, value, size=22, color="#e7edf5", record=True, font=None):
        selected_font = font or load_font(self.font_names, size)
        self.draw.text((x, y), value, fill=color, font=selected_font)
        if record and value:
            self.entries.append((y, x, value))

    def box(self, xy, fill, outline=None, width=1):
        self.draw.rectangle(xy, fill=fill, outline=outline, width=width)

    def save(self, path):
        self.image.save(path, format="PNG")
        return "\n".join(text for _, _, text in sorted(self.entries)) + "\n"


def syntax_color(line):
    if line.lstrip().startswith(("#", "//", "--")):
        return "#78a875"
    if any(token in line for token in ("def ", "function ", "export function", "fn ", "class ", "CREATE ", "SELECT ", "return ")):
        return "#76b7e5"
    if any(token in line for token in ("\"", "'")):
        return "#e4b66a"
    return "#d8dee9"


def render_ide(screen, sample):
    filename, code = sample
    screen.box((0, 0, WIDTH, 66), "#20242c")
    screen.text(34, 20, "Nexa Studio  |  File  Edit  Selection  View  Run", 23, "#d4dae4")
    screen.text(1540, 20, "workspace  |  Python", 21, "#aab5c4")
    screen.box((0, 66, 355, HEIGHT), "#1c2028")
    screen.text(28, 91, "EXPLORER", 19, "#96a4b7")
    for index, value in enumerate(("workspace", "src", filename, "tests", "README.md")):
        screen.text(34 + (18 if index > 0 else 0), 138 + index * 36, value, 21, "#d4dae4")
    screen.box((355, 66, WIDTH, 117), "#282d36")
    screen.text(383, 84, filename, 22, "#f0f3f7")
    screen.text(1470, 84, "OUTLINE", 18, "#96a4b7")
    screen.box((355, 117, 1530, HEIGHT), "#171a20")
    screen.text(1560, 132, "SYMBOLS", 18, "#96a4b7")
    screen.text(1560, 171, "Functions", 21, "#d4dae4")
    screen.text(1560, 210, "Classes", 21, "#d4dae4")
    selected = 2 + (int(filename[0], 36) % max(1, len(code) - 4))
    line_y = 140
    for index, line in enumerate(code, 1):
        y = line_y + (index - 1) * 45
        if y > HEIGHT - 38:
            break
        if index == selected:
            screen.box((355, y - 4, 1530, y + 34), "#42351f")
        screen.text(390, y, f"{index:>2}  {line}", 23, syntax_color(line), font=load_font(["CascadiaMono.ttf", "consola.ttf"], 23))
    screen.text(1560, 292, "GIT", 18, "#96a4b7")
    screen.text(1560, 331, "working tree", 20, "#d4dae4")
    screen.text(1560, 380, f"highlight: amber", 19, "#e4b66a")
    return selected


def render_terminal(screen, sample, variant):
    title, lines = sample
    screen.box((0, 0, WIDTH, 64), "#242832")
    screen.text(30, 18, f"Terminal  |  {title}  |  PowerShell", 24, "#d4dae4")
    screen.box((0, 64, WIDTH, HEIGHT), "#101317")
    markers = ("error:", "error ", "fatal:", "assertionerror:", "operationalerror:", "permission denied", "severity:")
    error_line = next((line for line in lines if any(marker in line.lower() for marker in markers)), lines[-1])
    for index, line in enumerate(lines):
        y = 104 + index * 57
        color = "#f0ad4e" if line == error_line else ("#ed6a5a" if "FATAL" in line or "failed" in line.lower() else "#d7e0e8")
        screen.text(48, y, line, 25, color, font=load_font(["CascadiaMono.ttf", "consola.ttf"], 25))
    screen.text(1640, 1010, f"session {variant + 1:02d}", 20, "#8995a4")
    return error_line


def render_web(screen, sample, variant):
    title, subtitle, cards = sample
    screen.box((0, 0, WIDTH, 62), "#e9edf0")
    screen.text(30, 17, "‹   ›   ⟳     https://nexa.local/notes", 21, "#293845")
    screen.box((0, 62, WIDTH, 146), "#ffffff")
    screen.text(95, 92, title, 30, "#1c3844")
    screen.text(1340, 98, "Overview    Notes    Contact", 21, "#3b5965")
    screen.box((0, 146, WIDTH, 438), "#dce9e7")
    screen.text(115, 208, subtitle, 25, "#385b58")
    screen.text(115, 270, title, 45, "#193e3a")
    screen.text(115, 352, "Updated today  |  Details and service information", 22, "#4a6964")
    screen.text(115, 492, "At a glance", 29, "#233b42")
    colors = ["#ffffff", "#f5f7f6", "#ffffff"]
    x_values = [115, 690, 1265]
    for index, card in enumerate(cards[:3]):
        screen.box((x_values[index], 552, x_values[index] + 520, 842), colors[index], "#cad6d5")
        screen.text(x_values[index] + 30, 592, f"0{index + 1}  {card}", 25, "#264c50")
        screen.text(x_values[index] + 30, 656, "Open details", 20, "#3b7770")
    screen.box((0, 926, WIDTH, HEIGHT), "#f2f4f3")
    screen.text(115, 970, f"{title}  |  Information page  |  Reference {variant + 1:02d}", 20, "#596a70")
    return cards[variant % 3]


def render_document(screen, sample, variant):
    title, department, paragraphs = sample
    screen.box((0, 0, WIDTH, 60), "#303943")
    screen.text(28, 17, "Document Viewer  |  File  Edit  View", 22, "#eef2f4")
    screen.box((0, 60, WIDTH, 110), "#e7ebee")
    screen.text(32, 77, f"{title}.pdf", 20, "#33434c")
    screen.box((0, 110, 340, HEIGHT), "#e8ecef")
    screen.text(32, 144, "CONTENTS", 19, "#687985")
    screen.text(32, 192, "Bookmarks", 22, "#235f79")
    screen.text(32, 244, "Comments", 22, "#566974")
    screen.text(32, 296, "Page 1 of 1", 20, "#566974")
    screen.box((340, 110, 1580, HEIGHT), "#cbd2d7")
    screen.box((430, 144, 1490, 990), "#fffefa", "#c1c7c9")
    screen.text(510, 208, department.upper(), 19, "#60737b")
    screen.text(510, 264, title, 36, "#243b45")
    screen.text(510, 334, f"Review note  |  Issue {variant + 1:02d}", 20, "#62737a")
    for index, paragraph in enumerate(paragraphs):
        screen.text(510, 425 + index * 104, paragraph, 22, "#343e42")
    screen.box((1580, 110, WIDTH, HEIGHT), "#f1f3f4")
    screen.text(1610, 144, "REVIEW", 19, "#687985")
    screen.text(1610, 192, "Selected", 22, "#235f79")
    screen.text(1610, 244, "Comments  2", 20, "#566974")
    return "Bookmarks"


def render_spreadsheet(screen, sample, variant):
    name, headers, rows = sample
    screen.box((0, 0, WIDTH, 58), "#f4f5f6")
    screen.text(25, 16, f"Workbook  |  {name}.xlsx  |  Saved", 22, "#33404a")
    screen.box((0, 58, WIDTH, 110), "#e6e9ec")
    screen.text(28, 77, "File    Home    Insert    Data    Review", 20, "#46545d")
    screen.box((0, 110, WIDTH, 154), "#fafbfc")
    screen.text(28, 124, "fx", 20, "#68747b")
    screen.text(93, 124, "A1", 20, "#33404a")
    left, top, row_h = 78, 196, 102
    widths = [180, 400, 400]
    x_positions = [left, left + widths[0], left + widths[0] + widths[1]]
    for column in range(3):
        screen.box((x_positions[column], top - 40, x_positions[column] + widths[column], top), "#e7eaed", "#c3cbd0")
        screen.text(x_positions[column] + 18, top - 32, chr(ord("A") + column), 18, "#4c5a62")
    screen.box((0, top, left, top + row_h * 5), "#e7eaed")
    for row_index in range(5):
        y = top + row_index * row_h
        screen.text(28, y + 34, str(row_index + 1), 18, "#4c5a62")
        values = headers if row_index == 0 else rows[row_index - 1]
        for column, value in enumerate(values):
            fill = "#dce9ef" if row_index == 0 else ("#fff4d8" if row_index == 1 and column == 0 else "#ffffff")
            screen.box((x_positions[column], y, x_positions[column] + widths[column], y + row_h), fill, "#d0d6da")
            screen.text(x_positions[column] + 18, y + 33, value, 22, "#2e3c43")
    screen.text(1050, 229, f"Sheet: {name}", 23, "#53636b")
    screen.text(1050, 286, "Selected cell: A1", 20, "#53636b")
    screen.text(1050, 343, "Filter: All records", 20, "#53636b")
    return rows[0][0]


def render_record(category, sample, variant):
    fonts = ["segoeui.ttf", "arial.ttf"] if category in ("webpage", "document", "spreadsheet") else ["CascadiaMono.ttf", "consola.ttf"]
    background = {"ide_code": "#171a20", "terminal_error": "#101317", "webpage": "#f7f9f8", "document": "#cbd2d7", "spreadsheet": "#ffffff"}[category]
    screen = Screen(background, fonts)
    if category == "ide_code":
        selected = render_ide(screen, sample)
        title = sample[0]
        questions = [
            {"q": "Which code line is highlighted amber?", "a": f"line {selected}"},
            {"q": "Which file is open in the editor?", "a": title},
        ]
        summary = f"The IDE shows {title} in the main editor with a selected line highlighted in amber. The project explorer and symbol panels remain visible around the source code."
    elif category == "terminal_error":
        error_line = render_terminal(screen, sample, variant)
        status = error_line.split()[0].rstrip(":")
        questions = [
            {"q": "Which status label is highlighted amber?", "a": status[:30]},
            {"q": "Which command is shown in the terminal?", "a": sample[1][0][2:]},
        ]
        summary = f"The terminal records the {sample[0]} command and its resulting diagnostic output. The failure or warning is highlighted against the dark console background."
    elif category == "webpage":
        card = render_web(screen, sample, variant)
        title = sample[0]
        questions = [
            {"q": "Which card appears in the leftmost position?", "a": sample[2][0]},
            {"q": "What is the page title?", "a": title},
        ]
        summary = f"The webpage presents {title} with a short introduction and three information cards. The leftmost card is {card}, followed by two related items."
    elif category == "document":
        selected = render_document(screen, sample, variant)
        title = sample[0]
        questions = [
            {"q": "Which tab is selected in the left contents panel?", "a": selected},
            {"q": "What department is named above the document title?", "a": sample[1]},
        ]
        summary = f"The document viewer displays {title}, issued by {sample[1]}. Its page contains three short review notes, and the Bookmarks tab is selected in the contents panel."
    else:
        first_region = render_spreadsheet(screen, sample, variant)
        title, headers, rows = sample
        questions = [
            {"q": "Which region or item is in the first data row?", "a": first_region},
            {"q": "Which column is at the far left?", "a": headers[0]},
        ]
        summary = f"The {title} worksheet shows three labeled columns and four data rows. The first data row begins with {first_region}, positioned directly below the header row."
    return screen, questions, summary


def main():
    DATASET.mkdir(parents=True, exist_ok=True)
    records = []
    samples = {
        "ide_code": IDE_SAMPLES,
        "terminal_error": TERMINAL_SAMPLES,
        "webpage": WEB_SAMPLES,
        "document": DOCUMENT_SAMPLES,
        "spreadsheet": SPREADSHEET_SAMPLES,
    }
    for category, category_samples in samples.items():
        if len(category_samples) != 8:
            raise ValueError(f"Expected 8 {category} samples; found {len(category_samples)}")
        for index, sample in enumerate(category_samples, 1):
            image_name = f"{category}_{index:02d}"
            screen, questions, summary = render_record(category, sample, index - 1)
            ground_truth = screen.save(DATASET / f"{image_name}.png")
            (DATASET / f"{image_name}.txt").write_text(ground_truth, encoding="utf-8")
            metadata = {
                "category": CATEGORIES[category],
                "questions": questions,
                "summary": summary,
            }
            (DATASET / f"{image_name}.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            records.append((image_name, screen.image.copy()))

    columns, tile_w, tile_h, label_h = 4, 480, 270, 30
    rows = (len(records) + columns - 1) // columns
    preview = Image.new("RGB", (columns * tile_w, rows * (tile_h + label_h)), "#20242b")
    preview_draw = ImageDraw.Draw(preview)
    label_font = load_font(["segoeui.ttf", "arial.ttf"], 17)
    for index, (name, image) in enumerate(records):
        x = (index % columns) * tile_w
        y = (index // columns) * (tile_h + label_h)
        preview.paste(image.resize((tile_w, tile_h), Image.Resampling.LANCZOS), (x, y))
        preview_draw.text((x + 8, y + tile_h + 5), name, fill="#f1f4f6", font=label_font)
    preview.save(PREVIEW, format="PNG")
    print(f"Generated {len(records)} screenshots in {DATASET}")
    print(f"Category counts: {json.dumps({CATEGORIES[key]: len(value) for key, value in samples.items()}, sort_keys=True)}")
    print(f"Screenshot dimensions: {WIDTH}x{HEIGHT}")
    print(f"Contact sheet: {PREVIEW}")


if __name__ == "__main__":
    main()