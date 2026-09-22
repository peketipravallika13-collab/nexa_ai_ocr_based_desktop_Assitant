import os
import sys
import re
import io
import json
import logging
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

logger = logging.getLogger("input_processors")

def get_temp_dir():
    temp_dir = os.path.join(os.path.expanduser("~"), ".nexa_ai", "temp_attachments")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

# ------------------------------------------------------------------------------
# 1. Text & Code Files
# ------------------------------------------------------------------------------
CODE_EXTENSIONS = {
    '.py': 'python', '.js': 'javascript', '.jsx': 'javascript', '.ts': 'typescript',
    '.tsx': 'typescript', '.html': 'html', '.htm': 'html', '.css': 'css',
    '.scss': 'scss', '.json': 'json', '.xml': 'xml', '.yaml': 'yaml',
    '.yml': 'yaml', '.sql': 'sql', '.c': 'c', '.cpp': 'cpp', '.h': 'c',
    '.cs': 'csharp', '.java': 'java', '.go': 'go', '.rs': 'rust',
    '.php': 'php', '.rb': 'ruby', '.sh': 'bash', '.bat': 'batch',
    '.ps1': 'powershell', '.md': 'markdown', '.txt': 'text', '.log': 'text',
    '.ini': 'ini', '.cfg': 'ini', '.toml': 'toml'
}

def read_text_or_code(file_path):
    """Read plain text or code file with encoding fallbacks."""
    for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            ext = os.path.splitext(file_path)[1].lower()
            lang = CODE_EXTENSIONS.get(ext, '')
            filename = os.path.basename(file_path)
            lines_count = len(content.splitlines())
            
            # Truncate if excessively large (keep up to ~25,000 characters)
            if len(content) > 30000:
                content = content[:30000] + f"\n\n... [Content truncated from {lines_count} total lines] ..."
                
            formatted = f"📄 **Attached File:** `{filename}` ({lines_count} lines)\n```{lang}\n{content}\n```"
            return {
                "type": "code" if lang in ('python', 'javascript', 'html', 'css', 'cpp', 'java', 'sql', 'json') else "document",
                "text": formatted,
                "summary": f"`{filename}` ({lines_count} lines)",
                "filename": filename,
                "path": file_path
            }
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"Error reading text file {file_path}: {e}")
            return {"type": "error", "error": f"Failed to read file: {e}"}
            
    return {"type": "error", "error": "Unable to decode text file with standard encodings."}

# ------------------------------------------------------------------------------
# 2. DOCX Word Documents (Pure Python Zero-Dependency Parser)
# ------------------------------------------------------------------------------
def read_docx(file_path):
    """Extract text from .docx file using standard library zipfile & XML parser."""
    try:
        with zipfile.ZipFile(file_path) as z:
            xml_content = z.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            
            # Namespace map for WordprocessingML
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            paragraphs = []
            for p in tree.iterfind('.//w:p', ns):
                texts = [node.text for node in p.iterfind('.//w:t', ns) if node.text]
                if texts:
                    paragraphs.append(''.join(texts))
                    
            full_text = "\n\n".join(paragraphs).strip()
            filename = os.path.basename(file_path)
            
            if len(full_text) > 30000:
                full_text = full_text[:30000] + "\n\n... [Content truncated] ..."
                
            formatted = f"📄 **Attached Word Document:** `{filename}`\n\n```text\n{full_text}\n```"
            return {
                "type": "document",
                "text": formatted,
                "summary": f"`{filename}` (Word Doc, {len(paragraphs)} paragraphs)",
                "filename": filename,
                "path": file_path
            }
    except Exception as e:
        logger.error(f"Error parsing DOCX {file_path}: {e}")
        return {"type": "error", "error": f"Failed to parse Word Document: {e}"}

