import os
import requests
import json
import base64
import mimetypes
import logging
from database import get_setting

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_client")

def encode_image_to_base64(image_path):
    """Load image file and encode to base64 string with its mime type."""
    if not image_path or not os.path.exists(image_path):
        return None, None
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        ext = os.path.splitext(image_path)[1].lower()
        if ext in ('.jpg', '.jpeg'):
            mime_type = 'image/jpeg'
        elif ext == '.png':
            mime_type = 'image/png'
        elif ext == '.webp':
            mime_type = 'image/webp'
        else:
            mime_type = 'image/png'
    try:
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
            return encoded, mime_type
    except Exception as e:
        logger.error(f"Failed to read image {image_path}: {e}")
        return None, None

def get_ai_client_config():
    """Load AI configurations from database settings."""
    provider = get_setting("api_provider", "gemini").lower()
    api_key = get_setting("api_key", "").strip()
    # Strip newlines and spaces in case user accidentally copied console log lines
    api_key = api_key.replace("\n", "").replace("\r", "").replace(" ", "")
    model_name = get_setting("model_name", "").strip()
    
    # Normalize model names
    if provider == "gemini":
        if not model_name or model_name in ("gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash", "gemini-1.5-flash-lite", "gemini", ""):
            model_name = "gemini-3.6-flash"
    elif provider == "openai":
        if not model_name:
            model_name = "gpt-4o-mini"
    elif provider == "groq":
        if not model_name or model_name in ("llama-3.1-8b-instant", "llama3-8b-8192", "llama3-70b-8192", "mixtral-8x7b-32768", ""):
            model_name = "openai/gpt-oss-20b"
            
    return provider, api_key, model_name

SYSTEM_PROMPT = (
    "You are Nexa AI, a premier, highly intelligent desktop visual and multi-modal assistant. "
    "You have powerful capabilities to understand, analyze, and explain diverse input modalities: "
    "1. High-Resolution Screen Captures & Images (anime/cartoon characters, diagrams, UI layouts, landscapes, objects, screenshots).\n"
    "2. Attached Documents (PDF, DOCX, TXT, Markdown, CSV, Excel spreadsheets).\n"
    "3. Code Files (.py, .js, .html, .css, .cpp, .java, .sql, etc.) — provide expert debugging, optimization, and line-by-line analysis.\n"
    "4. Video Storyboards & Audio Transcripts.\n"
    "5. Webpage Analysis & URLs.\n\n"
    "Guidelines for your response:\n"
    "- Provide clear, concise, accurate, and structured answers.\n"
    "- When visual images or screen captures are provided, identify everything shown accurately.\n"
    "- Use clean Markdown formatting, bullet points, bold key terms, and highlighted syntax code blocks."
)

def build_gemini_tools():
    """Build the list of tools for Gemini API including Search, Code Execution, and Function Declarations."""
    import plugin_manager
    tools = []
    
    # 1. Google Search Grounding (if enabled)
    if get_setting("plugin_web_search", "True") == "True":
        tools.append({"google_search": {}})
        
    # 2. Code Execution (if enabled)
    if get_setting("plugin_code_execution", "True") == "True":
        tools.append({"code_execution": {}})
        
    # 3. Custom & Built-in Function Declarations from plugin manager
    decls = plugin_manager.get_active_function_declarations()
    if decls:
        tools.append({"function_declarations": decls})
        
    return tools

