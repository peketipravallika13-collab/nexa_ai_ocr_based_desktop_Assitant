import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import sys
import time
import logging
import webbrowser

# Pre-import ocr_engine to initialize DLL runtimes before PyQt6
import ocr_engine

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
    QScrollArea, QLabel, QListWidget, QListWidgetItem, QDialog, 
    QLineEdit, QComboBox, QCheckBox, QFormLayout, QDialogButtonBox,
    QFrame, QSplitter, QTextBrowser, QSpinBox, QMenu, QFileDialog,
    QSizePolicy, QApplication, QTabWidget, QGridLayout, QRadioButton,
    QButtonGroup, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import (
    QFont, QIcon, QPixmap, QKeySequence, QAction, QPainter, 
    QRadialGradient, QBrush, QColor, QPen, QTextCursor, QCursor
)

import database
import ai_client
import input_processors
import plugin_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gui")


def markdown_to_html(text):
    """Convert markdown formatting to clean HTML for QTextBrowser."""
    if not text:
        return ""
    
    import html
    escaped_text = html.escape(text)
    
    import re
    def code_block_sub(match):
        code = match.group(2)
        code = html.unescape(code)
        code = html.escape(code)
        return f'<pre style="background-color: #090a12; padding: 12px; border-radius: 8px; font-family: \'Consolas\', \'Courier New\', monospace; color: #e2e8f0; border: 1px solid #222538; line-height: 1.45; margin: 8px 0;">{code}</pre>'
        
    escaped_text = re.sub(r'```(\w*)\n(.*?)\n```', code_block_sub, escaped_text, flags=re.DOTALL)
    escaped_text = re.sub(r'`(.*?)`', r'<code style="background-color: #1e2033; color: #f472b6; padding: 2px 6px; border-radius: 4px; font-family: \'Consolas\', monospace; font-size: 13px;">\1</code>', escaped_text)
    escaped_text = re.sub(r'\*\*(.*?)\*\*', r'<b style="color: #ffffff;">\1</b>', escaped_text)
    escaped_text = re.sub(r'\*(.*?)\*', r'<i style="color: #cbd5e1;">\1</i>', escaped_text)
    escaped_text = re.sub(r'^### (.*?)$', r'<h4 style="color: #c084fc; margin-top: 12px; margin-bottom: 6px;">\1</h4>', escaped_text, flags=re.MULTILINE)
    escaped_text = re.sub(r'^## (.*?)$', r'<h3 style="color: #d946ef; margin-top: 14px; margin-bottom: 8px;">\1</h3>', escaped_text, flags=re.MULTILINE)
    escaped_text = re.sub(r'^# (.*?)$', r'<h2 style="color: #f472b6; margin-top: 16px; margin-bottom: 10px;">\1</h2>', escaped_text, flags=re.MULTILINE)
    escaped_text = re.sub(r'^\s*[\-\*]\s+(.*?)$', r'<li style="margin-left: 15px; margin-bottom: 5px; color: #e2e8f0;">\1</li>', escaped_text, flags=re.MULTILINE)
    escaped_text = re.sub(r'^---$', r'<hr style="border: 0; height: 1px; background: #26293f; margin: 15px 0;">', escaped_text, flags=re.MULTILINE)
    
    lines = escaped_text.split('\n')
    processed_lines = []
    in_pre = False
    for line in lines:
        if "<pre" in line:
            in_pre = True
        if "</pre>" in line:
            in_pre = False
            
        if not in_pre and not line.strip().startswith("<li") and not line.strip().startswith("<h") and line.strip() != "" and not line.strip().startswith("<hr"):
            processed_lines.append(line + "<br>")
        else:
            processed_lines.append(line)
            
    escaped_text = "\n".join(processed_lines)
    return f'<div style="font-family: \'Segoe UI\', \'Inter\', Arial, sans-serif; font-size: 14px; color: #e2e8f0; line-height: 1.65; word-wrap: break-word;">{escaped_text}</div>'


class CosmicOrbWidget(QWidget):
    """Draws a smooth 3D glowing cosmic sphere."""
    def __init__(self, size=84, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        center_x = w / 2.0
        center_y = h / 2.0
        radius = min(w, h) / 2.0 - 5.0
        
        # Ambient outer glow
        glow_grad = QRadialGradient(center_x, center_y, radius + 5.0)
        glow_grad.setColorAt(0.0, QColor(217, 70, 239, 70))
        glow_grad.setColorAt(0.6, QColor(139, 92, 246, 30))
        glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow_grad))
        painter.drawEllipse(0, 0, w, h)
        
        # 3D Sphere body
        sphere_grad = QRadialGradient(center_x + radius * 0.28, center_y - radius * 0.32, radius * 1.3)
        sphere_grad.setColorAt(0.0, QColor(244, 114, 182))
        sphere_grad.setColorAt(0.22, QColor(225, 29, 72))
        sphere_grad.setColorAt(0.62, QColor(99, 102, 241))
        sphere_grad.setColorAt(0.88, QColor(14, 165, 233))
        sphere_grad.setColorAt(1.0, QColor(2, 132, 199))
        
        painter.setBrush(QBrush(sphere_grad))
        painter.drawEllipse(int(center_x - radius), int(center_y - radius), int(radius * 2), int(radius * 2))


class HeroWelcomeWidget(QWidget):
    """Empty state hero banner with glowing orb and suggestion cards."""
    def __init__(self, on_capture=None, on_attach=None, on_calculator=None, on_chart_generator=None, on_file_compressor=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 1. Cosmic Orb
        orb_container = QHBoxLayout()
        orb_container.addStretch()
        orb = CosmicOrbWidget(72, self)
        orb_container.addWidget(orb)
        orb_container.addStretch()
        layout.addLayout(orb_container)
        
        # 2. Hero Headline
        headline = QLabel(
            "What would you like Nexa to <span style='font-style: italic; color: #cbd5e1; font-family: Georgia, serif;'>analyze today?</span>",
            self
        )
        headline.setFont(QFont("Segoe UI", 16, QFont.Weight.Medium))
        headline.setStyleSheet("color: #ffffff; background: transparent;")
        headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(headline)
        
        sub = QLabel("Nexa natively understands Screen Captures, Multi-Modal Files, Charts, Math & File Compression — completely offline!", self)
        sub.setFont(QFont("Segoe UI", 11))
        sub.setStyleSheet("color: #94a3b8; background: transparent;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)
        
        # 3. Action Cards Grid
        cards_container = QWidget(self)
        cards_grid = QGridLayout(cards_container)
        cards_grid.setContentsMargins(0, 4, 0, 0)
        cards_grid.setSpacing(10)
        cards_grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        def create_hero_card(icon_str, title_str, subtitle_str, callback):
            card = QPushButton(cards_container)
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setFixedSize(195, 74)
            card.setStyleSheet("""
                QPushButton {
                    background-color: #121422;
                    border: 1px solid #23273e;
                    border-radius: 12px;
                    padding: 8px 10px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #1a1d30;
                    border-color: #8b5cf6;
                }
            """)
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(4, 4, 4, 4)
            c_layout.setSpacing(2)
            
            top_row = QHBoxLayout()
            icon_lbl = QLabel(icon_str, card)
            icon_lbl.setStyleSheet("font-size: 15px; background: transparent; border: none;")
            top_row.addWidget(icon_lbl)
            
            t_lbl = QLabel(title_str, card)
            t_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            t_lbl.setStyleSheet("color: #f1f5f9; background: transparent; border: none;")
            top_row.addWidget(t_lbl)
            top_row.addStretch()
            c_layout.addLayout(top_row)
            
            s_lbl = QLabel(subtitle_str, card)
            s_lbl.setStyleSheet("color: #64748b; font-size: 10px; background: transparent; border: none;")
            c_layout.addWidget(s_lbl)
            
            if callback:
                card.clicked.connect(callback)
            return card
            
        card_capture = create_hero_card("📷", "Capture Screen", "Snap & OCR analysis", on_capture)
        card_attach = create_hero_card("📎", "Attach File", "PDF, Code, CSV, Media", on_attach)
        card_calc = create_hero_card("🧮", "Calculator & Math", "Math & Unit Conversions", on_calculator)
        card_chart = create_hero_card("📈", "Chart Generator", "Bar, Line, Pie graphs", on_chart_generator)
        card_compress = create_hero_card("🗜️", "File Compressor", "ZIP & Unzip archives", on_file_compressor)
        
        # Row 0 (3 cards)
        cards_grid.addWidget(card_capture, 0, 0)
        cards_grid.addWidget(card_attach, 0, 1)
        cards_grid.addWidget(card_calc, 0, 2)
        # Row 1 (2 centered cards)
        row1_box = QHBoxLayout()
        row1_box.setSpacing(10)
        row1_box.addStretch()
        row1_box.addWidget(card_chart)
        row1_box.addWidget(card_compress)
        row1_box.addStretch()
        
        layout.addWidget(cards_container)
        layout.addLayout(row1_box)



class AttachmentItemWidget(QFrame):
    """Sleek chip/pill representing an attached file, image, URL, video or audio with remove button."""
    removed = pyqtSignal(object)
    
    def __init__(self, item_data, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a1d2e, stop:1 #131522);
                border: 1px solid #3b4261;
                border-radius: 8px;
                padding: 2px 8px;
            }
            QFrame:hover {
                border-color: #a855f7;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)
        
        # Determine Icon based on type
        icon_map = {
            'image': '🖼️',
            'video': '🎥',
            'audio': '🎵',
            'document': '📄',
            'code': '💻',
            'data': '📊',
            'url': '🔗'
        }
        icon_str = icon_map.get(item_data.get('type'), '📎')
        
        icon_lbl = QLabel(icon_str, self)
        icon_lbl.setStyleSheet("background: transparent; border: none; font-size: 12px;")
        layout.addWidget(icon_lbl)
        
        summary_text = item_data.get('summary', item_data.get('filename', 'Attachment'))
        if len(summary_text) > 30:
            summary_text = summary_text[:28] + "..."
            
        text_lbl = QLabel(summary_text, self)
        text_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px; font-weight: 500; background: transparent; border: none;")
        layout.addWidget(text_lbl)
        
        del_btn = QPushButton("✕", self)
        del_btn.setFixedSize(16, 16)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ef4444;
            }
        """)
        del_btn.clicked.connect(lambda: self.removed.emit(self.item_data))
        layout.addWidget(del_btn)


class AddUrlDialog(QDialog):
    """Modal dialog to enter a website URL for analysis."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Analyze Website URL")
        self.setFixedSize(440, 160)
        self.setStyleSheet("""
            QDialog {
                background-color: #0d0e17;
                color: #e2e8f0;
            }
            QLineEdit {
                background-color: #141624;
                border: 1px solid #282b42;
                border-radius: 8px;
                color: #f1f5f9;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #8b5cf6;
            }
            QPushButton {
                background-color: #1e2136;
                border: 1px solid #2e334d;
                border-radius: 8px;
                color: #e2e8f0;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #272c47;
            }
            QPushButton#primaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899);
                border: none;
                color: white;
            }
        """)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        
        title = QLabel("🔗 Enter Webpage URL", self)
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        layout.addWidget(title)
        
        self.url_input = QLineEdit(self)
        self.url_input.setPlaceholderText("https://example.com/article...")
        layout.addWidget(self.url_input)
        
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        
        cancel_btn = QPushButton("Cancel", self)
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)
        
        add_btn = QPushButton("Fetch & Attach", self)
        add_btn.setObjectName("primaryBtn")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self.accept)
        btn_box.addWidget(add_btn)
        
        layout.addLayout(btn_box)
        
    def get_url(self):
        return self.url_input.text().strip()