# ------------------------------------------------------------------------------
# 3. PDF Documents
# ------------------------------------------------------------------------------
def read_pdf(file_path):
    """Extract text from PDF using PyMuPDF (fitz), pypdf, or EasyOCR for scanned pages."""
    filename = os.path.basename(file_path)
    extracted_pages = []
    num_pages = 0
    scanned_image_path = None

    # 1. Try PyMuPDF (fitz) - Highest accuracy & speed
    try:
        import fitz
        doc = fitz.open(file_path)
        num_pages = len(doc)
        for i in range(min(num_pages, 30)):
            page = doc[i]
            page_text = page.get_text("text").strip()
            if page_text:
                extracted_pages.append(f"--- Page {i+1} ---\n{page_text}")
                
        # If no extractable text (e.g. scanned PDF), render first page to image for OCR / Vision
        if not extracted_pages and num_pages > 0:
            try:
                page0 = doc[0]
                pix = page0.get_pixmap(dpi=150)
                temp_img = os.path.join(get_temp_dir(), f"pdf_render_{int(datetime.now().timestamp())}.png")
                pix.save(temp_img)
                scanned_image_path = temp_img
                
                # Perform OCR on rendered page
                import ocr_engine
                from PIL import Image
                rendered_pil = Image.open(temp_img)
                processed_np = ocr_engine.preprocess_image(rendered_pil)
                reader = ocr_engine.get_ocr_reader()
                ocr_results = reader.readtext(processed_np)
                ocr_results.sort(key=lambda x: (x[0][0][1], x[0][0][0]))
                ocr_text = " ".join([r[1] for r in ocr_results if r[2] > 0.15]).strip()
                if ocr_text:
                    extracted_pages.append(f"--- Page 1 (Scanned OCR) ---\n{ocr_text}")
            except Exception as ocr_err:
                logger.warning(f"Scanned PDF OCR fallback failed: {ocr_err}")
                
        doc.close()
    except Exception as e:
        logger.warning(f"PyMuPDF PDF extraction failed: {e}")

    # 2. Try pypdf / PyPDF2 fallback if PyMuPDF didn't yield text
    if not extracted_pages:
        for mod_name in ['pypdf', 'PyPDF2']:
            try:
                pypdf_mod = __import__(mod_name)
                reader = pypdf_mod.PdfReader(file_path)
                num_pages = len(reader.pages)
                for i in range(min(num_pages, 30)):
                    page_text = reader.pages[i].extract_text()
                    if page_text and page_text.strip():
                        extracted_pages.append(f"--- Page {i+1} ---\n{page_text.strip()}")
                if extracted_pages:
                    break
            except Exception as e:
                logger.warning(f"Extraction with {mod_name} failed: {e}")

    # 3. Fallback regex stream extractor
    if not extracted_pages:
        try:
            with open(file_path, 'rb') as f:
                raw = f.read()
            text_matches = re.findall(rb'\((.*?)\)\s*T[jJ]', raw)
            if text_matches:
                decoded = " ".join([m.decode('latin-1', errors='ignore') for m in text_matches[:500]])
                if decoded.strip():
                    extracted_pages.append(decoded.strip())
        except Exception:
            pass

    full_text = "\n\n".join(extracted_pages).strip()
    
    if not full_text:
        full_text = "[PDF contains no extractable text or is password-protected.]"
    elif len(full_text) > 35000:
        full_text = full_text[:35000] + f"\n\n... [Content truncated from {num_pages} pages] ..."

    page_info = f" ({num_pages} pages)" if num_pages > 0 else ""
    formatted = f"📄 **Attached PDF Document:** `{filename}`{page_info}\n\n```text\n{full_text}\n```"
    
    res = {
        "type": "document",
        "text": formatted,
        "summary": f"`{filename}` (PDF{page_info})",
        "filename": filename,
        "path": file_path
    }
    if scanned_image_path:
        res["image_path"] = scanned_image_path
        res["type"] = "image"
        
    return res

