import os
# Set environment variable to prevent OpenMP duplicate runtime crashes when combining PyTorch and Qt
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import time
import re
import logging
from PIL import Image
import numpy as np
import torch
import easyocr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr_engine")

_reader = None

def get_ocr_reader():
    """Lazily load and cache the EasyOCR reader to save memory and startup time."""
    global _reader
    if _reader is None:
        logger.info("Initializing EasyOCR reader...")
        use_gpu = torch.cuda.is_available()
        logger.info(f"EasyOCR GPU support: {use_gpu}")
        # Initialize reader for English
        _reader = easyocr.Reader(['en'], gpu=use_gpu)
    return _reader

def preprocess_image(image):
    """
    Preprocess image for better OCR accuracy.
    Converts PIL Image to grayscale and enhances contrast.
    """
    import cv2
    
    # Convert PIL Image to RGB (guarantees 3 channels: RGB)
    img_rgb = image.convert("RGB")
    img_np = np.array(img_rgb)
    
    # PIL RGB -> OpenCV BGR -> Grayscale
    bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        
    # Resize image to double the size if it's low resolution
    # This helps EasyOCR with smaller fonts
    h, w = gray.shape
    if w < 1000 or h < 800:
        gray = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        
    # Contrast enhancement (CLAHE - Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Apply moderate bilateral filtering to denoise while preserving text edges
    denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
    
    # Return processed numpy array
    return denoised

def clean_extracted_text(text, max_length=15000):
    """Clean the OCR text using regex and basic NLP techniques and enforce character limits."""
    if not text:
        return ""
        
    # Remove excessive empty lines (more than 2 consecutive newlines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Clean multiple spaces or tabs
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Remove control characters or non-printable characters except basic symbols & punctuation
    # (keeps english unicode, numbers, punctuation, layout newlines)
    text = "".join(ch for ch in text if ch.isprintable() or ch in ('\n', '\r', '\t'))
    
    text = text.strip()
    
    # Enforce maximum character length limit to protect API token context and prevent database bloat
    if len(text) > max_length:
        logger.warning(f"OCR text length ({len(text)} characters) exceeded maximum limit ({max_length}). Truncating text.")
        text = text[:max_length] + "\n\n[Extracted text truncated due to character length limits...]"
        
    return text

def capture_screen_and_ocr(auto_scroll=False, scroll_count=3, on_capture_done=None, canvas_size=1024, batch_size=32):
    """
    Capture the screen, preprocess the image, and perform EasyOCR text extraction.
    If auto_scroll is True, perform multiple captures while scrolling down.
    """
    import mss
    import pyautogui
    
    screenshots_dir = os.path.join(os.path.expanduser("~"), ".nexa_ai", "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)
    
    captured_texts = []
    first_screenshot_path = None
    screenshots = []
    
    with mss.mss() as sct:
        # Get the primary monitor
        if len(sct.monitors) > 1:
            monitor = sct.monitors[1]
        else:
            monitor = sct.monitors[0]
            
        # 1. Grab all screen captures first to minimize desktop flicker/interference
        for i in range(scroll_count if auto_scroll else 1):
            if i > 0:
                logger.info(f"Auto scrolling down (Step {i})...")
                # Scroll down using PyAutoGUI Page Down keypress for maximum compatibility with third-party applications
                pyautogui.press('pagedown')
                # Wait for the screen to settle (avoid motion blur in screenshot)
                time.sleep(0.8)
                
            logger.info("Capturing screenshot...")
            sct_img = sct.grab(monitor)
            
            # Convert mss image bytes to PIL Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            # Save the screenshot for UI and DB records (save original PIL image)
            timestamp = int(time.time() * 1000)
            filename = f"capture_{timestamp}_{i}.png"
            filepath = os.path.join(screenshots_dir, filename)
            img.save(filepath)
            
            if i == 0:
                first_screenshot_path = filepath
                
            screenshots.append((filepath, img))
            
    # Call the callback immediately after all screenshots are captured to restore the parent window
    if on_capture_done:
        try:
            on_capture_done()
        except Exception as e:
            logger.error(f"Failed to execute on_capture_done callback: {e}")
        
    # 2. Perform OCR on the captured screenshots
    for i, (filepath, img) in enumerate(screenshots):
        logger.info(f"Extracting text from screenshot slice {i} via EasyOCR...")
        try:
            processed_img_np = preprocess_image(img)
            reader = get_ocr_reader()
            # Run text detection and recognition with optimized parameters for CPU performance speedup
            results = reader.readtext(processed_img_np, canvas_size=canvas_size, batch_size=batch_size)
            
            # Sort bounding boxes by top-to-bottom, left-to-right to read naturally
            results.sort(key=lambda x: (x[0][0][1], x[0][0][0]))
            
            texts_in_page = []
            for box, text_str, confidence in results:
                if confidence > 0.15:  # Filter out low-confidence noise
                    texts_in_page.append(text_str)
                    
            page_text = " ".join(texts_in_page)
            if page_text.strip():
                captured_texts.append(page_text)
        except Exception as e:
            logger.error(f"OCR processing failed for slice {i}: {e}")
            captured_texts.append(f"[OCR Error on page/slice {i}]")
            
    # Combine texts from all scrolls
    combined_text = "\n\n--- Page Scroll Break ---\n\n".join(captured_texts)
    cleaned_text = clean_extracted_text(combined_text)
    
    return first_screenshot_path, cleaned_text
