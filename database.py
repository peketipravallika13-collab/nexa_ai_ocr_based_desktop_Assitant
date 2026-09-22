import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv("NEXA_DB_PATH", os.path.join(os.path.expanduser("~"), ".nexa_ai", "nexa_history.db"))

def init_db():
    """Initialize the SQLite database and create tables if they do not exist."""
    db_dir = os.path.dirname(DB_PATH)
    # Avoid creating directory for in-memory databases or empty paths
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    
    # Create chat sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create chat messages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        text TEXT NOT NULL,
        screenshot_path TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
    )
    """)
    
    # Populate default settings if not exists
    defaults = {
        "api_provider": "gemini",
        "api_key": "",
        "model_name": "gemini-3.6-flash",
        "global_hotkey": "Ctrl+Alt+N",
        "auto_scroll": "False",
        "show_capture_prompt": "True",
        "scroll_count": "3",
        "plugin_web_search": "True",
        "plugin_code_execution": "True",
        "plugin_desktop_tools": "True",
        "plugin_productivity": "True",
        "plugin_custom_dir": "True",
        "user_email": "peketipravallika13@gmail.com",
        "user_name": "Pravallika Peketi",
        "user_logged_in": "True"
    }
    
    for key, val in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
        
    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_PATH)

def get_setting(key, default=None):
    """Retrieve a setting value by key."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    """Update or insert a setting value."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def create_session(title=None):
    """Create a new chat session and return its ID."""
    if not title:
        title = "New Chat"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_sessions (title) VALUES (?)", (title,))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id

def update_session_title(session_id, title):
    """Update title of an existing chat session."""
    if not title or not str(title).strip():
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE chat_sessions SET title = ? WHERE id = ?", (str(title).strip(), session_id))
    conn.commit()
    conn.close()

def delete_session(session_id):
    """Delete a chat session and all associated messages."""
    conn = get_connection()
    cursor = conn.cursor()
    # Enable foreign keys so CASCADE works if supported, or manually delete
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

def get_sessions():
    """Retrieve all chat sessions ordered by newest first."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, created_at FROM chat_sessions ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "created_at": r[2]} for r in rows]

def add_message(session_id, role, text, screenshot_path=None):
    """Add a message to a chat session."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_messages (session_id, role, text, screenshot_path) VALUES (?, ?, ?, ?)",
        (session_id, role, text, screenshot_path)
    )
    conn.commit()
    conn.close()

def get_messages(session_id):
    """Retrieve all messages in a session ordered by time."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, role, text, screenshot_path, timestamp FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "role": r[1],
            "text": r[2],
            "screenshot_path": r[3],
            "timestamp": r[4]
        }
        for r in rows
    ]

def get_user_profile():
    """Retrieve user profile information."""
    email = get_setting("user_email", "")
    name = get_setting("user_name", "")
    is_logged_in = get_setting("user_logged_in", "False").lower() == "true"
    
    if not name and email:
        name = email.split("@")[0].capitalize()
        
    return {
        "email": email,
        "name": name,
        "is_logged_in": is_logged_in
    }

def set_user_profile(email: str, name: str = None):
    """Save user profile information."""
    email = email.strip()
    if not name:
        name = email.split("@")[0].capitalize() if "@" in email else email.capitalize()
    set_setting("user_email", email)
    set_setting("user_name", name)
    set_setting("user_logged_in", "True" if email else "False")

def logout_user():
    """Clear logged in user profile."""
    set_setting("user_email", "")
    set_setting("user_name", "")
    set_setting("user_logged_in", "False")

# Initialize database on import
init_db()
