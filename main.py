import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Pre-import ocr_engine to initialize PyTorch/EasyOCR DLLs before PyQt6 to prevent conflict crashes
import ocr_engine

import sys
import time
import logging
import threading
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QMetaObject, Qt
from PyQt6.QtGui import QFont

import database
from gui_components import NexaChatWindow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# Global reference to prevent garbage collection
tray_icon = None
hotkey_manager = None
window = None

class HotkeyManager:
    """Manages global keyboard hotkeys using pynput, supporting dynamic re-registration."""
    def __init__(self, callback):
        self.callback = callback
        self.listener = None
        
    def parse_hotkey_to_pynput(self, hotkey_str):
        """Convert a standard string format like 'Ctrl+Alt+N' to pynput's '<ctrl>+<alt>+n'."""
        parts = hotkey_str.lower().split('+')
        mapped_parts = []
        for part in parts:
            part = part.strip()
            if part in ("ctrl", "control"):
                mapped_parts.append("<ctrl>")
            elif part == "alt":
                mapped_parts.append("<alt>")
            elif part in ("shift", "sft"):
                mapped_parts.append("<shift>")
            elif part in ("win", "cmd", "meta"):
                mapped_parts.append("<cmd>")
            else:
                mapped_parts.append(part)
        return "+".join(mapped_parts)
        
    def register(self, hotkey_str):
        """Stop current listener and register a new hotkey."""
        self.stop()
        pynput_str = self.parse_hotkey_to_pynput(hotkey_str)
        logger.info(f"Registering global hotkey listener: {pynput_str}")
        try:
            from pynput import keyboard
            
            def trigger_callback():
                logger.info("Global hotkey triggered!")
                # Call callback on main thread using QTimer
                QTimer.singleShot(0, self.callback)
                
            self.listener = keyboard.GlobalHotKeys({
                pynput_str: trigger_callback
            })
            self.listener.start()
        except Exception as e:
            logger.error(f"Failed to register global hotkey '{hotkey_str}': {e}")
            
    def stop(self):
        """Stop hotkey listening thread."""
        if self.listener:
            try:
                self.listener.stop()
            except Exception as e:
                logger.error(f"Error stopping hotkey listener: {e}")
            self.listener = None


def setup_system_tray(main_window):
    """Create and start system tray icon using PyStray."""
    global tray_icon
    import pystray
    from PIL import Image, ImageDraw
    
    # Generate tray icon image (ChatGPT green circular theme with letter 'N')
    img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Circle base
    d.ellipse([4, 4, 60, 60], fill=(16, 163, 127))
    # Draw letter 'N'
    d.polygon(
        [(18, 16), (26, 16), (46, 44), (46, 16), (52, 16), (52, 48), (44, 48), (24, 20), (24, 48), (18, 48)], 
        fill=(255, 255, 255)
    )
    
    def on_clicked(icon, item):
        cmd = str(item)
        if cmd == "Capture & Analyze":
            QTimer.singleShot(0, main_window.trigger_capture_and_analyze)
        elif cmd == "Show Nexa Window":
            QTimer.singleShot(0, lambda: toggle_window(True))
        elif cmd == "Settings":
            QTimer.singleShot(0, main_window.open_settings)
        elif cmd == "Exit":
            logger.info("Exiting application from system tray...")
            icon.stop()
            # Quit the QApplication event loop on main thread
            QTimer.singleShot(0, lambda: QApplication.quit())
            
    menu = pystray.Menu(
        pystray.MenuItem("Capture & Analyze", on_clicked),
        pystray.MenuItem("Show Nexa Window", on_clicked),
        pystray.MenuItem("Settings", on_clicked),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", on_clicked)
    )
    
    tray_icon = pystray.Icon("Nexa AI", img, "Nexa AI Assistant", menu)
    
    # Run tray loop in a background daemon thread
    tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
    tray_thread.start()
    logger.info("System tray icon started in background thread.")


def toggle_window(visible):
    """Safely show, hide, or restore main GUI window."""
    global window
    if not window:
        return
        
    if visible:
        window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        window.showNormal()
        window.raise_()
        window.activateWindow()
        try:
            import ctypes
            ctypes.windll.user32.SetForegroundWindow(int(window.winId()))
        except Exception:
            pass
    else:
        window.hide()


def main():
    global window, hotkey_manager
    
    logger.info("Starting Nexa AI Application...")
    
    # Create QApplication
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) # Remain active in tray when window is closed/hidden
    
    # Set app style and font
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    
    # Initialize the main ChatGPT-styled chat interface window
    window = NexaChatWindow(toggle_callback=toggle_window)
    
    # Setup System Tray
    setup_system_tray(window)
    
    # Register global hotkey
    hotkey_str = database.get_setting("global_hotkey", "Ctrl+Alt+N")
    hotkey_manager = HotkeyManager(window.trigger_capture_and_analyze)
    hotkey_manager.register(hotkey_str)
    
    # Bind window signal to update hotkeys dynamically
    window.hotkey_registered_signal.connect(hotkey_manager.register)
    
    # Enable clean Ctrl+C termination from terminal on Windows
    import signal
    def sigint_handler(sig, frame):
        logger.info("Ctrl+C detected in terminal. Exiting Nexa AI...")
        if hotkey_manager:
            hotkey_manager.stop()
        if tray_icon:
            try:
                tray_icon.stop()
            except Exception:
                pass
        app.quit()
        os._exit(0)
        
    signal.signal(signal.SIGINT, sigint_handler)
    
    # Periodic timer to allow Python interpreter to process OS signals during Qt event loop
    sigint_timer = QTimer()
    sigint_timer.start(300)
    sigint_timer.timeout.connect(lambda: None)
    
    # Show window on startup to confirm initialization
    toggle_window(True)
    
    # Execute App Loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