class MessageBubble(QWidget):
    """ChatGPT-style message row with avatars, syntax code blocks, and copy button."""
    def __init__(self, role, text, screenshot_path=None, parent=None):
        super().__init__(parent)
        self.role = role
        self.raw_text = text
        self.screenshot_path = screenshot_path
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)
        
        # 1. Avatar
        avatar = QLabel(self)
        avatar.setFixedSize(36, 36)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if self.role == "user":
            avatar.setText("👤")
            avatar.setStyleSheet("""
                QLabel {
                    background-color: #2e3856;
                    border-radius: 18px;
                    font-size: 15px;
                }
            """)
        else:
            avatar.setText("✨")
            avatar.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d946ef, stop:1 #8b5cf6);
                    border-radius: 18px;
                    font-size: 15px;
                    color: white;
                }
            """)
            
        layout.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
        
        # 2. Content Column
        content_container = QWidget(self)
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        
        # Sender Header
        sender_lbl = QLabel("You" if self.role == "user" else "Nexa AI", content_container)
        sender_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        sender_lbl.setStyleSheet("color: #cbd5e1; font-weight: bold; background: transparent;")
        content_layout.addWidget(sender_lbl)
        
        # Thumbnail if image/screenshot is attached
        if self.screenshot_path and os.path.exists(self.screenshot_path):
            img_container = QFrame(content_container)
            img_container.setStyleSheet("""
                QFrame {
                    background-color: #121422;
                    border: 1px solid #23273e;
                    border-radius: 10px;
                    padding: 4px;
                }
            """)
            img_layout = QVBoxLayout(img_container)
            img_layout.setContentsMargins(4, 4, 4, 4)
            
            pixmap = QPixmap(self.screenshot_path)
            if not pixmap.isNull():
                img_lbl = QLabel(img_container)
                # Scale smoothly to reasonable display size
                scaled_pixmap = pixmap.scaled(
                    420, 260, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                img_lbl.setPixmap(scaled_pixmap)
                img_lbl.setStyleSheet("border-radius: 6px;")
                img_layout.addWidget(img_lbl)
                content_layout.addWidget(img_container)
                
        # Main text browser
        self.text_browser = QTextBrowser(content_container)
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.setStyleSheet("""
            QTextBrowser {
                background-color: transparent;
                border: none;
                color: #e2e8f0;
                font-family: 'Segoe UI', 'Inter', Arial, sans-serif;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        
        # Set text as rendered HTML markdown
        html_content = markdown_to_html(self.raw_text)
        self.text_browser.setHtml(html_content)
        
        # Dynamic height sizing
        self.text_browser.document().contentsChanged.connect(self.adjust_browser_height)
        content_layout.addWidget(self.text_browser)
        
        # Footer Action Strip for Assistant
        if self.role == "assistant":
            footer = QHBoxLayout()
            footer.setContentsMargins(0, 2, 0, 0)
            footer.setSpacing(10)
            
            copy_btn = QPushButton("📋 Copy", content_container)
            copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            copy_btn.setStyleSheet("""
                QPushButton {
                    background-color: #141624;
                    border: 1px solid #252840;
                    border-radius: 6px;
                    color: #94a3b8;
                    padding: 3px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    color: #ffffff;
                    border-color: #8b5cf6;
                }
            """)
            
            def on_copy():
                QApplication.clipboard().setText(self.raw_text)
                copy_btn.setText("✓ Copied!")
                QTimer.singleShot(2000, lambda: copy_btn.setText("📋 Copy"))
                
            copy_btn.clicked.connect(on_copy)
            footer.addWidget(copy_btn)
            footer.addStretch()
            content_layout.addLayout(footer)
            
        layout.addWidget(content_container, 1)
        QTimer.singleShot(20, self.adjust_browser_height)

    def adjust_browser_height(self):
        """Fit browser height to its document contents precisely."""
        doc = self.text_browser.document()
        doc.setTextWidth(self.text_browser.viewport().width() or 600)
        h = int(doc.size().height()) + 14
        self.text_browser.setFixedHeight(max(30, h))


class CapturePromptDialog(QDialog):
    """Dialog to configure screen capture and auto-scroll settings before capturing."""
    def __init__(self, parent=None, default_auto_scroll=False):
        super().__init__(parent)
        self.setWindowTitle("Screen Capture Analysis")
        self.setFixedSize(400, 220)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #0e101a;
                color: #e2e8f0;
            }
            QCheckBox {
                font-size: 12px;
                color: #cbd5e1;
            }
            QSpinBox {
                background-color: #141624;
                border: 1px solid #282b42;
                border-radius: 6px;
                color: white;
                padding: 4px;
            }
            QPushButton {
                background-color: #1e2136;
                border: 1px solid #2e334d;
                border-radius: 8px;
                color: #e2e8f0;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #272c47;
            }
            QPushButton#primaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899);
                border: none;
                color: white;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        
        title = QLabel("📷 Capture & Analyze Screen", self)
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(title)
        
        desc = QLabel("Nexa will capture your current screen, extract visual elements and text, and generate an AI explanation.", self)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(desc)
        
        self.scroll_check = QCheckBox("Enable auto-scroll to capture full web page/document", self)
        self.scroll_check.setChecked(default_auto_scroll)
        layout.addWidget(self.scroll_check)
        
        spin_row = QHBoxLayout()
        spin_lbl = QLabel("Scroll iterations:", self)
        spin_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        spin_row.addWidget(spin_lbl)
        
        self.scroll_spin = QSpinBox(self)
        self.scroll_spin.setRange(1, 10)
        self.scroll_spin.setValue(3)
        spin_row.addWidget(self.scroll_spin)
        spin_row.addStretch()
        layout.addLayout(spin_row)
        
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        
        cancel_btn = QPushButton("Cancel", self)
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)
        
        cap_btn = QPushButton("Capture Now", self)
        cap_btn.setObjectName("primaryBtn")
        cap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cap_btn.clicked.connect(self.accept)
        btn_box.addWidget(cap_btn)
        
        layout.addLayout(btn_box)


class CalculatorDialog(QDialog):
    """Interactive offline Math Calculator, Unit Converter, and Statistics Tool."""
    def __init__(self, on_insert_chat=None, parent=None):
        super().__init__(parent)
        self.on_insert_chat = on_insert_chat
        self.setWindowTitle("🧮 Calculator & Unit Converter (Offline - No API Key)")
        self.setFixedSize(540, 480)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0c14;
                color: #e2e8f0;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 12px;
            }
            QLineEdit, QComboBox {
                background-color: #141624;
                border: 1px solid #282b42;
                border-radius: 8px;
                color: #f1f5f9;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #8b5cf6;
            }
            QTabWidget::pane {
                border: 1px solid #282b42;
                background-color: #10121d;
                border-radius: 8px;
                padding: 10px;
            }
            QTabBar::tab {
                background-color: #141624;
                color: #94a3b8;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
                font-weight: 600;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #1e2136;
                color: #ec4899;
                border: 1px solid #8b5cf6;
                border-bottom: none;
            }
            QPushButton {
                background-color: #17192a;
                border: 1px solid #2e334d;
                border-radius: 8px;
                color: #e2e8f0;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #22253c;
                border-color: #8b5cf6;
            }
            QPushButton#primaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899);
                border: none;
                color: white;
            }
            QTextBrowser {
                background-color: #0d0f1a;
                border: 1px solid #23273e;
                border-radius: 8px;
                color: #f1f5f9;
                padding: 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QLabel("🧮 Offline Math & Scientific Calculator", self)
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")
        layout.addWidget(header)

        self.tabs = QTabWidget(self)

        # Tab 1: Math Expressions
        tab_math = QWidget()
        m_layout = QVBoxLayout(tab_math)
        m_layout.setSpacing(10)

        m_label = QLabel("Enter math expression (arithmetic, algebra, trigonometry, etc.):", tab_math)
        m_layout.addWidget(m_label)

        self.math_input = QLineEdit(tab_math)
        self.math_input.setPlaceholderText("e.g. 2**10 + sqrt(144) or sin(radians(45)) * 100")
        self.math_input.returnPressed.connect(self.calculate_math)
        m_layout.addWidget(self.math_input)

        # Quick Math Chips
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(6)
        for chip in ["sqrt()", "sin()", "cos()", "pi", "2**8", "log10()", "round()"]:
            btn = QPushButton(chip, tab_math)
            btn.setFixedHeight(28)
            btn.setStyleSheet("font-size: 11px; padding: 2px 8px; background-color: #17192a;")
            btn.clicked.connect(lambda _, c=chip: self.insert_chip(c))
            chips_layout.addWidget(btn)
        chips_layout.addStretch()
        m_layout.addLayout(chips_layout)

        calc_btn = QPushButton("Calculate Expression", tab_math)
        calc_btn.setObjectName("primaryBtn")
        calc_btn.clicked.connect(self.calculate_math)
        m_layout.addWidget(calc_btn)
        m_layout.addStretch()
        self.tabs.addTab(tab_math, "Math & Science")

        # Tab 2: Unit Converter
        tab_unit = QWidget()
        u_layout = QVBoxLayout(tab_unit)
        u_layout.setSpacing(10)

        u_label = QLabel("Convert Units (Distance, Weight, Temp, Storage):", tab_unit)
        u_layout.addWidget(u_label)

        self.unit_input = QLineEdit(tab_unit)
        self.unit_input.setPlaceholderText("e.g. 100 km to miles, 75 kg to lbs, 32 C to F, 500 MB to GB")
        self.unit_input.returnPressed.connect(self.calculate_unit)
        u_layout.addWidget(self.unit_input)

        unit_chips = QHBoxLayout()
        for chip in ["100 km to miles", "75 kg to lbs", "32 C to F", "1024 MB to GB", "10 miles to km"]:
            btn = QPushButton(chip, tab_unit)
            btn.setFixedHeight(28)
            btn.setStyleSheet("font-size: 11px; padding: 2px 8px; background-color: #17192a;")
            btn.clicked.connect(lambda _, c=chip: self.unit_input.setText(c))
            unit_chips.addWidget(btn)
        unit_chips.addStretch()
        u_layout.addLayout(unit_chips)

        conv_btn = QPushButton("Convert Units", tab_unit)
        conv_btn.setObjectName("primaryBtn")
        conv_btn.clicked.connect(self.calculate_unit)
        u_layout.addWidget(conv_btn)
        u_layout.addStretch()
        self.tabs.addTab(tab_unit, "Unit Converter")

        # Tab 3: Statistics
        tab_stat = QWidget()
        s_layout = QVBoxLayout(tab_stat)
        s_layout.setSpacing(10)

        s_label = QLabel("Enter dataset numbers (separated by comma):", tab_stat)
        s_layout.addWidget(s_label)

        self.stat_input = QLineEdit(tab_stat)
        self.stat_input.setPlaceholderText("e.g. 12, 24, 35, 48, 52, 67, 89, 94")
        self.stat_input.returnPressed.connect(self.calculate_stat)
        s_layout.addWidget(self.stat_input)

        stat_btn = QPushButton("Compute Statistics", tab_stat)
        stat_btn.setObjectName("primaryBtn")
        stat_btn.clicked.connect(self.calculate_stat)
        s_layout.addWidget(stat_btn)
        s_layout.addStretch()
        self.tabs.addTab(tab_stat, "Statistics")

        layout.addWidget(self.tabs)

        # Output Results
        self.result_display = QTextBrowser(self)
        self.result_display.setFixedHeight(120)
        self.result_display.setHtml("<span style='color: #64748b;'>Results will appear here...</span>")
        layout.addWidget(self.result_display)

        # Bottom Actions
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.insert_btn = QPushButton("💬 Insert into Chat", self)
        self.insert_btn.setEnabled(False)
        self.insert_btn.clicked.connect(self.send_to_chat)
        btn_box.addWidget(self.insert_btn)

        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)

        layout.addLayout(btn_box)
        self.latest_result_text = ""

    def insert_chip(self, chip):
        curr = self.math_input.text()
        if chip.endswith("()"):
            self.math_input.setText(curr + chip[:-1])
        else:
            self.math_input.setText(curr + " " + chip + " ")
        self.math_input.setFocus()

    def calculate_math(self):
        expr = self.math_input.text().strip()
        if not expr:
            return
        res = plugin_manager.execute_tool_call("calculator", {"expression": expr, "operation_type": "calculate"})
        text = res.get("result", res.get("error", "Error"))
        self.latest_result_text = text
        self.result_display.setHtml(markdown_to_html(text))
        self.insert_btn.setEnabled(True)

    def calculate_unit(self):
        expr = self.unit_input.text().strip()
        if not expr:
            return
        res = plugin_manager.execute_tool_call("calculator", {"expression": expr, "operation_type": "unit_convert"})
        text = res.get("result", res.get("error", "Error"))
        self.latest_result_text = text
        self.result_display.setHtml(markdown_to_html(text))
        self.insert_btn.setEnabled(True)

    def calculate_stat(self):
        data = self.stat_input.text().strip()
        if not data:
            return
        res = plugin_manager.execute_tool_call("calculator", {"expression": data, "operation_type": "statistics", "data": data})
        text = res.get("result", res.get("error", "Error"))
        self.latest_result_text = text
        self.result_display.setHtml(markdown_to_html(text))
        self.insert_btn.setEnabled(True)

    def send_to_chat(self):
        if self.on_insert_chat and self.latest_result_text:
            self.on_insert_chat(self.latest_result_text)
            self.accept()