def query_gemini(api_key, model, messages, retry_fallback=True):
    """Call Google Gemini REST API with multi-modal image support and autonomous backend tool execution."""
    import plugin_manager
    if not model or model in ("gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash", "gemini-1.5-flash-lite", "gemini", ""):
        model = "gemini-3.6-flash"
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    contents = []
    
    system_instruction = {
        "parts": [{"text": SYSTEM_PROMPT}]
    }
    
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        parts = []
        
        # Attach image inline if present
        img_path = msg.get("screenshot_path")
        if img_path and role == "user":
            img_b64, mime_type = encode_image_to_base64(img_path)
            if img_b64:
                parts.append({
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": img_b64
                    }
                })
                
        parts.append({"text": msg.get("text", "")})
        contents.append({
            "role": role,
            "parts": parts
        })
        
    tools_list = build_gemini_tools()
    
    payload = {
        "contents": contents,
        "systemInstruction": system_instruction,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096
        }
    }
    
    if tools_list:
        payload["tools"] = tools_list
    
    logger.info(f"Querying Gemini API model {model} (Multimodal with Backend Orchestration)")
    
    # Loop to allow autonomous tool calls (up to 4 iterations)
    max_tool_iterations = 4
    for iteration in range(max_tool_iterations):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45)
            
            # Handle tool combination conflict fallback if needed
            if response.status_code == 400 and "tools" in payload and iteration == 0:
                logger.warning("Retrying Gemini query with function declarations only (excluding search/code combo)...")
                decls = plugin_manager.get_active_function_declarations()
                payload["tools"] = [{"function_declarations": decls}] if decls else []
                if not payload["tools"]:
                    payload.pop("tools", None)
                response = requests.post(url, headers=headers, json=payload, timeout=45)
            
            if response.status_code == 200:
                res_json = response.json()
                candidates = res_json.get("candidates", [])
                if not candidates:
                    return "Error: No response generated from Gemini API."
                    
                candidate = candidates[0]
                parts = candidate.get("content", {}).get("parts", [])
                
                # Check for Function Call from Gemini
                has_function_call = False
                for p in parts:
                    if "functionCall" in p or "function_call" in p:
                        fc = p.get("functionCall") or p.get("function_call")
                        func_name = fc.get("name", "")
                        func_args = fc.get("args", {})
                        
                        logger.info(f"Gemini requested tool execution: '{func_name}' with args: {func_args}")
                        
                        # Execute the tool on the backend controller
                        tool_output = plugin_manager.execute_tool_call(func_name, func_args)
                        
                        # Append the model's tool call turn to contents
                        contents.append({
                            "role": "model",
                            "parts": [p]
                        })
                        
                        # Append the function response turn to contents
                        contents.append({
                            "role": "user",
                            "parts": [{
                                "functionResponse": {
                                    "name": func_name,
                                    "response": tool_output
                                }
                            }]
                        })
                        
                        payload["contents"] = contents
                        has_function_call = True
                        break # Process tool call and continue loop
                        
                if has_function_call:
                    continue
                    
                # If no function call, collect final text response
                final_text_parts = [p.get("text", "") for p in parts if "text" in p]
                final_text = "".join(final_text_parts).strip()
                
                if not final_text:
                    final_text = "Task processed successfully."
                    
                return final_text
                
            elif response.status_code == 404 and retry_fallback and model != "gemini-3.5-flash-lite":
                logger.warning(f"Model '{model}' returned 404. Retrying with 'gemini-3.5-flash-lite'...")
                return query_gemini(api_key, "gemini-3.5-flash-lite", messages, retry_fallback=False)
            elif response.status_code == 429 and retry_fallback and model != "gemini-3.5-flash-lite":
                logger.warning(f"Model '{model}' hit 429 Rate Limit. Retrying with high-throughput 'gemini-3.5-flash-lite'...")
                return query_gemini(api_key, "gemini-3.5-flash-lite", messages, retry_fallback=False)
            else:
                logger.error(f"Gemini API error {response.status_code}: {response.text}")
                try:
                    err_data = response.json()
                    err_msg = err_data.get("error", {}).get("message", response.text)
                    if response.status_code == 429:
                        return f"**Gemini Rate Limit Exceeded (429):** {err_msg}\n\n*Solution:* Google Free Tier has request and daily quota limits. Switch to **`gemini-3.5-flash-lite`** in Settings for maximum daily capacity, or use a Groq API key."
                    return f"**Gemini API Error ({response.status_code}):** {err_msg}\n\n*Tip: Check that your API key is active in [Google AI Studio](https://aistudio.google.com).* "
                except Exception:
                    return f"Error: Gemini API error {response.status_code}. {response.text}"
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error querying Gemini: {e}")
            return f"**Network Error:** Could not connect to Gemini API ({e}). Check your internet connection."
            
    return "Task reached maximum tool calling depth without final text output."

def query_openai(api_key, model, messages):
    """Call OpenAI REST API with multimodal image support."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    formatted_messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]
    
    for msg in messages:
        role = "user" if msg["role"] == "user" else "assistant"
        img_path = msg.get("screenshot_path")
        
        if img_path and role == "user":
            img_b64, mime_type = encode_image_to_base64(img_path)
            if img_b64:
                content = [
                    {"type": "text", "text": msg.get("text", "")},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{img_b64}"
                        }
                    }
                ]
            else:
                content = msg.get("text", "")
        else:
            content = msg.get("text", "")
            
        formatted_messages.append({
            "role": role,
            "content": content
        })
        
    payload = {
        "model": model,
        "messages": formatted_messages,
        "temperature": 0.7
    }
    
    logger.info(f"Querying OpenAI API model {model} (Multimodal)")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        
        if response.status_code == 200:
            res_json = response.json()
            try:
                return res_json["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                logger.error(f"Failed to parse OpenAI response: {e}. Response: {res_json}")
                return "Error: Unexpected response format from OpenAI API."
        else:
            logger.error(f"OpenAI API returned error code {response.status_code}: {response.text}")
            return f"Error: OpenAI API error {response.status_code}. {response.text}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error querying OpenAI: {e}")
        return f"**Network Error:** Could not connect to OpenAI API ({e})."

def query_groq(api_key, model, messages):
    """Call Groq REST API."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    formatted_messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]
    
    for msg in messages:
        role = "user" if msg["role"] == "user" else "assistant"
        formatted_messages.append({
            "role": role,
            "content": msg.get("text", "")
        })
        
    payload = {
        "model": model,
        "messages": formatted_messages,
        "temperature": 0.7
    }
    
    logger.info(f"Querying Groq API model {model}")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=35)
        
        if response.status_code == 200:
            res_json = response.json()
            try:
                return res_json["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                logger.error(f"Failed to parse Groq response: {e}. Response: {res_json}")
                return "Error: Unexpected response format from Groq API."
        else:
            logger.error(f"Groq API returned error code {response.status_code}: {response.text}")
            return f"Error: Groq API error {response.status_code}. {response.text}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error querying Groq: {e}")
        return f"**Network Error:** Could not connect to Groq API ({e})."

