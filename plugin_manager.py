import os
import sys
import json
import logging
import math
import datetime
import importlib.util
import subprocess
import webbrowser
import requests
from database import get_setting

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("plugin_manager")

PLUGINS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")

# Ensure plugins directory exists
os.makedirs(PLUGINS_DIR, exist_ok=True)

# ------------------------------------------------------------------------------
# Built-in Desktop & OS Automation Tools
# ------------------------------------------------------------------------------

def launch_app_or_url(target: str) -> str:
    """Launch a Windows application or open a URL in the default browser."""
    if not target or not isinstance(target, str):
        return "Error: Target application or URL was not specified."
    
    target = target.strip()
    
    # Check if URL
    if target.startswith("http://") or target.startswith("https://") or target.startswith("www."):
        url = target if target.startswith("http") else f"https://{target}"
        webbrowser.open(url)
        return f"Successfully opened web URL in browser: {url}"
    
    # Common app shortcuts for Windows
    common_apps = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "paint": "mspaint.exe",
        "explorer": "explorer.exe",
        "cmd": "cmd.exe",
        "terminal": "wt.exe",
        "powershell": "powershell.exe",
        "taskmgr": "taskmgr.exe",
        "control": "control.exe",
        "chrome": "chrome.exe",
        "edge": "msedge.exe",
        "code": "code",
        "spotify": "spotify.exe"
    }
    
    executable = common_apps.get(target.lower(), target)
    
    try:
        if sys.platform == "win32":
            try:
                os.startfile(executable)
                return f"Successfully launched '{target}' on Windows."
            except Exception:
                subprocess.Popen(executable, shell=True)
                return f"Successfully executed '{target}'."
        else:
            subprocess.Popen([executable])
            return f"Successfully started '{target}'."
    except Exception as e:
        logger.error(f"Failed to launch '{target}': {e}")
        return f"Error launching '{target}': {str(e)}"