# ------------------------------------------------------------------------------
# 4. CSV & Excel Spreadsheets
# ------------------------------------------------------------------------------
def read_spreadsheet(file_path):
    """Read CSV, TSV, or Excel file and generate summary table and statistics."""
    filename = os.path.basename(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    
    # Check if CSV / TSV
    if ext in ('.csv', '.tsv'):
        import csv
        delimiter = '\t' if ext == '.tsv' else ','
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = list(csv.reader(f, delimiter=delimiter))
                
            if not reader:
                return {"type": "error", "error": "CSV file is empty."}
                
            headers = reader[0]
            total_rows = len(reader) - 1
            sample_rows = reader[1:11] # Top 10 sample rows
            
            table_md = "| " + " | ".join(headers) + " |\n"
            table_md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
            for row in sample_rows:
                padded_row = row + [""] * (len(headers) - len(row))
                table_md += "| " + " | ".join([cell.replace("|", "/") for cell in padded_row[:len(headers)]]) + " |\n"
                
            formatted = (
                f"📊 **Attached Spreadsheet Data:** `{filename}`\n"
                f"- **Total Columns ({len(headers)}):** {', '.join(headers)}\n"
                f"- **Total Rows:** {total_rows}\n\n"
                f"**Preview of first {len(sample_rows)} rows:**\n\n"
                f"{table_md}"
            )
            return {
                "type": "data",
                "text": formatted,
                "summary": f"`{filename}` ({total_rows} rows × {len(headers)} cols)",
                "filename": filename,
                "path": file_path
            }
        except Exception as e:
            return {"type": "error", "error": f"Failed reading CSV: {e}"}
            
    # For Excel (.xlsx, .xls)
    try:
        import pandas as pd
        df = pd.read_excel(file_path, nrows=500)
        shape_info = f"{df.shape[0]} rows × {df.shape[1]} columns"
        preview_md = df.head(10).to_markdown()
        formatted = (
            f"📊 **Attached Excel Spreadsheet:** `{filename}` ({shape_info})\n\n"
            f"**Preview (first 10 rows):**\n\n{preview_md}\n\n"
            f"**Column Statistics:**\n```text\n{df.describe(include='all').to_string()}\n```"
        )
        return {
            "type": "data",
            "text": formatted,
            "summary": f"`{filename}` (Excel: {shape_info})",
            "filename": filename,
            "path": file_path
        }
    except Exception:
        # Fallback if pandas not available or parsing failed
        return read_text_or_code(file_path)

# ------------------------------------------------------------------------------
# 5. Video Processing (Keyframe Grid Extraction for Vision AI)
# ------------------------------------------------------------------------------
def process_video_file(file_path):
    """Extract keyframes from video and compile a composite storyboard image for multimodal AI."""
    import cv2
    import numpy as np
    from PIL import Image
    
    filename = os.path.basename(file_path)
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        return {"type": "error", "error": f"Could not open video file: {filename}"}
        
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = round(frame_count / fps, 1) if fps > 0 else 0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Pick 4 representative timestamps: 10%, 35%, 65%, 90%
    timestamps = [0.10, 0.35, 0.65, 0.90]
    extracted_frames = []
    
    for pct in timestamps:
        target_frame = int(frame_count * pct)
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame = cap.read()
        if ret and frame is not None:
            # Resize frame to standard width 480px while maintaining aspect ratio
            h, w = frame.shape[:2]
            new_w = 480
            new_h = int(h * (new_w / w))
            resized = cv2.resize(frame, (new_w, new_h))
            
            # Put timestamp label on the frame
            time_str = f"{int((target_frame / fps) // 60):02d}:{int((target_frame / fps) % 60):02d}"
            cv2.putText(resized, f"Time: {time_str}", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
            cv2.putText(resized, f"Time: {time_str}", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            extracted_frames.append(Image.fromarray(rgb_frame))
            
    cap.release()
    
    if not extracted_frames:
        return {"type": "error", "error": "Could not extract video frames."}
        
    # Stitch frames into a 2x2 grid storyboard
    fw, fh = extracted_frames[0].size
    grid_img = Image.new("RGB", (fw * 2, fh * 2), color=(15, 15, 20))
    positions = [(0, 0), (fw, 0), (0, fh), (fw, fh)]
    for idx, img in enumerate(extracted_frames[:4]):
        grid_img.paste(img, positions[idx])
        
    output_path = os.path.join(get_temp_dir(), f"video_storyboard_{int(datetime.now().timestamp())}.jpg")
    grid_img.save(output_path, "JPEG", quality=85)
    
    summary_text = (
        f"🎥 **Attached Video:** `{filename}`\n"
        f"- **Duration:** {duration_sec}s | **Resolution:** {width}x{height} | **FPS:** {round(fps, 1)}\n"
        f"- *Visual Storyboard extracted (4 keyframes across timeline) and attached for visual analysis.*"
    )
    
    return {
        "type": "video",
        "image_path": output_path,
        "text": summary_text,
        "summary": f"`{filename}` ({duration_sec}s video)",
        "filename": filename,
        "path": file_path
    }

# ------------------------------------------------------------------------------
# 6. Audio Processing & Speech-to-Text
# ------------------------------------------------------------------------------
def process_audio_file(file_path):
    """Process audio file and transcribe speech using SpeechRecognition."""
    import speech_recognition as sr
    filename = os.path.basename(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    
    # If WAV, transcribe directly
    wav_path = file_path
    temp_wav = None
    
    try:
        recognizer = sr.Recognizer()
        
        # If not wav, try converting or reading
        if ext != '.wav':
            # Attempt to convert using pydub or soundfile if available
            try:
                import soundfile as sf
                data, samplerate = sf.read(file_path)
                temp_wav = os.path.join(get_temp_dir(), f"temp_audio_{int(datetime.now().timestamp())}.wav")
                sf.write(temp_wav, data, samplerate)
                wav_path = temp_wav
            except Exception:
                pass
                
        if wav_path.endswith('.wav'):
            with sr.AudioFile(wav_path) as source:
                audio = recognizer.record(source)
            transcription = recognizer.recognize_google(audio)
            
            formatted = f"🎵 **Attached Audio Recording:** `{filename}`\n\n**Transcribed Voice Text:**\n> \"{transcription}\""
            return {
                "type": "audio",
                "text": formatted,
                "summary": f"`{filename}` (Transcribed Audio)",
                "filename": filename,
                "path": file_path
            }
    except sr.UnknownValueError:
        return {
            "type": "audio",
            "text": f"🎵 **Attached Audio:** `{filename}`\n*(Audio detected, no clear spoken voice identified for automatic transcription)*",
            "summary": f"`{filename}` (Audio File)",
            "filename": filename,
            "path": file_path
        }
    except Exception as e:
        logger.warning(f"Audio transcription error {file_path}: {e}")
    finally:
        if temp_wav and os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass
                
    return {
        "type": "audio",
        "text": f"🎵 **Attached Audio File:** `{filename}` (Ready for audio analysis)",
        "summary": f"`{filename}` (Audio File)",
        "filename": filename,
        "path": file_path
    }

# ------------------------------------------------------------------------------
# 7. Live Camera Photo Capture (Webcam Snapshot)
# ------------------------------------------------------------------------------
def capture_webcam_snapshot():
    """Capture a single photo snapshot from default webcam (0)."""
    import cv2
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        # Try device index 1
        cap = cv2.VideoCapture(1)
        if not cap.isOpened():
            return {"type": "error", "error": "No accessible webcam or camera device found on this system."}
            
    # Allow camera sensor auto-exposure to adjust
    for _ in range(5):
        cap.read()
        
    ret, frame = cap.read()
    cap.release()
    
    if not ret or frame is None:
        return {"type": "error", "error": "Failed to capture photo from webcam."}
        
    snap_path = os.path.join(get_temp_dir(), f"camera_snap_{int(datetime.now().timestamp())}.jpg")
    cv2.imwrite(snap_path, frame)
    
    return {
        "type": "image",
        "image_path": snap_path,
        "text": "📷 **Camera Snapshot:** Captured live from webcam for visual analysis.",
        "summary": "📷 Camera Snapshot",
        "filename": os.path.basename(snap_path),
        "path": snap_path
    }

# ------------------------------------------------------------------------------
# 8. Webpage URL Fetcher & Article Parser
# ------------------------------------------------------------------------------
def fetch_url_content(url):
    """Fetch webpage HTML and parse clean readable article content without heavy browser engines."""
    import requests
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code != 200:
            return {"type": "error", "error": f"HTTP {res.status_code} error fetching webpage."}
            
        html_text = res.text
        
        # Extract title
        title_match = re.search(r'<title>(.*?)</title>', html_text, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else url
        title = re.sub(r'\s+', ' ', title)
        
        # Clean HTML tags and scripts
        cleaned = re.sub(r'<(script|style|nav|footer|header|noscript)[\s\S]*?</\1>', ' ', html_text, flags=re.IGNORECASE)
        cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        if len(cleaned) > 20000:
            cleaned = cleaned[:20000] + "\n\n... [Webpage content truncated] ..."
            
        formatted = f"🔗 **Attached Webpage Analysis:** [{title}]({url})\n\n```text\n{cleaned}\n```"
        return {
            "type": "url",
            "url": url,
            "text": formatted,
            "summary": f"🔗 {title[:40]}...",
            "filename": title[:30]
        }
    except Exception as e:
        logger.error(f"Failed fetching URL {url}: {e}")
        return {"type": "error", "error": f"Failed to fetch webpage: {str(e)}"}

# ------------------------------------------------------------------------------
# 9. Nexa Project & Conversation Capsule Parser
# ------------------------------------------------------------------------------
def is_nexa_capsule(data: dict) -> bool:
    """Check if dictionary has Nexa Project Capsule structure."""
    if not isinstance(data, dict):
        return False
    capsule_keys = {"project", "completed_work", "next_steps", "technology", "goal", "nexa_capsule_version", "important_decisions"}
    matching = [k for k in capsule_keys if k in data]
    return len(matching) >= 2

def read_nexa_capsule_file(file_path: str) -> dict:
    """Load and parse a Nexa Project Capsule file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not is_nexa_capsule(data):
            return read_text_or_code(file_path)
            
        filename = os.path.basename(file_path)
        project_name = data.get("project", "Untitled Project")
        goal = data.get("goal", "N/A")
        tech_list = data.get("technology", [])
        tech_str = ", ".join(tech_list) if isinstance(tech_list, list) else str(tech_list)
        
        completed_items = data.get("completed_work", [])
        completed_str = "\n".join([f"- ✅ {item}" for item in completed_items]) if completed_items else "- None listed"
        
        decision_items = data.get("important_decisions", [])
        decision_str = "\n".join([f"- 💡 {item}" for item in decision_items]) if decision_items else "- None listed"
        
        next_items = data.get("next_steps", [])
        next_str = "\n".join([f"- 🚀 {item}" for item in next_items]) if next_items else "- Continue project"
        
        current_status = data.get("current_status", "Active")
        summary = data.get("conversation_summary", "")
        
        formatted_text = (
            f"📦 **Imported Nexa Project Capsule:** `{project_name}`\n\n"
            f"**🎯 Project Goal:** {goal}\n"
            f"**🛠️ Tech Stack:** {tech_str}\n"
            f"**⚡ Current Status:** {current_status}\n\n"
            f"**✅ Completed Work:**\n{completed_str}\n\n"
            f"**💡 Key Decisions & Architecture:**\n{decision_str}\n\n"
            f"**🚀 Next Steps:**\n{next_str}\n"
        )
        if summary:
            formatted_text += f"\n**📝 Context Summary:** {summary}\n"
            
        return {
            "type": "capsule",
            "text": formatted_text,
            "summary": f"📦 Capsule: {project_name[:25]}",
            "filename": filename,
            "path": file_path,
            "capsule_data": data
        }
    except Exception as e:
        logger.error(f"Error reading capsule file {file_path}: {e}")
        return read_text_or_code(file_path)

# ------------------------------------------------------------------------------
# 10. Main Universal Input Router
# ------------------------------------------------------------------------------
def process_any_file(file_path):
    """Detect file type and dispatch to appropriate processor."""
    if not os.path.exists(file_path):
        return {"type": "error", "error": f"File does not exist: {file_path}"}
        
    ext = os.path.splitext(file_path)[1].lower()
    
    # 0. Check for Project Capsule files (.json or .nexa_capsule)
    if ext in ('.json', '.nexa_capsule', '.capsule'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                peek_data = json.load(f)
            if is_nexa_capsule(peek_data):
                return read_nexa_capsule_file(file_path)
        except Exception:
            pass
    
    # 1. Images
    if ext in ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.tiff'):
        return {
            "type": "image",
            "image_path": file_path,
            "text": f"🖼️ **Attached Image:** `{os.path.basename(file_path)}`",
            "summary": f"`{os.path.basename(file_path)}`",
            "filename": os.path.basename(file_path),
            "path": file_path
        }
        
    # 2. Videos
    if ext in ('.mp4', '.mov', '.avi', '.webm', '.mkv', '.m4v'):
        return process_video_file(file_path)
        
    # 3. Audio
    if ext in ('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac'):
        return process_audio_file(file_path)
        
    # 4. Word Documents
    if ext in ('.docx', '.doc'):
        return read_docx(file_path)
        
    # 5. PDF
    if ext == '.pdf':
        return read_pdf(file_path)
        
    # 6. Spreadsheets / Data
    if ext in ('.csv', '.tsv', '.xlsx', '.xls'):
        return read_spreadsheet(file_path)
        
    # 7. Text & Code files
    return read_text_or_code(file_path)