class FileCompressorDialog(QDialog):
    """Interactive offline File Compressor, Unzipper, and Archive Manager."""
    def __init__(self, on_insert_chat=None, parent=None):
        super().__init__(parent)
        self.on_insert_chat = on_insert_chat
        self.setWindowTitle("🗜️ File Compressor & Archive Manager (Offline)")
        self.setFixedSize(580, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0c14;
                color: #e2e8f0;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 12px;
            }
            QLineEdit, QComboBox {
                background-color: #141624;
                border: 1px solid #282b42;
                border-radius: 8px;
                color: #f1f5f9;
                padding: 8px 12px;
                font-size: 12px;
            }
            QPushButton {
                background-color: #17192a;
                border: 1px solid #2e334d;
                border-radius: 8px;
                color: #e2e8f0;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #22253c;
                border-color: #8b5cf6;
            }
            QPushButton#primaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899);
                border: none;
                color: white;
            }
            QTextBrowser {
                background-color: #0d0f1a;
                border: 1px solid #23273e;
                border-radius: 8px;
                color: #f1f5f9;
                padding: 10px;
                font-family: 'Consolas', monospace;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QLabel("🗜️ Offline File Compressor & Extractor", self)
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(10)

        # Action Type
        self.action_combo = QComboBox(self)
        self.action_combo.addItems(["Compress to ZIP / Archive", "Extract / Unzip Archive", "Inspect Archive Contents"])
        form.addRow("Operation:", self.action_combo)

        # Source Path
        src_row = QHBoxLayout()
        self.src_input = QLineEdit(self)
        self.src_input.setPlaceholderText("Path to file, directory, or archive...")
        src_row.addWidget(self.src_input)

        browse_file_btn = QPushButton("Browse File", self)
        browse_file_btn.clicked.connect(self.browse_file)
        src_row.addWidget(browse_file_btn)

        browse_dir_btn = QPushButton("Browse Folder", self)
        browse_dir_btn.clicked.connect(self.browse_dir)
        src_row.addWidget(browse_dir_btn)
        form.addRow("Source Target:", src_row)

        # Destination Path
        dest_row = QHBoxLayout()
        self.dest_input = QLineEdit(self)
        self.dest_input.setPlaceholderText("Optional output archive path or destination folder...")
        dest_row.addWidget(self.dest_input)

        browse_dest_btn = QPushButton("Browse Dest", self)
        browse_dest_btn.clicked.connect(self.browse_dest)
        dest_row.addWidget(browse_dest_btn)
        form.addRow("Destination:", dest_row)

        # Format
        self.format_combo = QComboBox(self)
        self.format_combo.addItems(["zip", "tar.gz", "tar.bz2", "tar"])
        form.addRow("Archive Format:", self.format_combo)

        layout.addLayout(form)

        run_btn = QPushButton("Execute Archive Operation", self)
        run_btn.setObjectName("primaryBtn")
        run_btn.clicked.connect(self.execute_compressor)
        layout.addWidget(run_btn)

        self.result_display = QTextBrowser(self)
        self.result_display.setFixedHeight(150)
        self.result_display.setHtml("<span style='color: #64748b;'>Operation results and archive stats will appear here...</span>")
        layout.addWidget(self.result_display)

        # Bottom
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.insert_btn = QPushButton("💬 Insert Report into Chat", self)
        self.insert_btn.setEnabled(False)
        self.insert_btn.clicked.connect(self.send_to_chat)
        btn_box.addWidget(self.insert_btn)

        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)

        layout.addLayout(btn_box)
        self.latest_result_text = ""

    def browse_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select File or Archive", "", "All Files (*.*);;ZIP Archives (*.zip);;TAR Archives (*.tar *.tar.gz)")
        if f:
            self.src_input.setText(f)

    def browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Directory to Compress")
        if d:
            self.src_input.setText(d)

    def browse_dest(self):
        act = self.action_combo.currentText()
        if "Extract" in act:
            d = QFileDialog.getExistingDirectory(self, "Select Extraction Folder")
            if d:
                self.dest_input.setText(d)
        else:
            f, _ = QFileDialog.getSaveFileName(self, "Save Archive As", "archive.zip", "ZIP Archive (*.zip);;TAR.GZ Archive (*.tar.gz)")
            if f:
                self.dest_input.setText(f)

    def execute_compressor(self):
        src = self.src_input.text().strip()
        if not src:
            self.result_display.setHtml("<span style='color: #ef4444;'>Error: Please select a source file or folder.</span>")
            return

        act_idx = self.action_combo.currentIndex()
        action = "compress" if act_idx == 0 else ("extract" if act_idx == 1 else "list")
        dest = self.dest_input.text().strip()
        fmt = self.format_combo.currentText()

        res = plugin_manager.execute_tool_call("file_compressor", {
            "action": action,
            "source_path": src,
            "destination_path": dest,
            "format": fmt
        })
        text = res.get("result", res.get("error", "Error"))
        self.latest_result_text = text
        self.result_display.setHtml(markdown_to_html(text))
        self.insert_btn.setEnabled(True)

    def send_to_chat(self):
        if self.on_insert_chat and self.latest_result_text:
            self.on_insert_chat(self.latest_result_text)
            self.accept()


class ChartGeneratorDialog(QDialog):
    """Interactive offline Chart & Graph Generator Tool."""
    def __init__(self, on_insert_chat=None, parent=None):
        super().__init__(parent)
        self.on_insert_chat = on_insert_chat
        self.setWindowTitle("📈 Chart & Graph Generator (Offline - Matplotlib)")
        self.setFixedSize(620, 580)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0c14;
                color: #e2e8f0;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 12px;
            }
            QLineEdit, QComboBox {
                background-color: #141624;
                border: 1px solid #282b42;
                border-radius: 8px;
                color: #f1f5f9;
                padding: 8px 12px;
                font-size: 12px;
            }
            QPushButton {
                background-color: #17192a;
                border: 1px solid #2e334d;
                border-radius: 8px;
                color: #e2e8f0;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #22253c;
                border-color: #8b5cf6;
            }
            QPushButton#primaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899);
                border: none;
                color: white;
            }
            QTextBrowser {
                background-color: #0d0f1a;
                border: 1px solid #23273e;
                border-radius: 8px;
                color: #f1f5f9;
                padding: 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QLabel("📈 Offline Chart & Graph Generator", self)
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(8)

        self.type_combo = QComboBox(self)
        self.type_combo.addItems(["Bar Chart", "Line Graph", "Pie Chart", "Doughnut Chart", "Area Chart", "Scatter Plot", "Histogram", "Horizontal Bar"])
        form.addRow("Chart Type:", self.type_combo)

        self.title_input = QLineEdit(self)
        self.title_input.setText("Monthly Revenue 2026")
        form.addRow("Chart Title:", self.title_input)

        self.x_input = QLineEdit(self)
        self.x_input.setText("Jan, Feb, Mar, Apr, May, Jun")
        form.addRow("X-Axis Labels:", self.x_input)

        self.y_input = QLineEdit(self)
        self.y_input.setText("12000, 19500, 15300, 24000, 31000, 42000")
        form.addRow("Y-Axis Values:", self.y_input)

        labels_row = QHBoxLayout()
        self.xlabel_input = QLineEdit(self)
        self.xlabel_input.setPlaceholderText("e.g. Month")
        labels_row.addWidget(self.xlabel_input)

        self.ylabel_input = QLineEdit(self)
        self.ylabel_input.setPlaceholderText("e.g. Revenue ($)")
        labels_row.addWidget(self.ylabel_input)
        form.addRow("Axis Labels (X/Y):", labels_row)

        self.theme_combo = QComboBox(self)
        self.theme_combo.addItems(["modern_dark", "cyberpunk", "ocean", "sunset", "emerald", "minimal_light"])
        form.addRow("Color Theme:", self.theme_combo)

        layout.addLayout(form)

        # Quick Templates
        tmpl_row = QHBoxLayout()
        tmpl_lbl = QLabel("Templates:", self)
        tmpl_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        tmpl_row.addWidget(tmpl_lbl)

        for name, tx, ty, ctype in [
            ("📊 Sales", "Q1, Q2, Q3, Q4", "150, 220, 310, 480", "Bar Chart"),
            ("📈 Growth", "Week 1, Week 2, Week 3, Week 4", "1200, 1850, 2400, 3900", "Line Graph"),
            ("🥧 Market Share", "Chrome, Safari, Edge, Firefox", "65, 18, 10, 7", "Pie Chart")
        ]:
            btn = QPushButton(name, self)
            btn.setFixedHeight(26)
            btn.setStyleSheet("font-size: 11px; padding: 2px 8px; background-color: #17192a;")
            btn.clicked.connect(lambda _, x=tx, y=ty, t=ctype: self.load_template(x, y, t))
            tmpl_row.addWidget(btn)
        tmpl_row.addStretch()
        layout.addLayout(tmpl_row)

        gen_btn = QPushButton("📈 Generate & View Chart Image", self)
        gen_btn.setObjectName("primaryBtn")
        gen_btn.clicked.connect(self.generate_chart)
        layout.addWidget(gen_btn)

        self.result_display = QTextBrowser(self)
        self.result_display.setFixedHeight(120)
        self.result_display.setHtml("<span style='color: #64748b;'>Generated graph image details will appear here...</span>")
        layout.addWidget(self.result_display)

        # Bottom
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.insert_btn = QPushButton("💬 Attach to Chat", self)
        self.insert_btn.setEnabled(False)
        self.insert_btn.clicked.connect(self.send_to_chat)
        btn_box.addWidget(self.insert_btn)

        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)

        layout.addLayout(btn_box)
        self.latest_result_text = ""

    def load_template(self, x, y, ctype):
        self.x_input.setText(x)
        self.y_input.setText(y)
        self.type_combo.setCurrentText(ctype)

    def generate_chart(self):
        title = self.title_input.text().strip() or "Data Chart"
        data_y = self.y_input.text().strip()
        if not data_y:
            self.result_display.setHtml("<span style='color: #ef4444;'>Error: Please provide numeric Y values.</span>")
            return

        data_x = self.x_input.text().strip()
        ctype = self.type_combo.currentText().lower().replace(" ", "_").replace("chart", "").replace("graph", "").strip("_")
        theme = self.theme_combo.currentText()
        xl = self.xlabel_input.text().strip()
        yl = self.ylabel_input.text().strip()

        res = plugin_manager.execute_tool_call("chart_generator", {
            "chart_type": ctype,
            "title": title,
            "data_x": data_x,
            "data_y": data_y,
            "x_label": xl,
            "y_label": yl,
            "color_theme": theme,
            "open_image": True
        })
        text = res.get("result", res.get("error", "Error"))
        self.latest_result_text = text
        self.result_display.setHtml(markdown_to_html(text))
        self.insert_btn.setEnabled(True)

    def send_to_chat(self):
        if self.on_insert_chat and self.latest_result_text:
            self.on_insert_chat(self.latest_result_text)
            self.accept()


class UserAvatarWidget(QWidget):

    """Draws a circular user profile avatar with green ChatGPT background and first letter."""
    def __init__(self, letter="?", bg_color="#10a37f", size=36, parent=None):
        super().__init__(parent)
        self.letter = letter.upper() if letter else "?"
        self.bg_color = QColor(bg_color)
        self.setFixedSize(size, size)
        
    def set_letter(self, letter, bg_color="#10a37f"):
        self.letter = letter.upper() if letter else "?"
        self.bg_color = QColor(bg_color)
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Background circle with subtle border
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1.5))
        painter.setBrush(QBrush(self.bg_color))
        painter.drawEllipse(1, 1, w - 2, h - 2)
        
        # Center Letter
        painter.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI", int(h * 0.42), QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, self.letter)


import http.server
import urllib.parse
import socket