def get_system_stats() -> dict:
    """Check computer system statistics including CPU, RAM, Disk, and Platform details."""
    stats = {
        "os": sys.platform,
        "python_version": sys.version.split()[0],
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        import psutil
        stats["cpu_percent"] = f"{psutil.cpu_percent(interval=0.2)}%"
        stats["cpu_cores_physical"] = psutil.cpu_count(logical=False)
        stats["cpu_cores_logical"] = psutil.cpu_count(logical=True)
        
        vm = psutil.virtual_memory()
        stats["ram_total_gb"] = round(vm.total / (1024**3), 2)
        stats["ram_used_gb"] = round(vm.used / (1024**3), 2)
        stats["ram_percent"] = f"{vm.percent}%"
        
        disk = psutil.disk_usage('/')
        stats["disk_total_gb"] = round(disk.total / (1024**3), 2)
        stats["disk_free_gb"] = round(disk.free / (1024**3), 2)
        stats["disk_used_percent"] = f"{disk.percent}%"
        
        battery = psutil.sensors_battery()
        if battery:
            stats["battery_percent"] = f"{battery.percent}%"
            stats["battery_plugged"] = battery.power_plugged
    except ImportError:
        stats["note"] = "psutil library not installed. Showing basic system stats."
    except Exception as e:
        stats["error"] = str(e)
        
    return stats


def manage_clipboard(action: str, text: str = "") -> str:
    """Read from or write text to the system clipboard."""
    action = action.lower().strip()
    
    if action in ("write", "copy", "set"):
        if not text:
            return "Error: No text provided to copy to clipboard."
        try:
            import pyperclip
            pyperclip.copy(text)
            return f"Successfully copied {len(text)} characters to clipboard."
        except ImportError:
            # Fallback on Windows via PowerShell
            if sys.platform == "win32":
                try:
                    subprocess.run(["powershell", "-command", f"Set-Clipboard -Value @'\n{text}\n'@"], check=True)
                    return f"Successfully copied {len(text)} characters to clipboard."
                except Exception as e:
                    return f"Failed to set clipboard: {e}"
            return "Error: pyperclip not installed."
        except Exception as e:
            return f"Error setting clipboard: {str(e)}"
            
    elif action in ("read", "get", "paste"):
        try:
            import pyperclip
            content = pyperclip.paste()
            return f"Clipboard Content:\n{content}"
        except ImportError:
            if sys.platform == "win32":
                try:
                    res = subprocess.run(["powershell", "-command", "Get-Clipboard"], capture_output=True, text=True, check=True)
                    return f"Clipboard Content:\n{res.stdout}"
                except Exception as e:
                    return f"Failed to read clipboard: {e}"
            return "Error: pyperclip not installed."
        except Exception as e:
            return f"Error reading clipboard: {str(e)}"
    else:
        return f"Unknown clipboard action '{action}'. Use 'read' or 'write'."


def read_local_file(file_path: str, max_chars: int = 4000) -> str:
    """Read contents of a local file safely."""
    if not file_path or not isinstance(file_path, str):
        return "Error: file_path must be specified."
        
    # Expand user directory ~
    expanded_path = os.path.expanduser(file_path.strip().strip('"').strip("'"))
    
    if not os.path.exists(expanded_path):
        return f"Error: File does not exist at '{expanded_path}'."
    if not os.path.isfile(expanded_path):
        return f"Error: Path '{expanded_path}' is not a file."
        
    try:
        with open(expanded_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_chars)
            total_size = os.path.getsize(expanded_path)
            trunc_note = f"\n\n[...Truncated: showing first {max_chars} chars of {total_size} bytes file...]" if total_size > max_chars else ""
            return f"File Content ({expanded_path}):\n\n```\n{content}\n```{trunc_note}"
    except Exception as e:
        return f"Error reading file '{expanded_path}': {str(e)}"


# ------------------------------------------------------------------------------
# Built-in Productivity & Utility Tools
# ------------------------------------------------------------------------------

def get_live_weather(city: str) -> str:
    """Fetch current weather and forecast for any city in the world."""
    if not city or not isinstance(city, str):
        city = "London"
        
    city_clean = city.strip()
    try:
        url = f"https://wttr.in/{city_clean}?format=j1"
        res = requests.get(url, timeout=8, headers={"User-Agent": "curl/7.68.0"})
        if res.status_code == 200:
            data = res.json()
            curr = data.get("current_condition", [{}])[0]
            temp_c = curr.get("temp_C", "N/A")
            temp_f = curr.get("temp_F", "N/A")
            desc = curr.get("weatherDesc", [{}])[0].get("value", "N/A")
            humidity = curr.get("humidity", "N/A")
            wind_kph = curr.get("windspeedKmph", "N/A")
            feels_like_c = curr.get("FeelsLikeC", "N/A")
            
            output = (
                f"🌤️ **Weather in {city_clean.title()}:**\n"
                f"- **Condition:** {desc}\n"
                f"- **Temperature:** {temp_c}°C ({temp_f}°F) | Feels like {feels_like_c}°C\n"
                f"- **Humidity:** {humidity}%\n"
                f"- **Wind Speed:** {wind_kph} km/h"
            )
            return output
        else:
            return f"Unable to fetch weather for '{city_clean}'. (HTTP {res.status_code})"
    except Exception as e:
        logger.error(f"Weather fetch error: {e}")
        return f"Weather service error: {str(e)}"


def calculate_expression(expression: str) -> str:
    """Safely calculate mathematical expressions or unit conversions."""
    if not expression or not isinstance(expression, str):
        return "Error: No expression provided."
        
    # Build safe math environment
    allowed_names = {
        "abs": abs, "round": round, "min": min, "max": max, "sum": sum, "pow": pow,
        "math": math, "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "sqrt": math.sqrt, "log": math.log, "log10": math.log10, "exp": math.exp,
        "pi": math.pi, "e": math.e, "radians": math.radians, "degrees": math.degrees
    }
    
    clean_expr = expression.strip()
    try:
        result = eval(clean_expr, {"__builtins__": {}}, allowed_names)
        return f"Calculation Result:\n`{clean_expr}` = **{result}**"
    except Exception as e:
        return f"Error evaluating expression `{clean_expr}`: {str(e)}"


def fetch_url_content(url: str, max_chars: int = 4000) -> str:
    """Scrape and extract readable text from a webpage URL."""
    if not url or not isinstance(url, str):
        return "Error: URL is missing."
        
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"https://{url}"
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code != 200:
            return f"Error: Failed to fetch URL (HTTP {res.status_code})."
            
        import re
        html = res.text
        # Strip script and style tags
        html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Strip all HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        # Clean whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)
        
        truncated = clean_text[:max_chars]
        note = f"\n\n[...Truncated to first {max_chars} chars...]" if len(clean_text) > max_chars else ""
        return f"Webpage Content from {url}:\n\n{truncated}{note}"
    except Exception as e:
        logger.error(f"URL scraper error for {url}: {e}")
        return f"Error fetching webpage {url}: {str(e)}"


# ------------------------------------------------------------------------------
# Dynamic Custom Plugin Loader (Scans `plugins/` directory)
# ------------------------------------------------------------------------------

def load_custom_plugins() -> dict:
    """
    Scans the `plugins/` folder for custom `.py` plugins.
    Each plugin can expose:
      - `PLUGIN_NAME`: str
      - `PLUGIN_DESCRIPTION`: str
      - `PLUGIN_SCHEMA`: dict (Gemini function declaration schema)
      - `run(**kwargs)`: callable that returns str
    """
    custom_plugins = {}
    if not os.path.exists(PLUGINS_DIR):
        return custom_plugins
        
    for file_name in os.listdir(PLUGINS_DIR):
        if file_name.endswith(".py") and not file_name.startswith("__"):
            file_path = os.path.join(PLUGINS_DIR, file_name)
            module_name = file_name[:-3]
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                
                # Check for single or multiple tools
                if hasattr(mod, "PLUGIN_SCHEMA") and hasattr(mod, "run"):
                    schema = getattr(mod, "PLUGIN_SCHEMA")
                    func_name = schema.get("name", module_name)
                    custom_plugins[func_name] = {
                        "schema": schema,
                        "handler": getattr(mod, "run"),
                        "file": file_name
                    }
                    logger.info(f"Loaded custom plugin: {func_name} from {file_name}")
                elif hasattr(mod, "PLUGINS") and isinstance(mod.PLUGINS, list):
                    for p in mod.PLUGINS:
                        func_name = p["schema"]["name"]
                        custom_plugins[func_name] = {
                            "schema": p["schema"],
                            "handler": p["handler"],
                            "file": file_name
                        }
                        logger.info(f"Loaded custom plugin tool: {func_name} from {file_name}")
            except Exception as e:
                logger.error(f"Failed to load custom plugin {file_name}: {e}")
                
    return custom_plugins


# ------------------------------------------------------------------------------
# Gemini Function Declarations Generator & Dispatcher
# ------------------------------------------------------------------------------

def get_active_function_declarations() -> list:
    """Build the list of Gemini Function Declarations based on enabled settings."""
    declarations = []
    
    desktop_enabled = get_setting("plugin_desktop_tools", "True") == "True"
    prod_enabled = get_setting("plugin_productivity", "True") == "True"
    custom_enabled = get_setting("plugin_custom_dir", "True") == "True"
    
    if desktop_enabled:
        declarations.extend([
            {
                "name": "launch_app_or_url",
                "description": "Launch a Windows application (e.g. notepad, calc, chrome, spotify, vs code) or open any URL in the user's default browser.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "target": {
                            "type": "STRING",
                            "description": "The application name (e.g. 'notepad', 'calc', 'chrome') or full URL (e.g. 'https://github.com')."
                        }
                    },
                    "required": ["target"]
                }
            },
            {
                "name": "get_system_stats",
                "description": "Get real-time CPU, RAM, Disk, battery percentage, and operating system statistics of the user's computer.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {}
                }
            },
            {
                "name": "manage_clipboard",
                "description": "Read from or write/copy text directly to the user's Windows clipboard.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "action": {
                            "type": "STRING",
                            "description": "The action to perform: 'read' (to get current clipboard content) or 'write' (to copy text to clipboard)."
                        },
                        "text": {
                            "type": "STRING",
                            "description": "The text to copy to clipboard if action is 'write'."
                        }
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "read_local_file",
                "description": "Read the text or code content of a local file on the user's computer.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "file_path": {
                            "type": "STRING",
                            "description": "The path to the file to read (e.g. 'C:/Users/.../notes.txt' or '~/document.md')."
                        }
                    },
                    "required": ["file_path"]
                }
            }
        ])
        
    if prod_enabled:
        declarations.extend([
            {
                "name": "get_live_weather",
                "description": "Get current live weather condition, temperature, humidity, and wind speed for any city in the world.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "city": {
                            "type": "STRING",
                            "description": "City name (e.g. 'New York', 'Tokyo', 'London', 'Hyderabad')."
                        }
                    },
                    "required": ["city"]
                }
            },
            {
                "name": "calculate_expression",
                "description": "Perform mathematical evaluations, scientific calculations, or arithmetic formulas.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "expression": {
                            "type": "STRING",
                            "description": "Math expression (e.g. '2 ** 10', 'sqrt(144) + sin(pi/2)', '1500 * 0.18')."
                        }
                    },
                    "required": ["expression"]
                }
            },
            {
                "name": "fetch_url_content",
                "description": "Scrape and read full text content from an article or website link.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "url": {
                            "type": "STRING",
                            "description": "The webpage URL to scrape and read."
                        }
                    },
                    "required": ["url"]
                }
            }
        ])
        
    if custom_enabled:
        custom_plugins = load_custom_plugins()
        for p in custom_plugins.values():
            declarations.append(p["schema"])
            
    return declarations


