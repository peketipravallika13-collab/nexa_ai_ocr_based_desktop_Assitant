import os
import sys

# Set test database path before importing database to prevent polluting production DB
TEST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_nexa_history.db")
os.environ["NEXA_DB_PATH"] = TEST_DB_PATH

import unittest
from PIL import Image, ImageDraw
import numpy as np

# Ensure workspace is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database
import ai_client
import input_processors
import gui_components

class TestNexaComponents(unittest.TestCase):
    
    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception as e:
                print(f"Failed to remove test database: {e}")
                
    def test_database_crud(self):
        """Test database settings, sessions, and messages creation/deletion."""
        print("\n--- Running Database CRUD Tests ---")
        database.set_setting("test_key", "test_value")
        val = database.get_setting("test_key")
        self.assertEqual(val, "test_value")
        
        session_id = database.create_session("Test Session 123")
        self.assertIsNotNone(session_id)
        
        sessions = database.get_sessions()
        self.assertTrue(any(s["id"] == session_id for s in sessions))
        
        database.add_message(session_id, "user", "Hello Test AI")
        database.add_message(session_id, "assistant", "Hello Test User")
        
        messages = database.get_messages(session_id)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")
        
        database.delete_session(session_id)
        sessions_after = database.get_sessions()
        self.assertFalse(any(s["id"] == session_id for s in sessions_after))
        print("Database CRUD tests completed successfully.")
        
    def test_input_processors(self):
        """Test processing of code files, csv files, and documents."""
        print("\n--- Running Multi-Modal Input Processors Tests ---")
        temp_dir = input_processors.get_temp_dir()
        
        # 1. Test Code File
        code_file = os.path.join(temp_dir, "test_calc.py")
        with open(code_file, "w", encoding="utf-8") as f:
            f.write("def add(a, b):\n    return a + b\n")
        res_code = input_processors.process_any_file(code_file)
        self.assertEqual(res_code["type"], "code")
        self.assertIn("test_calc.py", res_code["text"])
        self.assertIn("def add", res_code["text"])
        
        # 2. Test CSV Data File
        csv_file = os.path.join(temp_dir, "test_sales.csv")
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("Month,Revenue,Profit\nJan,10000,3000\nFeb,15000,4500\n")
        res_csv = input_processors.process_any_file(csv_file)
        self.assertEqual(res_csv["type"], "data")
        self.assertIn("Month", res_csv["text"])
        self.assertIn("Revenue", res_csv["text"])
        
        # 3. Clean up
        if os.path.exists(code_file):
            os.remove(code_file)
        if os.path.exists(csv_file):
            os.remove(csv_file)
            
        print("Input Processors tests completed successfully.")

    def test_gui_chat_window(self):
        """Test NexaChatWindow initialization, attachments bar, and plus button."""
        print("\n--- Running GUI Multi-Modal Input Tests ---")
        from PyQt6.QtWidgets import QApplication
        
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
            
        chat_win = gui_components.NexaChatWindow()
        self.assertIsNotNone(chat_win.plus_btn)
        self.assertEqual(chat_win.plus_btn.text(), "+")
        self.assertIsNotNone(chat_win.clip_btn)
        self.assertEqual(chat_win.clip_btn.text(), "📎")
        self.assertIsNotNone(chat_win.mic_btn)
        self.assertEqual(chat_win.mic_btn.text(), "🎙️")
        
        # Test adding an attachment
        test_attachment = {
            "type": "code",
            "text": "```python\nprint('hello')\n```",
            "summary": "test.py",
            "filename": "test.py"
        }
        chat_win.add_attachment(test_attachment)
        self.assertEqual(len(chat_win.attachments), 1)
        self.assertFalse(chat_win.attachment_bar.isHidden())
        
        # Test clearing attachments
        chat_win.clear_attachments()
        self.assertEqual(len(chat_win.attachments), 0)
        self.assertTrue(chat_win.attachment_bar.isHidden())

        
        print("GUI Multi-Modal Input tests completed successfully.")

    def test_project_capsule(self):
        """Test creating, exporting, and importing Nexa Project Capsules."""
        print("\n--- Running Project Capsule Tests ---")
        import json
        temp_dir = input_processors.get_temp_dir()
        capsule_file = os.path.join(temp_dir, "test_nexa_capsule.json")
        
        sample_capsule = {
            "project": "Nexa AI Assistant",
            "goal": "Build an intelligent multimodal desktop AI",
            "technology": ["Python", "PyQt6", "Gemini API", "SQLite"],
            "completed_work": ["Screen capture", "OCR Engine", "Chat Window", "Capsule Export"],
            "current_status": "Integrating project capsules",
            "important_decisions": ["Centralized backend controller", "Single Gemini API Key"],
            "next_steps": ["Test capsule import", "Verify context continuity"],
            "conversation_summary": "Built multimodal input features and capsule export/import mechanism.",
            "nexa_capsule_version": "1.0"
        }
        
        with open(capsule_file, 'w', encoding='utf-8') as f:
            json.dump(sample_capsule, f, indent=2)
            
        # Test capsule detection
        self.assertTrue(input_processors.is_nexa_capsule(sample_capsule))
        
        # Test parsing via process_any_file
        parsed = input_processors.process_any_file(capsule_file)
        self.assertEqual(parsed.get("type"), "capsule")
        self.assertIn("Nexa AI Assistant", parsed.get("text", ""))
        self.assertIn("Single Gemini API Key", parsed.get("text", ""))
        self.assertIn("Test capsule import", parsed.get("text", ""))
        
        # Test AI capsule generator fallback structure
        mock_messages = [
            {"role": "user", "text": "Let's build a desktop app"},
            {"role": "assistant", "text": "I can help build Nexa with PyQt6."}
        ]
        generated = ai_client.generate_project_capsule(mock_messages)
        self.assertIsInstance(generated, dict)
        self.assertIn("project", generated)
        self.assertIn("nexa_capsule_version", generated)
        
        # Clean up
        if os.path.exists(capsule_file):
            os.remove(capsule_file)
            
        print("Project Capsule tests completed successfully.")

    def test_user_profile_and_sidebar_widget(self):
        """Test database user profile functions and UserProfileWidget initial state."""
        print("\n--- Running User Profile & Sidebar Widget Tests ---")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
            
        # 1. Test database profile
        database.set_user_profile("pravallika@gmail.com", "Pravallika")
        prof = database.get_user_profile()
        self.assertEqual(prof["email"], "pravallika@gmail.com")
        self.assertEqual(prof["name"], "Pravallika")
        self.assertTrue(prof["is_logged_in"])
        
        # 2. Test UserAvatarWidget & UserProfileWidget
        avatar = gui_components.UserAvatarWidget("P", bg_color="#10a37f")
        self.assertEqual(avatar.letter, "P")
        
        prof_widget = gui_components.UserProfileWidget()
        prof_widget.refresh_profile()
        self.assertEqual(prof_widget.avatar.letter, "P")
        self.assertEqual(prof_widget.name_label.text(), "Pravallika")
        
        # 3. Test logout
        database.logout_user()
        prof_logged_out = database.get_user_profile()
        self.assertFalse(prof_logged_out["is_logged_in"])
        prof_widget.refresh_profile()
        self.assertEqual(prof_widget.avatar.letter, "👤")
        print("User Profile & Sidebar Widget tests completed successfully.")

if __name__ == "__main__":
    unittest.main()