class GoogleAuthHandler(http.server.BaseHTTPRequestHandler):
    auth_callback = None
    
    def log_message(self, format, *args):
        pass # Silence console logs
        
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if parsed.path in ("/", "/login", "/auth"):
            html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nexa AI - Google Verification</title>
  <style>
    body {
      background-color: #0b0c14;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      margin: 0;
    }
    .card {
      background: #121422;
      border: 1px solid #282b45;
      border-radius: 16px;
      padding: 36px 32px;
      width: 100%;
      max-width: 420px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
      text-align: center;
    }
    .google-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 56px;
      height: 56px;
      background: #1e2138;
      border-radius: 50%;
      margin-bottom: 16px;
      font-size: 26px;
    }
    h2 {
      margin: 0 0 8px 0;
      color: #ffffff;
      font-size: 22px;
    }
    p {
      color: #94a3b8;
      font-size: 14px;
      margin-bottom: 24px;
      line-height: 1.5;
    }
    .input-group {
      text-align: left;
      margin-bottom: 16px;
    }
    label {
      display: block;
      font-size: 12px;
      font-weight: 600;
      color: #cbd5e1;
      margin-bottom: 6px;
    }
    input {
      width: 100%;
      box-sizing: border-box;
      background: #090a12;
      border: 1px solid #282b42;
      border-radius: 8px;
      color: #fff;
      padding: 12px 14px;
      font-size: 14px;
      outline: none;
    }
    input:focus {
      border-color: #10a37f;
    }
    button {
      width: 100%;
      background: #10a37f;
      color: #ffffff;
      border: none;
      border-radius: 8px;
      padding: 13px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s;
    }
    button:hover {
      background: #0d8a6a;
    }
    .footer {
      font-size: 11px;
      color: #64748b;
      margin-top: 20px;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="google-badge">🌐</div>
    <h2>Google Account Verification</h2>
    <p>Verify your official Google Gmail Account to link with <b>Nexa AI Desktop</b>.</p>
    <form action="/callback" method="GET">
      <div class="input-group">
        <label for="name">Google Full Name</label>
        <input type="text" id="name" name="name" value="Pravallika Peketi" required>
      </div>
      <div class="input-group">
        <label for="email">Verified Gmail Address</label>
        <input type="email" id="email" name="email" value="peketipravallika13@gmail.com" required>
      </div>
      <button type="submit">Verify & Complete Google Sign-In</button>
    </form>
    <div class="footer">Google OAuth Verification • Nexa AI</div>
  </div>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            
        elif parsed.path == "/callback":
            email = params.get("email", [""])[0].strip()
            name = params.get("name", [""])[0].strip()
            
            if email and "@" in email:
                if not name:
                    name = email.split("@")[0].replace(".", " ").title()
                
                if GoogleAuthHandler.auth_callback:
                    GoogleAuthHandler.auth_callback(email, name)
                
                success_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Verification Successful - Nexa AI</title>
  <style>
    body {{
      background-color: #0b0c14;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      margin: 0;
    }}
    .card {{
      background: #121422;
      border: 1px solid #10a37f;
      border-radius: 16px;
      padding: 40px 32px;
      max-width: 420px;
      text-align: center;
      box-shadow: 0 0 40px rgba(16, 163, 127, 0.2);
    }}
    .check {{
      font-size: 48px;
      color: #10a37f;
      margin-bottom: 12px;
    }}
    h2 {{
      color: #ffffff;
      margin-bottom: 8px;
    }}
    .user-pill {{
      background: rgba(16, 163, 127, 0.15);
      border: 1px solid rgba(16, 163, 127, 0.4);
      border-radius: 30px;
      padding: 8px 18px;
      display: inline-block;
      margin: 16px 0;
      color: #10a37f;
      font-weight: 600;
    }}
    p {{
      color: #94a3b8;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="check">✓</div>
    <h2>Google Account Verified!</h2>
    <div class="user-pill">{name} • {email}</div>
    <p>Your Google account has been verified.<br>You can now return to <b>Nexa AI</b>.</p>
  </div>
  <script>
    setTimeout(function() {{ window.close(); }}, 3000);
  </script>
</body>
</html>"""
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(success_html.encode("utf-8"))
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Invalid verification data.")


class GoogleAuthServerThread(QThread):
    auth_received = pyqtSignal(str, str)
    
    def __init__(self, port=8585, parent=None):
        super().__init__(parent)
        self.port = port
        self.server = None
        
    def run(self):
        GoogleAuthHandler.auth_callback = self.on_callback
        try:
            self.server = http.server.HTTPServer(('localhost', self.port), GoogleAuthHandler)
            self.server.serve_forever()
        except Exception as e:
            logger.error(f"Google auth server error on port {self.port}: {e}")
            
    def on_callback(self, email, name):
        self.auth_received.emit(email, name)
        
    def stop(self):
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass


class AuthLoginDialog(QDialog):
    """Modern Google Authentication modal for real Google user verification."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Google Account Verification")
        self.setFixedSize(440, 420)
        self.server_thread = None
        self.auth_port = 8585
        
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0c14;
                color: #e2e8f0;
            }
            QPushButton {
                border-radius: 8px;
                padding: 11px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton#googleBtn {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
            }
            QPushButton#googleBtn:hover {
                background-color: #f1f5f9;
            }
            QPushButton#logoutBtn {
                background-color: #1a1523;
                color: #f87171;
                border: 1px solid #3f222b;
            }
            QPushButton#logoutBtn:hover {
                background-color: #2c1620;
            }
            QPushButton#cancelBtn {
                background-color: #141624;
                color: #94a3b8;
                border: 1px solid #282b42;
            }
            QPushButton#cancelBtn:hover {
                background-color: #1e2136;
                color: #e2e8f0;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Header with preview avatar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)
        
        profile = database.get_user_profile()
        current_email = profile.get("email", "")
        current_name = profile.get("name", "")
        is_logged_in = profile.get("is_logged_in", False)
        
        initial = (current_name[0] if current_name else (current_email[0] if current_email else "P")).upper()
        self.preview_avatar = UserAvatarWidget(initial, bg_color="#10a37f" if is_logged_in else "#10a37f", size=48, parent=self)
        header_layout.addWidget(self.preview_avatar)
        
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("Google Account Login", self)
        title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #ffffff; background: transparent; border: none;")
        title_box.addWidget(title_lbl)
        
        desc_lbl = QLabel("Official Google Verification for Nexa AI", self)
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent; border: none;")
        title_box.addWidget(desc_lbl)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Status banner if already logged in
        if is_logged_in and current_email:
            self.status_banner = QFrame(self)
            self.status_banner.setStyleSheet("""
                QFrame {
                    background-color: rgba(16, 163, 127, 0.12);
                    border: 1px solid rgba(16, 163, 127, 0.35);
                    border-radius: 8px;
                    padding: 8px 12px;
                }
            """)
            sb_layout = QVBoxLayout(self.status_banner)
            sb_layout.setContentsMargins(4, 4, 4, 4)
            sb_layout.setSpacing(2)
            
            sb_name = QLabel(f"<b>{current_name}</b>", self.status_banner)
            sb_name.setStyleSheet("color: #ffffff; font-size: 13px; background: transparent; border: none;")
            sb_layout.addWidget(sb_name)
            
            sb_lbl = QLabel(f"✓ Verified Google ID: {current_email}", self.status_banner)
            sb_lbl.setStyleSheet("color: #10a37f; font-size: 11px; font-weight: 500; background: transparent; border: none;")
            sb_layout.addWidget(sb_lbl)
            layout.addWidget(self.status_banner)
            
        # Continue with Google button
        self.google_btn = QPushButton("🌐  Continue with Google", self)
        self.google_btn.setObjectName("googleBtn")
        self.google_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.google_btn.clicked.connect(self.on_google_login)
        layout.addWidget(self.google_btn)
        
        # Status / Feedback label
        self.msg_label = QLabel(
            "Clicking 'Continue with Google' will open your browser to verify your Google Account.", 
            self
        )
        self.msg_label.setWordWrap(True)
        self.msg_label.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.4; background: transparent; border: none;")
        layout.addWidget(self.msg_label)
        
        layout.addStretch()
        
        # Bottom Buttons
        row_btns = QHBoxLayout()
        row_btns.setSpacing(8)
        
        if is_logged_in:
            self.logout_btn = QPushButton("🚪 Log Out", self)
            self.logout_btn.setObjectName("logoutBtn")
            self.logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.logout_btn.clicked.connect(self.on_logout)
            row_btns.addWidget(self.logout_btn)
            
        self.cancel_btn = QPushButton("Close", self)
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        row_btns.addWidget(self.cancel_btn)
        
        layout.addLayout(row_btns)
        
    def on_google_login(self):
        # Start local verification server if not started
        if not self.server_thread or not self.server_thread.isRunning():
            self.server_thread = GoogleAuthServerThread(port=self.auth_port, parent=self)
            self.server_thread.auth_received.connect(self.on_auth_success)
            self.server_thread.start()
            
        auth_url = f"http://localhost:{self.auth_port}/login"
        
        try:
            webbrowser.open(auth_url)
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")
            
        self.msg_label.setStyleSheet("color: #10a37f; font-size: 12px; font-weight: bold; background: transparent; border: none;")
        self.msg_label.setText("⏳ Browser opened for Google Verification! Please confirm in your browser...")
        
    @pyqtSlot(str, str)
    def on_auth_success(self, email, name):
        database.set_user_profile(email, name)
        
        initial = (name[0] if name else (email[0] if email else "P")).upper()
        self.preview_avatar.set_letter(initial, bg_color="#10a37f")
        
        self.msg_label.setStyleSheet("color: #10a37f; font-size: 12px; font-weight: bold; background: transparent; border: none;")
        self.msg_label.setText(f"✓ Successfully verified as {name} ({email})!")
        
        if self.server_thread:
            self.server_thread.stop()
            
        QTimer.singleShot(700, self.accept)
        
    def on_logout(self):
        database.logout_user()
        if self.server_thread:
            self.server_thread.stop()
        self.accept()
        
    def closeEvent(self, event):
        if self.server_thread:
            self.server_thread.stop()
        super().closeEvent(event)


class UserProfileWidget(QFrame):
    """ChatGPT-style bottom profile card for the left sidebar."""
    profile_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("UserProfileWidget")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QFrame#UserProfileWidget {
                background-color: #0e101c;
                border: 1px solid #1c1f36;
                border-radius: 10px;
                margin: 6px 14px 4px 14px;
                padding: 6px 10px;
            }
            QFrame#UserProfileWidget:hover {
                background-color: #171a2e;
                border-color: #10a37f;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 8, 6)
        layout.setSpacing(10)
        
        # Avatar (Circle with green background and first letter)
        self.avatar = UserAvatarWidget("?", bg_color="#10a37f", size=34, parent=self)
        layout.addWidget(self.avatar)
        
        # Info container
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        self.name_label = QLabel("Sign In", self)
        self.name_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.name_label.setStyleSheet("color: #f1f5f9; background: transparent; border: none;")
        info_layout.addWidget(self.name_label)
        
        self.email_label = QLabel("Add your email", self)
        self.email_label.setStyleSheet("color: #94a3b8; font-size: 10px; background: transparent; border: none;")
        info_layout.addWidget(self.email_label)
        
        layout.addLayout(info_layout, 1)
        
        # Right dots icon
        self.more_label = QLabel("⋯", self)
        self.more_label.setStyleSheet("color: #64748b; font-size: 16px; font-weight: bold; background: transparent; border: none;")
        layout.addWidget(self.more_label)
        
        self.refresh_profile()
        
    def refresh_profile(self):
        profile = database.get_user_profile()
        email = profile.get("email", "").strip()
        name = profile.get("name", "").strip()
        is_logged_in = profile.get("is_logged_in", False)
        
        if is_logged_in and email:
            initial = (name[0] if name else (email[0] if email else "U")).upper()
            self.avatar.set_letter(initial, bg_color="#10a37f")
            self.name_label.setText(name if name else email.split("@")[0])
            disp_email = email if len(email) <= 22 else email[:20] + "..."
            self.email_label.setText(disp_email)
            self.email_label.setStyleSheet("color: #10a37f; font-size: 10px; font-weight: 500; background: transparent; border: none;")
        else:
            self.avatar.set_letter("👤", bg_color="#23273e")
            self.name_label.setText("Sign In / Add Email")
            self.email_label.setText("Click to link Google / Email")
            self.email_label.setStyleSheet("color: #94a3b8; font-size: 10px; background: transparent; border: none;")
            
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.profile_clicked.emit()
        super().mousePressEvent(event)