def execute_tool_call(function_name: str, arguments: dict) -> dict:
    """
    Execute a local tool or custom plugin requested by Gemini and return standard response dict.
    """
    logger.info(f"Executing tool call: {function_name} with args: {arguments}")
    
    try:
        # Built-in Desktop Tools
        if function_name == "launch_app_or_url":
            res = launch_app_or_url(arguments.get("target", ""))
        elif function_name == "get_system_stats":
            res = get_system_stats()
        elif function_name == "manage_clipboard":
            res = manage_clipboard(arguments.get("action", "read"), arguments.get("text", ""))
        elif function_name == "read_local_file":
            res = read_local_file(arguments.get("file_path", ""))
            
        # Built-in Productivity Tools
        elif function_name == "get_live_weather":
            res = get_live_weather(arguments.get("city", ""))
        elif function_name == "calculate_expression":
            res = calculate_expression(arguments.get("expression", ""))
        elif function_name == "fetch_url_content":
            res = fetch_url_content(arguments.get("url", ""))
            
        # Custom Plugins
        else:
            custom_plugins = load_custom_plugins()
            if function_name in custom_plugins:
                handler = custom_plugins[function_name]["handler"]
                res = handler(**arguments)
            else:
                res = f"Error: Tool '{function_name}' is not recognized or has been disabled."
                
        # Format response for Gemini functionResponse
        if isinstance(res, (dict, list)):
            return {"result": res}
        else:
            return {"result": str(res)}
            
    except Exception as e:
        logger.error(f"Error executing tool '{function_name}': {e}")
        return {"error": str(e)}