def generate_response(session_messages):
    """Unified entry point to generate response based on configured provider."""
    provider, api_key, model = get_ai_client_config()
    
    if not api_key:
        return (
            "⚠️ **API Key Missing!**\n\n"
            "Please click **⚙️ Settings** in the sidebar or tray menu and enter your API Key to enable Nexa AI.\n\n"
            "- For **Google Gemini** (Recommended, Free): Get a key at [Google AI Studio](https://aistudio.google.com)\n"
            "- For **Groq** (Fast Free Tier): Get a key at [Groq Cloud](https://console.groq.com)\n"
            "- For **OpenAI**: Get a key at [OpenAI Platform](https://platform.openai.com)"
        )
        
    if provider == "gemini":
        return query_gemini(api_key, model, session_messages)
    elif provider == "openai":
        return query_openai(api_key, model, session_messages)
    elif provider == "groq":
        return query_groq(api_key, model, session_messages)
    else:
        return f"Error: Unsupported provider '{provider}'."

# Alias for backward compatibility
send_chat_history = generate_response


def generate_project_capsule(messages: list) -> dict:
    """
    Distill conversation history into a structured Project Capsule JSON.
    Extracts goals, tech stack, completed tasks, decisions, code refs, and next steps.
    """
    import re
    import datetime
    
    if not messages:
        return {
            "project": "New Project",
            "goal": "Project discussion",
            "technology": [],
            "completed_work": [],
            "current_status": "Starting new session",
            "important_decisions": [],
            "code_references": [],
            "next_steps": [],
            "conversation_summary": "Empty conversation.",
            "created_at": datetime.datetime.now().isoformat(),
            "nexa_capsule_version": "1.0"
        }
        
    provider, api_key, model = get_ai_client_config()
    
    capsule_prompt = (
        "Analyze the entire previous conversation history and synthesize it into a structured 'Project & Conversation Capsule' JSON object.\n"
        "Return ONLY a valid, parseable JSON object with no markdown fences, no conversational preamble, following this exact schema:\n\n"
        "{\n"
        '  "project": "Title or topic of the project/task",\n'
        '  "goal": "Core objective and goal",\n'
        '  "technology": ["list", "of", "technologies", "libraries", "tools"],\n'
        '  "completed_work": ["list", "of", "tasks", "or", "milestones", "completed"],\n'
        '  "current_status": "Current problem, bug, or exact state of the project",\n'
        '  "important_decisions": ["list", "of", "key", "architectural", "or", "design", "decisions"],\n'
        '  "code_references": ["key file paths, functions, or components mentioned"],\n'
        '  "next_steps": ["list", "of", "immediate", "next", "actions", "to", "take"],\n'
        '  "conversation_summary": "Concise 2-3 sentence overview of this chat."\n'
        "}"
    )
    
    analysis_messages = list(messages) + [{"role": "user", "text": capsule_prompt}]
    
    try:
        if api_key and provider == "gemini":
            raw_res = query_gemini(api_key, model, analysis_messages)
        elif api_key and provider == "openai":
            raw_res = query_openai(api_key, model, analysis_messages)
        elif api_key and provider == "groq":
            raw_res = query_groq(api_key, model, analysis_messages)
        else:
            raw_res = ""
            
        clean_json = raw_res.strip()
        if clean_json.startswith("```"):
            clean_json = re.sub(r'^```(?:json)?\s*', '', clean_json)
            clean_json = re.sub(r'\s*```$', '', clean_json)
            
        data = json.loads(clean_json)
        data["created_at"] = datetime.datetime.now().isoformat()
        data["nexa_capsule_version"] = "1.0"
        return data
    except Exception as e:
        logger.warning(f"Failed to generate capsule with AI, using heuristic fallback: {e}")
        first_user_msg = next((m.get("text", "") for m in messages if m.get("role") == "user"), "General Project")
        return {
            "project": first_user_msg[:40] + ("..." if len(first_user_msg) > 40 else ""),
            "goal": "Continue previous project discussion",
            "technology": ["Python", "Nexa AI"],
            "completed_work": [f"Discussed {len(messages)} interaction turns"],
            "current_status": "Context saved for next session",
            "important_decisions": [],
            "code_references": [],
            "next_steps": ["Resume discussion in new session"],
            "conversation_summary": f"Previous conversation containing {len(messages)} messages.",
            "created_at": datetime.datetime.now().isoformat(),
            "nexa_capsule_version": "1.0"
        }