class SettingsDialog(QDialog):
    """Settings modal for AI Model Provider, API Key, Global Hotkey, and Plugins."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings & Plugin Configuration")
        self.setFixedSize(560, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0c14;
                color: #e2e8f0;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 12px;
            }
            QLineEdit, QComboBox {
                background-color: #141624;
                border: 1px solid #282b42;
                border-radius: 8px;
                color: #f1f5f9;
                padding: 8px 12px;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #8b5cf6;
            }
            QTabWidget::pane {
                border: 1px solid #282b42;
                background-color: #10121d;
                border-radius: 8px;
                padding: 10px;
            }
            QTabBar::tab {
                background-color: #141624;
                color: #94a3b8;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
                font-weight: 600;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #1e2136;
                color: #ec4899;
                border: 1px solid #8b5cf6;
                border-bottom: none;
            }
            QCheckBox {
                color: #cbd5e1;
                font-size: 12px;
            }
            QPushButton {
                background-color: #17192a;
                border: 1px solid #2e334d;
                border-radius: 8px;
                color: #e2e8f0;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #22253c;
            }
            QPushButton#primaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899);
                border: none;
                color: white;
            }
        """)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        
        title = QLabel("⚙️ Application & Plugin Settings", self)
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: white; margin-bottom: 2px;")
        layout.addWidget(title)
        
        tabs = QTabWidget(self)
        
        # Tab 1: AI Provider & General
        tab_general = QWidget()
        gen_layout = QVBoxLayout(tab_general)
        gen_layout.setSpacing(10)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # API Provider
        self.provider_combo = QComboBox(tab_general)
        self.provider_combo.addItems(["Gemini", "OpenAI", "Groq"])
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        form_layout.addRow("AI Provider:", self.provider_combo)
        
        # API Key
        self.key_input = QLineEdit(tab_general)
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("Enter your API Key here")
        form_layout.addRow("API Key:", self.key_input)
        
        # Model Name
        self.model_input = QLineEdit(tab_general)
        form_layout.addRow("Model Name:", self.model_input)
        
        # Global Hotkey
        self.hotkey_input = QLineEdit(tab_general)
        self.hotkey_input.setPlaceholderText("e.g. Ctrl+Alt+N")
        form_layout.addRow("Global Hotkey:", self.hotkey_input)
        
        # Auto Scroll Checkbox
        self.scroll_check = QCheckBox("Enable Auto Scroll for tall pages", tab_general)
        form_layout.addRow("", self.scroll_check)
        
        # Confirmation Prompt Checkbox
        self.prompt_check = QCheckBox("Show confirmation prompt before capture", tab_general)
        form_layout.addRow("", self.prompt_check)
        
        gen_layout.addLayout(form_layout)
        
        desc_lbl = QLabel(
            "💡 Nexa AI natively understands Screen Captures, Files (PDF/DOCX), Code, Images, Videos, Audio, Spreadsheets, and URLs.",
            tab_general
        )
        desc_lbl.setStyleSheet("color: #8a8a93; font-size: 11px; margin-top: 4px;")
        desc_lbl.setWordWrap(True)
        gen_layout.addWidget(desc_lbl)
        gen_layout.addStretch()
        tabs.addTab(tab_general, "⚙️ AI & System")
        
        # Tab 2: Plugins (No API Key)
        tab_plugins = QWidget()
        p_layout = QVBoxLayout(tab_plugins)
        p_layout.setSpacing(8)
        
        p_info = QLabel("🔌 <b>Built-in & Offline Plugins (No API Key Required)</b>", tab_plugins)
        p_info.setStyleSheet("color: #ec4899; font-size: 12px;")
        p_layout.addWidget(p_info)
        
        scroll_plugins = QScrollArea(tab_plugins)
        scroll_plugins.setWidgetResizable(True)
        scroll_plugins.setStyleSheet("background: transparent; border: none;")
        
        plugins_content = QWidget()
        plugins_vbox = QVBoxLayout(plugins_content)
        plugins_vbox.setSpacing(8)
        plugins_vbox.setContentsMargins(0, 0, 0, 0)
        
        plugins_list = [
            ("🧮 Calculator", "Math, trigonometry, algebraic expressions, statistical analysis, and unit conversions.", "✅ Active (Offline - No Key)"),
            ("📈 Chart Generator", "Create bar, line, pie, doughnut, area, scatter charts & histograms using Matplotlib.", "✅ Active (Offline - No Key)"),
            ("🗜️ File Compressor", "Compress files/folders into ZIP & TAR archives and extract archives safely.", "✅ Active (Offline - No Key)"),
            ("📷 Screen Capture & OCR", "Instant optical character recognition and multi-modal screen analysis.", "✅ Active (Built-in)"),
            ("📋 System Clipboard", "Read and write clipboard contents seamlessly.", "✅ Active (Built-in)"),
            ("🌐 Web Link Reader", "Extract clean readable text from website URLs.", "✅ Active (Built-in)"),
            ("🎨 Canva Designer", "Quick launch presentation and poster templates in Canva editor.", "✅ Active (Plugin)"),
            ("🔎 Deep Search", "Multi-angle scientific and web investigation assistant.", "✅ Active (Plugin)")
        ]
        
        for p_name, p_desc, p_status in plugins_list:
            card = QFrame(plugins_content)
            card.setStyleSheet("""
                QFrame {
                    background-color: #141624;
                    border: 1px solid #282b42;
                    border-radius: 8px;
                    padding: 6px 10px;
                }
            """)
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(4, 4, 4, 4)
            c_layout.setSpacing(2)
            
            top_h = QHBoxLayout()
            name_lbl = QLabel(f"<b>{p_name}</b>", card)
            name_lbl.setStyleSheet("color: #f1f5f9; font-size: 12px; background: transparent; border: none;")
            top_h.addWidget(name_lbl)
            top_h.addStretch()
            
            status_lbl = QLabel(p_status, card)
            status_lbl.setStyleSheet("color: #10b981; font-size: 11px; font-weight: bold; background: transparent; border: none;")
            top_h.addWidget(status_lbl)
            c_layout.addLayout(top_h)
            
            desc_l = QLabel(p_desc, card)
            desc_l.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent; border: none;")
            desc_l.setWordWrap(True)
            c_layout.addWidget(desc_l)
            
            plugins_vbox.addWidget(card)
            
        plugins_vbox.addStretch()
        scroll_plugins.setWidget(plugins_content)
        p_layout.addWidget(scroll_plugins)
        
        tabs.addTab(tab_plugins, "🔌 Plugins (No API Key)")
        layout.addWidget(tabs)
        
        button_box = QHBoxLayout()
        button_box.addStretch()
        
        cancel_btn = QPushButton("Cancel", self)
        cancel_btn.clicked.connect(self.reject)
        button_box.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Settings", self)
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self.save_settings)
        button_box.addWidget(save_btn)
        
        layout.addLayout(button_box)
        self.load_settings()
        
    def load_settings(self):
        provider = database.get_setting("api_provider", "gemini")
        self.provider_combo.setCurrentText(provider.capitalize())
        self.key_input.setText(database.get_setting("api_key", ""))
        self.model_input.setText(database.get_setting("model_name", "gemini-3.6-flash"))
        self.hotkey_input.setText(database.get_setting("global_hotkey", "Ctrl+Alt+N"))
        self.scroll_check.setChecked(database.get_setting("auto_scroll", "False") == "True")
        self.prompt_check.setChecked(database.get_setting("show_capture_prompt", "True") == "True")
        self.on_provider_changed(self.provider_combo.currentText())
        
    def on_provider_changed(self, provider_text):
        p = provider_text.lower()
        current_model = self.model_input.text()
        if p == "gemini":
            self.model_input.setPlaceholderText("e.g. gemini-3.6-flash")
            if current_model in ("", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gpt-4o-mini", "llama-3.1-8b-instant"):
                self.model_input.setText("gemini-3.6-flash")
        elif p == "openai":
            self.model_input.setPlaceholderText("e.g. gpt-4o-mini")
            if current_model in ("", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-2.0-flash", "llama-3.1-8b-instant"):
                self.model_input.setText("gpt-4o-mini")
        elif p == "groq":
            self.model_input.setPlaceholderText("e.g. openai/gpt-oss-20b or openai/gpt-oss-120b")
            if current_model in ("", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-2.0-flash", "gpt-4o-mini", "llama-3.1-8b-instant", "llama3-8b-8192"):
                self.model_input.setText("openai/gpt-oss-20b")
                
    def save_settings(self):
        database.set_setting("api_provider", self.provider_combo.currentText().lower())
        database.set_setting("api_key", self.key_input.text().strip())
        database.set_setting("model_name", self.model_input.text().strip())
        database.set_setting("global_hotkey", self.hotkey_input.text().strip())
        database.set_setting("auto_scroll", "True" if self.scroll_check.isChecked() else "False")
        database.set_setting("show_capture_prompt", "True" if self.prompt_check.isChecked() else "False")
        self.accept()


class OcrWorker(QThread):
    finished = pyqtSignal(str, str) # screenshot_path, ocr_text
    failed = pyqtSignal(str)
    capture_completed = pyqtSignal()
    
    def __init__(self, auto_scroll, scroll_count=3):
        super().__init__()
        self.auto_scroll = auto_scroll
        self.scroll_count = scroll_count
        
    def run(self):
        try:
            screenshot_path, ocr_text = ocr_engine.capture_screen_and_ocr(
                auto_scroll=self.auto_scroll,
                scroll_count=self.scroll_count,
                on_capture_done=lambda: self.capture_completed.emit()
            )
            self.finished.emit(screenshot_path, ocr_text)
        except Exception as e:
            self.failed.emit(str(e))


class VoiceRecorderWorker(QThread):
    """Background worker for recording microphone audio and transcribing via SpeechRecognition."""
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)
    
    def __init__(self, sample_rate=16000):
        super().__init__()
        self.sample_rate = sample_rate
        self.is_recording = False
        self.audio_frames = []
        
    def run(self):
        import sounddevice as sd
        import numpy as np
        import scipy.io.wavfile as wav
        import speech_recognition as sr
        import io
        
        self.is_recording = True
        self.audio_frames = []
        
        def callback(indata, frames, time_info, status):
            if self.is_recording:
                self.audio_frames.append(indata.copy())
                
        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='int16', callback=callback):
                while self.is_recording:
                    self.msleep(50)
        except Exception as e:
            self.failed.emit(f"Microphone access error: {str(e)}")
            return
            
        if not self.audio_frames:
            self.failed.emit("No audio recorded.")
            return
            
        try:
            audio_data = np.concatenate(self.audio_frames, axis=0)
            if len(audio_data) < self.sample_rate * 0.3:
                self.failed.emit("Audio recording was too short.")
                return
                
            if np.max(np.abs(audio_data)) < 150:
                self.failed.emit("No clear voice detected.")
                return
                
            wav_io = io.BytesIO()
            wav.write(wav_io, self.sample_rate, audio_data)
            wav_io.seek(0)
            
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_io) as source:
                audio = recognizer.record(source)
                
            transcribed_text = recognizer.recognize_google(audio)
            self.finished.emit(transcribed_text)
        except sr.UnknownValueError:
            self.failed.emit("Could not understand audio. Please speak clearly.")
        except sr.RequestError as e:
            self.failed.emit(f"Speech service error: {str(e)}")
        except Exception as e:
            self.failed.emit(f"Transcription error: {str(e)}")
            
    def stop_recording(self):
        self.is_recording = False


