import os
import sys
import unittest
import database
import plugin_manager
import ai_client

class TestNexaPlugins(unittest.TestCase):
    def setUp(self):
        database.init_db()
        
    def test_database_plugin_settings(self):
        """Test reading and writing plugin toggles in database."""
        database.set_setting("plugin_web_search", "True")
        database.set_setting("plugin_code_execution", "False")
        
        self.assertEqual(database.get_setting("plugin_web_search"), "True")
        self.assertEqual(database.get_setting("plugin_code_execution"), "False")
        
        # Restore defaults
        database.set_setting("plugin_web_search", "True")
        database.set_setting("plugin_code_execution", "True")

    def test_calculate_expression(self):
        """Test calculation and math execution."""
        res = plugin_manager.calculate_expression("2 ** 8 + sqrt(144)")
        self.assertIn("268", res)

    def test_system_stats(self):
        """Test retrieving system hardware and OS stats."""
        stats = plugin_manager.get_system_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn("os", stats)
        self.assertIn("timestamp", stats)

    def test_custom_plugin_loading(self):
        """Test discovering and executing custom plugin in plugins/."""
        custom_plugins = plugin_manager.load_custom_plugins()
        self.assertIn("random_picker_and_dice", custom_plugins)
        
        # Execute dice tool
        dice_res = plugin_manager.execute_tool_call("random_picker_and_dice", {"action": "dice"})
        self.assertIn("Rolled a 6-sided die", dice_res.get("result", ""))
        
        # Execute pick tool
        pick_res = plugin_manager.execute_tool_call("random_picker_and_dice", {"action": "pick", "options": "Apple, Banana"})
        self.assertIn("Randomly selected", pick_res.get("result", ""))

    def test_gemini_tool_declarations(self):
        """Test generating valid Gemini function declarations schema."""
        tools = ai_client.build_gemini_tools()
        self.assertTrue(len(tools) >= 1)
        
        # Check for Google Search tool
        has_search = any("google_search" in t for t in tools)
        self.assertTrue(has_search)
        
        # Check for Code Execution tool
        has_code = any("code_execution" in t for t in tools)
        self.assertTrue(has_code)
        
        # Check for Function declarations
        funcs_tool = next((t for t in tools if "function_declarations" in t), None)
        self.assertIsNotNone(funcs_tool)
        func_names = [f["name"] for f in funcs_tool["function_declarations"]]
        self.assertIn("launch_app_or_url", func_names)
        self.assertIn("email_manager", func_names)
        self.assertIn("canva_designer", func_names)
        self.assertIn("deep_search_researcher", func_names)

    def test_new_plugins(self):
        """Test Email, Canva, and Deep Search custom plugins."""
        custom_plugins = plugin_manager.load_custom_plugins()
        self.assertIn("email_manager", custom_plugins)
        self.assertIn("canva_designer", custom_plugins)
        self.assertIn("deep_search_researcher", custom_plugins)
        
        # Test email format
        email_res = plugin_manager.execute_tool_call("email_manager", {
            "action": "format_email",
            "to_email": "test@example.com",
            "subject": "Project Update",
            "body": "Here is the summary of today's progress."
        })
        self.assertIn("Formatted Email Ready", email_res.get("result", ""))
        
        # Test Canva launcher
        canva_res = plugin_manager.execute_tool_call("canva_designer", {
            "design_type": "presentation",
            "topic_or_query": "AI Pitch Deck"
        })
        self.assertIn("Canva Project Initialized", canva_res.get("result", ""))
        
        # Test Deep Search
        deep_res = plugin_manager.execute_tool_call("deep_search_researcher", {
            "query": "Quantum Computing",
            "research_focus": "qubits overview"
        })
        self.assertIn("Deep Search Multi-Angle Investigation", deep_res.get("result", ""))

    def test_offline_plugins_no_api_key(self):
        """Test Calculator, File Compressor, and Chart Generator plugins."""
        custom_plugins = plugin_manager.load_custom_plugins()
        self.assertIn("calculator", custom_plugins)
        self.assertIn("file_compressor", custom_plugins)
        self.assertIn("chart_generator", custom_plugins)

        # 1. Test Calculator
        calc_res = plugin_manager.execute_tool_call("calculator", {
            "expression": "sqrt(256) + 2**5"
        })
        self.assertIn("48", str(calc_res.get("result", "")))

        # 2. Test Unit Conversion
        conv_res = plugin_manager.execute_tool_call("calculator", {
            "expression": "100 km to miles",
            "operation_type": "unit_convert"
        })
        self.assertIn("miles", str(conv_res.get("result", "")).lower())

        # 3. Test File Compressor
        test_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_dummy.txt")
        with open(test_file, "w") as f:
            f.write("Hello Nexa AI File Compressor Test!")
        
        zip_dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_dummy.zip")
        if os.path.exists(zip_dest):
            os.remove(zip_dest)

        compress_res = plugin_manager.execute_tool_call("file_compressor", {
            "action": "compress",
            "source_path": test_file,
            "destination_path": zip_dest
        })
        self.assertIn("Compression Successful", str(compress_res.get("result", "")))
        self.assertTrue(os.path.exists(zip_dest))

        # Test archive inspection
        list_res = plugin_manager.execute_tool_call("file_compressor", {
            "action": "list",
            "source_path": zip_dest
        })
        self.assertIn("test_dummy.txt", str(list_res.get("result", "")))

        # Clean up test files
        if os.path.exists(test_file):
            os.remove(test_file)
        if os.path.exists(zip_dest):
            os.remove(zip_dest)

        # 4. Test Chart Generator
        chart_res = plugin_manager.execute_tool_call("chart_generator", {
            "chart_type": "bar",
            "title": "Quarterly Sales Test",
            "data_x": "Q1, Q2, Q3, Q4",
            "data_y": "150, 220, 310, 450",
            "open_image": False
        })
        self.assertIn("Chart Generated Successfully", str(chart_res.get("result", "")))

if __name__ == "__main__":
    unittest.main()