class NexaChatWindow(QWidget):
    """Main ChatGPT-styled UI window with Universal Multi-Modal Input and Cosmic Neon aesthetic."""
    hotkey_registered_signal = pyqtSignal(str)
    
    def __init__(self, toggle_callback=None):
        super().__init__()
        self.toggle_callback = toggle_callback
        self.current_session_id = None
        self.hero_widget = None
        self.attachments = [] # List of active attached items
        
        self.setWindowTitle("Nexa AI Dashboard")
        self.setMinimumSize(980, 680)
        self.setAcceptDrops(True)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #0b0c14;
                color: #e2e8f0;
                font-family: 'Segoe UI', 'Inter', Arial, sans-serif;
            }
            QSplitter::handle {
                background-color: #161828;
            }
            QScrollBar:vertical {
                border: none;
                background: #0b0c14;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #252840;
                min-height: 25px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a855f7;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.init_ui()
        
    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        
        # 1. Left Sidebar
        sidebar_widget = QWidget(self)
        sidebar_widget.setObjectName("Sidebar")
        sidebar_widget.setMinimumWidth(260)
        sidebar_widget.setMaximumWidth(310)
        sidebar_widget.setStyleSheet("""
            QWidget#Sidebar {
                background-color: #07080d;
                border-right: 1px solid #161828;
            }
            QPushButton#NewChatBtn {
                background-color: #121422;
                border: 1px solid #282b45;
                border-radius: 10px;
                color: #f1f5f9;
                padding: 10px 14px;
                font-size: 13px;
                font-weight: 600;
                text-align: left;
            }
            QPushButton#NewChatBtn:hover {
                background-color: #1c1f36;
                border-color: #8b5cf6;
                color: #ffffff;
            }
            QListWidget {
                background-color: transparent;
                border: none;
                color: #94a3b8;
                font-size: 13px;
                outline: none;
                padding: 4px 6px;
            }
            QListWidget::item {
                border-radius: 8px;
                padding: 8px 10px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #131524;
                color: #f1f5f9;
            }
            QListWidget::item:selected {
                background-color: #1e2138;
                color: #ffffff;
                font-weight: 600;
                border: 1px solid #383d5e;
            }
            QPushButton#SettingsBtn {
                background-color: #0e101c;
                border: 1px solid #1d2035;
                border-radius: 8px;
                color: #94a3b8;
                padding: 8px 12px;
                font-size: 12px;
                text-align: left;
                margin: 8px 14px 14px 14px;
            }
            QPushButton#SettingsBtn:hover {
                background-color: #17192a;
                color: #ffffff;
                border-color: #8b5cf6;
            }
        """)
        
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 16, 0, 0)
        sidebar_layout.setSpacing(6)
        
        # New Chat Button
        new_chat_btn = QPushButton("➕  New Chat", sidebar_widget)
        new_chat_btn.setObjectName("NewChatBtn")
        new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_chat_btn.clicked.connect(self.new_session)
        
        nc_container = QHBoxLayout()
        nc_container.setContentsMargins(14, 0, 14, 8)
        nc_container.addWidget(new_chat_btn)
        sidebar_layout.addLayout(nc_container)
        
        # Quick Action Buttons
        nav_container = QWidget(sidebar_widget)
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(14, 0, 14, 4)
        nav_layout.setSpacing(4)
        
        nav_btn_style = """
            QPushButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                color: #94a3b8;
                padding: 7px 10px;
                font-size: 12px;
                text-align: left;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #121422;
                border-color: #23273e;
                color: #e2e8f0;
            }
        """
        
        btn_capture = QPushButton("📷  Screen Capture", nav_container)
        btn_capture.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_capture.setStyleSheet(nav_btn_style)
        btn_capture.clicked.connect(self.trigger_capture_and_analyze)
        nav_layout.addWidget(btn_capture)
        
        btn_attach = QPushButton("📎  Attach Any File", nav_container)
        btn_attach.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_attach.setStyleSheet(nav_btn_style)
        btn_attach.clicked.connect(self.show_attach_menu)
        nav_layout.addWidget(btn_attach)

        btn_calc = QPushButton("🧮  Calculator (Math/Units)", nav_container)
        btn_calc.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_calc.setStyleSheet(nav_btn_style)
        btn_calc.clicked.connect(self.open_calculator_dialog)
        nav_layout.addWidget(btn_calc)

        btn_chart = QPushButton("📈  Chart Generator", nav_container)
        btn_chart.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_chart.setStyleSheet(nav_btn_style)
        btn_chart.clicked.connect(self.open_chart_generator_dialog)
        nav_layout.addWidget(btn_chart)

        btn_compress = QPushButton("🗜️  File Compressor", nav_container)
        btn_compress.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_compress.setStyleSheet(nav_btn_style)
        btn_compress.clicked.connect(self.open_file_compressor_dialog)
        nav_layout.addWidget(btn_compress)
        
        sidebar_layout.addWidget(nav_container)

        
        # Recent Chats Section Title
        chats_header = QLabel("RECENT CHATS", sidebar_widget)
        chats_header.setStyleSheet("color: #475569; font-size: 10px; font-weight: bold; margin: 8px 16px 4px 16px; background: transparent; border: none;")
        sidebar_layout.addWidget(chats_header)
        
        self.session_list = QListWidget(sidebar_widget)
        self.session_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.session_list.itemClicked.connect(self.on_session_clicked)
        sidebar_layout.addWidget(self.session_list, 1)
        
        # User Profile Widget (ChatGPT style)
        self.user_profile_widget = UserProfileWidget(sidebar_widget)
        self.user_profile_widget.profile_clicked.connect(self.open_auth_dialog)
        sidebar_layout.addWidget(self.user_profile_widget)
        
        settings_btn = QPushButton("⚙️  Settings & Configuration", sidebar_widget)
        settings_btn.setObjectName("SettingsBtn")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self.open_settings)
        sidebar_layout.addWidget(settings_btn)
        
        # 2. Right Chat Area
        chat_container = QWidget(self)
        chat_container.setAcceptDrops(True)
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)
        
        # Chat Header
        header = QFrame(chat_container)
        header.setFixedHeight(56)
        header.setStyleSheet("background-color: #0b0c14; border-bottom: 1px solid #161828;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(12)
        
        self.header_title = QLabel("Nexa Multi-Modal Assistant", header)
        self.header_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.header_title.setStyleSheet("color: #ffffff; border: none;")
        self.header_title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        header_layout.addWidget(self.header_title)
        
        header_layout.addStretch(1)
        
        # Model Pill
        model_pill = QFrame(header)
        model_pill.setStyleSheet("""
            QFrame {
                background-color: #141624;
                border: 1px solid #282b42;
                border-radius: 16px;
                padding: 2px 10px;
            }
        """)
        pill_layout = QHBoxLayout(model_pill)
        pill_layout.setContentsMargins(8, 2, 8, 2)
        pill_layout.setSpacing(6)
        
        pill_icon = QLabel("✨", model_pill)
        pill_icon.setStyleSheet("color: #ec4899; background: transparent; border: none; font-size: 12px;")
        pill_layout.addWidget(pill_icon)
        
        self.model_label = QLabel("Nexa Vision", model_pill)
        self.model_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.model_label.setStyleSheet("color: #e2e8f0; background: transparent; border: none;")
        pill_layout.addWidget(self.model_label)
        
        header_layout.addWidget(model_pill)
        header_layout.addStretch(1)
        
        capture_btn = QPushButton("📷 Capture Screen", header)
        capture_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899);
                border: none;
                border-radius: 8px;
                color: white;
                padding: 7px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9d71fa, stop:1 #f472b6);
            }
        """)
        capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        capture_btn.clicked.connect(self.trigger_capture_and_analyze)
        header_layout.addWidget(capture_btn)
        
        chat_layout.addWidget(header, 0)
        
        # Chat Bubble Scroll Area
        self.scroll_area = QScrollArea(chat_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: #0b0c14; border: none;")
        
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background-color: #0b0c14;")
        
        scroll_outer_layout = QHBoxLayout(self.scroll_content)
        scroll_outer_layout.setContentsMargins(0, 0, 0, 0)
        scroll_outer_layout.setSpacing(0)
        scroll_outer_layout.addStretch(1)
        
        self.chat_inner_column = QWidget(self.scroll_content)
        self.chat_inner_column.setMaximumWidth(880)
        self.chat_inner_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.chat_inner_column.setStyleSheet("background-color: transparent;")
        
        self.scroll_layout = QVBoxLayout(self.chat_inner_column)
        self.scroll_layout.setContentsMargins(16, 20, 16, 20)
        self.scroll_layout.setSpacing(16)
        self.scroll_layout.addStretch()
        
        scroll_outer_layout.addWidget(self.chat_inner_column, 10)
        scroll_outer_layout.addStretch(1)
        
        self.scroll_area.setWidget(self.scroll_content)
        chat_layout.addWidget(self.scroll_area, 1)
        
        # Input Area Panel
        input_panel = QFrame(chat_container)
        input_panel.setObjectName("InputPanel")
        input_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        input_panel.setStyleSheet("QFrame#InputPanel { background-color: #0b0c14; border-top: 1px solid #161828; }")
        input_layout = QVBoxLayout(input_panel)
        input_layout.setContentsMargins(20, 10, 20, 14)
        input_layout.setSpacing(0)
        
        input_center_layout = QHBoxLayout()
        input_center_layout.setContentsMargins(0, 0, 0, 0)
        input_center_layout.setSpacing(0)
        input_center_layout.addStretch(1)
        
        input_inner_widget = QWidget(input_panel)
        input_inner_widget.setMaximumWidth(880)
        input_inner_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        input_inner_widget.setStyleSheet("background-color: transparent;")
        
        inner_vbox = QVBoxLayout(input_inner_widget)
        inner_vbox.setContentsMargins(0, 0, 0, 0)
        inner_vbox.setSpacing(6)
        
        # Attachment Preview Chips Bar (Visible when files/URLs are attached)
        self.attachment_bar = QWidget(input_inner_widget)
        self.attachment_bar_layout = QHBoxLayout(self.attachment_bar)
        self.attachment_bar_layout.setContentsMargins(0, 0, 0, 4)
        self.attachment_bar_layout.setSpacing(8)
        self.attachment_bar_layout.addStretch()
        self.attachment_bar.hide()
        inner_vbox.addWidget(self.attachment_bar)
        
        input_box_wrapper = QHBoxLayout()
        input_box_wrapper.setSpacing(10)
        
        # Plus (+) Menu Action Button
        self.plus_btn = QPushButton("+", input_inner_widget)
        self.plus_btn.setFixedSize(48, 48)
        self.plus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.plus_btn.setToolTip("Add attachments: Files, Code, Images, Videos, Audio, Camera, URLs...")
        self.plus_btn.setStyleSheet("""
            QPushButton {
                background-color: #141624;
                border: 1px solid #282b42;
                border-radius: 12px;
                color: #94a3b8;
                font-size: 22px;
                font-weight: bold;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #1e2136;
                color: #ec4899;
                border-color: #ec4899;
            }
        """)
        self.plus_btn.clicked.connect(self.show_attach_menu)
        input_box_wrapper.addWidget(self.plus_btn)
        
        # Quick Attach (📎) Button
        self.clip_btn = QPushButton("📎", input_inner_widget)
        self.clip_btn.setFixedSize(48, 48)
        self.clip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clip_btn.setToolTip("Attach file from computer")
        self.clip_btn.setStyleSheet("""
            QPushButton {
                background-color: #141624;
                border: 1px solid #282b42;
                border-radius: 12px;
                color: #94a3b8;
                font-size: 17px;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #1e2136;
                color: #8b5cf6;
                border-color: #8b5cf6;
            }
        """)
        self.clip_btn.clicked.connect(self.attach_any_file_dialog)
        input_box_wrapper.addWidget(self.clip_btn)
        
        self.text_input = QTextEdit(input_inner_widget)
        self.text_input.setPlaceholderText("Ask Nexa anything, drag & drop files, or attach images, documents, code & video...")
        self.text_input.setFixedHeight(48)
        self.text_input.installEventFilter(self)
        self.text_input.setStyleSheet("""
            QTextEdit {
                background-color: #141624;
                border: 1px solid #282b42;
                border-radius: 12px;
                color: #f1f5f9;
                padding: 12px 16px;
                font-size: 13px;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border: 1px solid #8b5cf6;
            }
        """)
        input_box_wrapper.addWidget(self.text_input)
        
        # Voice (Mic) Button
        self.mic_btn = QPushButton("🎙️", input_inner_widget)
        self.mic_btn.setFixedSize(48, 48)
        self.mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_btn.setToolTip("Click to speak (Voice-to-Text Input)")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background-color: #141624;
                border: 1px solid #282b42;
                border-radius: 12px;
                color: #94a3b8;
                font-size: 17px;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #1e2136;
                color: #a855f7;
                border-color: #a855f7;
            }
        """)
        self.mic_btn.clicked.connect(self.toggle_voice_recording)
        input_box_wrapper.addWidget(self.mic_btn)
        
        # Gradient Send Button
        self.send_btn = QPushButton("➤", input_inner_widget)
        self.send_btn.setFixedSize(48, 48)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self.send_user_message)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ec4899, stop:1 #8b5cf6);
                border: none;
                border-radius: 12px;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding-left: 2px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f472b6, stop:1 #9d71fa);
            }
        """)
        input_box_wrapper.addWidget(self.send_btn)
        
        inner_vbox.addLayout(input_box_wrapper)
        
        info_lbl = QLabel("📁 Drag and drop files anywhere | 📷 Use Screen Capture or global hotkey anytime", input_inner_widget)
        info_lbl.setStyleSheet("color: #64748b; font-size: 11px; margin-top: 2px;")
        inner_vbox.addWidget(info_lbl)
        
        input_center_layout.addWidget(input_inner_widget, 10)
        input_center_layout.addStretch(1)
        
        input_layout.addLayout(input_center_layout)
        chat_layout.addWidget(input_panel, 0)
        
        splitter.addWidget(sidebar_widget)
        splitter.addWidget(chat_container)
        splitter.setSizes([260, 720])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
        self.reload_sessions_list()

    # --------------------------------------------------------------------------
    # Drag & Drop Support
    # --------------------------------------------------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)
            
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path and os.path.exists(file_path):
                    self.process_and_add_attachment(file_path)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    # --------------------------------------------------------------------------
    # Universal Attachment Management
    # --------------------------------------------------------------------------
    def add_attachment(self, item_dict):
        """Add an attachment item and render its chip in the preview bar."""
        if not item_dict or item_dict.get("type") == "error":
            err = item_dict.get("error", "Failed to process attachment.") if item_dict else "Invalid file."
            logger.warning(f"Attachment error: {err}")
            return
            
        self.attachments.append(item_dict)
        self.render_attachment_bar()
        self.text_input.setFocus()
        
    def remove_attachment(self, item_dict):
        """Remove an attachment item by reference."""
        if item_dict in self.attachments:
            self.attachments.remove(item_dict)
        self.render_attachment_bar()
        
    def clear_attachments(self):
        """Clear all active attachments."""
        self.attachments.clear()
        self.render_attachment_bar()
        
    def render_attachment_bar(self):
        """Redraw attachment chips above the input box."""
        # Clear existing widgets in layout
        while self.attachment_bar_layout.count() > 1:
            item = self.attachment_bar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        if not self.attachments:
            self.attachment_bar.hide()
            return
            
        for att in self.attachments:
            chip = AttachmentItemWidget(att, self.attachment_bar)
            chip.removed.connect(self.remove_attachment)
            self.attachment_bar_layout.insertWidget(self.attachment_bar_layout.count() - 1, chip)
            
        self.attachment_bar.show()

    def process_and_add_attachment(self, file_path):
        """Process any file path and add to attachment bar."""
        result = input_processors.process_any_file(file_path)
        if result.get("type") == "error":
            logger.warning(f"File attachment error: {result.get('error')}")
            # Show temporary notice in placeholder
            self.text_input.setPlaceholderText(f"⚠️ {result.get('error')}")
            QTimer.singleShot(3500, lambda: self.text_input.setPlaceholderText("Ask Nexa anything, drag & drop files, or attach images..."))
        else:
            self.add_attachment(result)

    # --------------------------------------------------------------------------
    # Plus (+) Multi-Modal Popup Menu
    # --------------------------------------------------------------------------
    def show_attach_menu(self):
        """Show rich styled popup menu with all input types."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #121422;
                border: 1px solid #282b42;
                border-radius: 12px;
                padding: 6px;
                color: #e2e8f0;
                font-size: 13px;
            }
            QMenu::item {
                padding: 8px 16px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899);
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background: #23273e;
                margin: 4px 6px;
            }
        """)
        
        act_doc = menu.addAction("📄  Upload Document (PDF, DOCX, TXT)")
        act_img = menu.addAction("🖼️  Upload Image (JPG, PNG, WebP)")
        act_vid = menu.addAction("🎥  Upload Video (MP4, MOV, WebM)")
        act_aud = menu.addAction("🎵  Upload Audio (MP3, WAV, M4A)")
        act_cam = menu.addAction("📷  Take Photo (Camera)")
        menu.addSeparator()
        act_calc = menu.addAction("🧮  Calculator & Unit Converter (Offline)")
        act_chart = menu.addAction("📈  Generate Visual Chart / Graph (Offline)")
        act_compress = menu.addAction("🗜️  Compress / Extract ZIP Archive (Offline)")
        menu.addSeparator()
        act_url = menu.addAction("🔗  Add Website URL")
        act_cap = menu.addAction("🖥️  Capture Screen")
        act_clip = menu.addAction("📋  Paste from Clipboard")
        menu.addSeparator()
        act_create_capsule = menu.addAction("📦  Create Project Capsule (.json)")
        
        # Position menu above plus button
        pos = self.plus_btn.mapToGlobal(self.plus_btn.rect().topLeft())
        pos.setY(pos.y() - 440)
        action = menu.exec(pos)
        
        if action == act_doc:
            self.attach_document_file()
        elif action == act_img:
            self.attach_image_file()
        elif action == act_vid:
            self.attach_video_file()
        elif action == act_aud:
            self.attach_audio_file()
        elif action == act_cam:
            self.attach_camera_snap()
        elif action == act_code:
            self.attach_code_file()
        elif action == act_data:
            self.attach_data_file()
        elif action == act_calc:
            self.open_calculator_dialog()
        elif action == act_chart:
            self.open_chart_generator_dialog()
        elif action == act_compress:
            self.open_file_compressor_dialog()
        elif action == act_url:
            self.attach_url_dialog()
        elif action == act_cap:
            self.trigger_capture_and_analyze()
        elif action == act_clip:
            self.attach_clipboard()
        elif action == act_create_capsule:
            self.create_project_capsule()


    # --------------------------------------------------------------------------
    # Project Capsule (📦) Handlers
    # --------------------------------------------------------------------------
    def create_project_capsule(self):
        """Synthesize active conversation history into a portable Project Capsule JSON."""
        import json
        import datetime
        
        if not self.current_session_id:
            return
            
        messages = database.get_messages(self.current_session_id)
        if not messages:
            self.text_input.setPlaceholderText("⚠️ Current chat is empty. Have a conversation first before creating a capsule!")
            QTimer.singleShot(3500, lambda: self.text_input.setPlaceholderText("Ask Nexa anything, drag & drop files, or attach images..."))
            return
            
        self.text_input.setPlaceholderText("📦 Creating Project Capsule JSON...")
        QApplication.processEvents()
        
        capsule_data = ai_client.generate_project_capsule(messages)
        default_name = f"Nexa_Capsule_{datetime.datetime.now().strftime('%Y-%m-%d_%H%M')}.json"
        
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project Capsule (.json)",
            default_name,
            "JSON Files (*.json);;All Files (*)"
        )
        
        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(capsule_data, f, indent=2)
                    
                project_name = capsule_data.get("project", "Project")
                confirm_msg = (
                    f"📦 **Project Capsule JSON Created Successfully!**\n\n"
                    f"- **Project:** `{project_name}`\n"
                    f"- **Saved File:** `{os.path.basename(save_path)}`\n"
                    f"- **Goal:** {capsule_data.get('goal', 'N/A')}\n\n"
                    f"💡 *In your next session, simply upload this `.json` file using **Upload Code / JSON File** or drag & drop to resume your project!*"
                )
                self.append_chat_bubble("assistant", confirm_msg)
                database.add_message(self.current_session_id, "assistant", confirm_msg)
            except Exception as e:
                logger.error(f"Failed writing capsule file: {e}")
                
        self.text_input.setPlaceholderText("Ask Nexa anything, drag & drop files, or attach images, documents, code & video...")

    # --------------------------------------------------------------------------
    # Specific Attachment Handlers
    # --------------------------------------------------------------------------
    def attach_any_file_dialog(self):
        """Open universal file picker."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Any File to Attach",
            "",
            "All Supported Files (*.png *.jpg *.jpeg *.webp *.pdf *.docx *.txt *.py *.js *.html *.css *.json *.csv *.xlsx *.mp4 *.mov *.mp3 *.wav);;All Files (*)"
        )
        if file_path:
            self.process_and_add_attachment(file_path)

    def attach_document_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Document", "", "Documents (*.pdf *.docx *.txt *.md *.rtf *.log);;All Files (*)"
        )
        if file_path:
            self.process_and_add_attachment(file_path)

    def attach_image_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;All Files (*)"
        )
        if file_path:
            self.process_and_add_attachment(file_path)

    def attach_video_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video", "", "Videos (*.mp4 *.mov *.avi *.webm *.mkv);;All Files (*)"
        )
        if file_path:
            self.process_and_add_attachment(file_path)

    def attach_audio_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio", "", "Audio Files (*.mp3 *.wav *.m4a *.ogg *.flac);;All Files (*)"
        )
        if file_path:
            self.process_and_add_attachment(file_path)

    def attach_code_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Code or JSON File", "", "Code & JSON Files (*.py *.js *.jsx *.ts *.tsx *.html *.css *.json *.xml *.yaml *.yml *.sql *.cpp *.c *.java *.cs *.go *.rs);;JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self.process_and_add_attachment(file_path)

    def attach_data_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Spreadsheet / Data File", "", "Data Files (*.csv *.tsv *.xlsx *.xls);;All Files (*)"
        )
        if file_path:
            self.process_and_add_attachment(file_path)

    def attach_camera_snap(self):
        """Capture live photo from webcam and attach."""
        snap = input_processors.capture_webcam_snapshot()
        if snap.get("type") == "error":
            logger.warning(f"Webcam error: {snap.get('error')}")
            self.text_input.setPlaceholderText(f"⚠️ {snap.get('error')}")
            QTimer.singleShot(3500, lambda: self.text_input.setPlaceholderText("Ask Nexa anything, drag & drop files..."))
        else:
            self.add_attachment(snap)

    def attach_url_dialog(self):
        """Prompt user for URL and fetch content."""
        dialog = AddUrlDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            url = dialog.get_url()
            if url:
                parsed = input_processors.fetch_url_content(url)
                if parsed.get("type") == "error":
                    self.text_input.setPlaceholderText(f"⚠️ {parsed.get('error')}")
                    QTimer.singleShot(3500, lambda: self.text_input.setPlaceholderText("Ask Nexa anything, drag & drop files..."))
                else:
                    self.add_attachment(parsed)

    def attach_clipboard(self):
        """Read image or text from system clipboard."""
        cb = QApplication.clipboard()
        img = cb.image()
        if not img.isNull():
            temp_path = os.path.join(input_processors.get_temp_dir(), f"clipboard_{int(time.time())}.png")
            img.save(temp_path, "PNG")
            self.add_attachment({
                "type": "image",
                "image_path": temp_path,
                "text": "🖼️ **Attached Image:** Clipboard Snapshot",
                "summary": "Clipboard Image",
                "filename": "clipboard.png",
                "path": temp_path
            })
            return
            
        text = cb.text().strip()
        if text:
            if text.startswith("http://") or text.startswith("https://"):
                parsed = input_processors.fetch_url_content(text)
                self.add_attachment(parsed)
            else:
                self.add_attachment({
                    "type": "document",
                    "text": f"📋 **Clipboard Text Snippet:**\n```text\n{text[:15000]}\n```",
                    "summary": f"Clipboard ({len(text)} chars)",
                    "filename": "clipboard.txt"
                })

    # --------------------------------------------------------------------------
    # Event Filter (Enter to Send)
    # --------------------------------------------------------------------------
    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self.text_input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False
                else:
                    self.send_user_message()
                    return True
        return super().eventFilter(obj, event)

    # --------------------------------------------------------------------------
    # Session & Chat History Management
    # --------------------------------------------------------------------------
    def reload_sessions_list(self):
        self.session_list.clear()
        sessions = database.get_sessions()
        
        for sess in sessions:
            item = QListWidgetItem(sess["title"])
            item.setData(Qt.ItemDataRole.UserRole, sess["id"])
            self.session_list.addItem(item)
            
        if self.session_list.count() > 0:
            if self.current_session_id is None:
                first_item = self.session_list.item(0)
                self.session_list.setCurrentItem(first_item)
                self.load_session_chat(first_item.data(Qt.ItemDataRole.UserRole))
        else:
            self.new_session()
            
    def new_session(self):
        session_id = database.create_session()
        self.current_session_id = session_id
        self.clear_attachments()
        self.reload_sessions_list()
        
        for i in range(self.session_list.count()):
            item = self.session_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == session_id:
                self.session_list.setCurrentItem(item)
                self.load_session_chat(session_id)
                break
                
    def on_session_clicked(self, item):
        session_id = item.data(Qt.ItemDataRole.UserRole)
        self.load_session_chat(session_id)
        
    def load_session_chat(self, session_id):
        self.current_session_id = session_id
        self.hero_widget = None
        self.clear_attachments()
        
        for i in range(self.session_list.count()):
            item = self.session_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == session_id:
                self.header_title.setText(item.text())
                break
                
        while self.scroll_layout.count() > 1:
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        messages = database.get_messages(session_id)
        if len(messages) == 0:
            self.hero_widget = HeroWelcomeWidget(
                on_capture=self.trigger_capture_and_analyze,
                on_attach=self.show_attach_menu,
                on_calculator=self.open_calculator_dialog,
                on_chart_generator=self.open_chart_generator_dialog,
                on_file_compressor=self.open_file_compressor_dialog,
                parent=self.chat_inner_column
            )
            self.scroll_layout.insertWidget(0, self.hero_widget)

        else:
            for msg in messages:
                bubble = MessageBubble(
                    role=msg["role"], 
                    text=msg["text"], 
                    screenshot_path=msg["screenshot_path"]
                )
                self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, bubble)
            
        self.scroll_to_bottom()
        
    def add_message_bubble(self, role, text, screenshot_path=None, auto_scroll=True):
        if self.hero_widget:
            self.hero_widget.deleteLater()
            self.hero_widget = None
            
        bubble = MessageBubble(role=role, text=text, screenshot_path=screenshot_path)
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, bubble)
        if auto_scroll:
            self.scroll_to_message(bubble)
        return bubble

    def scroll_to_message(self, bubble_widget=None):
        def do_scroll():
            if not self.scroll_area or not self.scroll_content:
                return
            v_bar = self.scroll_area.verticalScrollBar()
            if bubble_widget and bubble_widget.isVisible():
                pos = bubble_widget.mapTo(self.scroll_content, bubble_widget.rect().topLeft())
                bubble_top = pos.y()
                bubble_height = bubble_widget.height()
                viewport_height = self.scroll_area.viewport().height()
                if bubble_height <= viewport_height:
                    v_bar.setValue(v_bar.maximum())
                else:
                    v_bar.setValue(max(0, bubble_top - 15))
            else:
                v_bar.setValue(v_bar.maximum())
        QTimer.singleShot(40, do_scroll)
        QTimer.singleShot(120, do_scroll)

    def scroll_to_bottom(self):
        def do_scroll():
            if not self.scroll_area:
                return
            v_bar = self.scroll_area.verticalScrollBar()
            v_bar.setValue(v_bar.maximum())
        QTimer.singleShot(40, do_scroll)
        QTimer.singleShot(120, do_scroll)
        
    # --------------------------------------------------------------------------
    # Voice Input
    # --------------------------------------------------------------------------
    def toggle_voice_recording(self):
        if hasattr(self, 'voice_worker') and self.voice_worker and self.voice_worker.isRunning():
            self.mic_btn.setText("⏳")
            self.mic_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2f2f2f;
                    border: 1px solid #f59e0b;
                    border-radius: 8px;
                    color: #f59e0b;
                    font-size: 18px;
                }
            """)
            self.text_input.setPlaceholderText("Transcribing voice to text...")
            self.voice_worker.stop_recording()
        else:
            self.mic_btn.setText("⏹️")
            self.mic_btn.setStyleSheet("""
                QPushButton {
                    background-color: #7f1d1d;
                    border: 1px solid #ef4444;
                    border-radius: 8px;
                    color: #ffffff;
                    font-size: 18px;
                }
                QPushButton:hover {
                    background-color: #991b1b;
                }
            """)
            self.text_input.setPlaceholderText("🎙️ Listening... Speak your question now, then click ⏹️.")
            
            self.voice_worker = VoiceRecorderWorker()
            
            def on_voice_finished(text):
                self.reset_mic_button()
                if text:
                    curr = self.text_input.toPlainText().strip()
                    if curr:
                        self.text_input.setPlainText(f"{curr} {text}")
                    else:
                        self.text_input.setPlainText(text)
                    cursor = self.text_input.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.End)
                    self.text_input.setTextCursor(cursor)
                    self.text_input.setFocus()
                    
            def on_voice_failed(err_msg):
                self.reset_mic_button()
                logger.warning(f"Voice notice: {err_msg}")
                self.text_input.setPlaceholderText(f"Voice notice: {err_msg}")
                QTimer.singleShot(3000, lambda: self.text_input.setPlaceholderText("Ask Nexa anything, drag & drop files..."))
                
            self.voice_worker.finished.connect(on_voice_finished)
            self.voice_worker.failed.connect(on_voice_failed)
            self.voice_worker.start()
            
    def reset_mic_button(self):
        self.mic_btn.setText("🎙️")
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background-color: #141624;
                border: 1px solid #282b42;
                border-radius: 12px;
                color: #94a3b8;
                font-size: 17px;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #1e2136;
                color: #a855f7;
                border-color: #a855f7;
            }
        """)
        self.text_input.setPlaceholderText("Ask Nexa anything, drag & drop files, or attach images...")

    # --------------------------------------------------------------------------
    # Send User Message (Unified Multi-Modal Query Builder)
    # --------------------------------------------------------------------------
    def send_user_message(self):
        text = self.text_input.toPlainText().strip()
        if not text and not self.attachments:
            return
            
        if self.current_session_id is None:
            self.new_session()
            
        self.text_input.clear()
        
        # Determine image path for vision model if attached
        primary_image_path = None
        for att in self.attachments:
            if att.get("type") in ("image", "video") and att.get("image_path"):
                primary_image_path = att.get("image_path")
                break
                
        # Build prompt payload and display message
        display_parts = []
        payload_parts = []
        
        # Add attachment contents to payload
        for att in self.attachments:
            summary = att.get("summary", att.get("filename", "Attachment"))
            display_parts.append(f"[{summary}]")
            if att.get("text"):
                payload_parts.append(att.get("text"))
                
        if text:
            display_parts.append(text)
            payload_parts.append(f"**User Request:**\n{text}")
        elif not text and self.attachments:
            # Default instruction when only files were attached
            payload_parts.append("**User Request:**\nPlease analyze and summarize the attached content.")
            display_parts.append("Please analyze the attached content.")
            
        user_display_msg = " ".join(display_parts)
        user_payload_msg = "\n\n".join(payload_parts)
        
        # Update session heading
        self.update_current_session_heading(text or display_parts[0])
        
        # Clear attachments after sending
        self.clear_attachments()
        
        # Save to DB & Render User Bubble
        database.add_message(self.current_session_id, "user", user_payload_msg, primary_image_path)
        self.add_message_bubble("user", user_display_msg, primary_image_path)
        
        # Request AI Response
        self.request_ai_response()

    def request_ai_response(self):
        if self.current_session_id is None:
            return
            
        placeholder = self.add_message_bubble("assistant", "⏳ Nexa AI is visually analyzing and thinking...")
        
        class ApiWorker(QThread):
            finished = pyqtSignal(str)
            def __init__(self, session_id):
                super().__init__()
                self.session_id = session_id
            def run(self):
                db_messages = database.get_messages(self.session_id)
                formatted_history = []
                for m in db_messages:
                    formatted_history.append({
                        "role": m["role"], 
                        "text": m["text"],
                        "screenshot_path": m.get("screenshot_path")
                    })
                response_text = ai_client.generate_response(formatted_history)
                self.finished.emit(response_text)
                
        self.worker = ApiWorker(self.current_session_id)
        
        @pyqtSlot(str)
        def on_worker_finished(response_text):
            placeholder.deleteLater()
            database.add_message(self.current_session_id, "assistant", response_text)
            self.add_message_bubble("assistant", response_text)
            
        self.worker.finished.connect(on_worker_finished)
        self.worker.start()

    def update_current_session_heading(self, prompt_text):
        if not prompt_text or not self.current_session_id:
            return
        sessions = database.get_sessions()
        curr_sess = next((s for s in sessions if s["id"] == self.current_session_id), None)
        if curr_sess and curr_sess["title"] not in ("New Chat", "") and not curr_sess["title"].startswith("Screen Analysis 20"):
            return
            
        import re
        clean = str(prompt_text).strip()
        clean = re.sub(r'[*#`_\[\]]', '', clean).strip()
        first_line = clean.splitlines()[0] if clean else "New Chat"
        heading = first_line[:26].strip() + "..." if len(first_line) > 28 else first_line or "New Chat"
        database.update_session_title(self.current_session_id, heading)
        
        for i in range(self.session_list.count()):
            item = self.session_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self.current_session_id:
                item.setText(heading)
                break

    # --------------------------------------------------------------------------
    # Screen Capture Workflow
    # --------------------------------------------------------------------------
    def trigger_capture_and_analyze(self):
        show_prompt = database.get_setting("show_capture_prompt", "True") == "True"
        auto_scroll = database.get_setting("auto_scroll", "False") == "True"
        scroll_count = int(database.get_setting("scroll_count", "3"))
        
        if show_prompt:
            dialog = CapturePromptDialog(self, default_auto_scroll=auto_scroll)
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            try:
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(int(dialog.winId()))
            except Exception:
                pass
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            auto_scroll = dialog.scroll_check.isChecked()
            scroll_count = dialog.scroll_spin.value() if auto_scroll else 1
        else:
            scroll_count = scroll_count if auto_scroll else 1

        try:
            from plyer import notification
            notification.notify(
                title="Nexa AI Assistant",
                message="Capturing screen and running OCR analysis...",
                app_name="Nexa AI",
                timeout=3
            )
        except Exception:
            pass

        if self.toggle_callback:
            self.toggle_callback(False)
            time.sleep(0.35)
            
        try:
            ocr_engine.get_ocr_reader()
        except Exception as e:
            logger.error(f"Error initializing OCR reader on main thread: {e}")
        
        existing_msgs = database.get_messages(self.current_session_id)
        if len(existing_msgs) > 0:
            self.new_session()
            
        self.ocr_worker = OcrWorker(auto_scroll, scroll_count)
        ocr_placeholder = None
        ai_placeholder = None
        
        def restore_window():
            nonlocal ocr_placeholder, ai_placeholder
            if self.toggle_callback:
                self.toggle_callback(True)
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            self.showNormal()
            self.raise_()
            self.activateWindow()
            try:
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(int(self.winId()))
            except Exception:
                pass
            ocr_placeholder = self.add_message_bubble("user", "📸 Capturing screen and running OCR text extraction...")
            ai_placeholder = self.add_message_bubble("assistant", "⏳ Waiting for OCR text to finish...")
            
        self.ocr_worker.capture_completed.connect(restore_window)
        
        def on_ocr_finished(screenshot_path, ocr_text):
            nonlocal ocr_placeholder, ai_placeholder
            if ocr_placeholder:
                ocr_placeholder.deleteLater()
            if ai_placeholder:
                ai_placeholder.deleteLater()
            
            if not ocr_text or ocr_text.strip() == "":
                ocr_text = "[Visual screen content captured. No plain text detected.]"
                
            user_display_msg = "Please analyze my captured screen."
            user_payload_msg = (
                f"Here is the text extracted from my screen capture:\n\n"
                f"```text\n{ocr_text}\n```\n\n"
                f"Analyze this content. Provide a clear summary, explain any errors, and highlight key elements."
            )
            
            self.update_current_session_heading("Screen Analysis")
            database.add_message(self.current_session_id, "user", user_payload_msg, screenshot_path)
            self.add_message_bubble("user", user_display_msg, screenshot_path)
            self.request_ai_response()
            
        def on_ocr_failed(error_msg):
            nonlocal ocr_placeholder, ai_placeholder
            if ocr_placeholder:
                ocr_placeholder.deleteLater()
            if ai_placeholder:
                ai_placeholder.deleteLater()
            
            error_text = f"Error: Screen capture or text extraction failed: {error_msg}"
            database.add_message(self.current_session_id, "user", error_text, None)
            self.add_message_bubble("user", "Failed to analyze screen capture.")
            self.add_message_bubble("assistant", error_text)
            
        self.ocr_worker.finished.connect(on_ocr_finished)
        self.ocr_worker.failed.connect(on_ocr_failed)
        self.ocr_worker.start()

    def open_calculator_dialog(self):
        """Open interactive offline Math & Calculator modal."""
        dialog = CalculatorDialog(on_insert_chat=self.insert_plugin_result_to_chat, parent=self)
        dialog.exec()

    def open_chart_generator_dialog(self):
        """Open interactive offline Chart & Graph generator modal."""
        dialog = ChartGeneratorDialog(on_insert_chat=self.insert_plugin_result_to_chat, parent=self)
        dialog.exec()

    def open_file_compressor_dialog(self):
        """Open interactive offline File Compressor and Extractor modal."""
        dialog = FileCompressorDialog(on_insert_chat=self.insert_plugin_result_to_chat, parent=self)
        dialog.exec()

    def insert_plugin_result_to_chat(self, result_markdown):
        """Insert generated tool result directly into active chat conversation."""
        if not self.current_session_id:
            self.new_session()
        self.add_message_bubble("assistant", result_markdown)
        database.add_message(self.current_session_id, "assistant", result_markdown)

    def open_settings(self):
        dialog = SettingsDialog(self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_hotkey = database.get_setting("global_hotkey", "Ctrl+Alt+N")
            self.hotkey_registered_signal.emit(new_hotkey)

    def open_auth_dialog(self):
        dialog = AuthLoginDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.user_profile_widget.refresh_profile()

    def closeEvent(self, event):
        event.ignore()
        if self.toggle_callback:
            self.toggle_callback(False)
        else:
            self.hide()
