import json
import re
from google import genai
from google.genai import types
from . import config

def _get_key():
    return config.GEMINI_API_KEY

def available():
    return bool(_get_key())

def ask(prompt, system="", max_tokens=1500):
    """Return the model's text, or None if no key / any error."""
    if not available():
        return None
    try:
        client = genai.Client(api_key=_get_key())
        generation_config = types.GenerateContentConfig(
            system_instruction=system if system else None,
            max_output_tokens=max_tokens,
        )
        response = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=prompt,
            config=generation_config,
        )
        return response.text
    except Exception as e:
        print(f"[llm] call failed: {e}")
        return None

def ask_json(prompt, system="", max_tokens=1500):
    """Return parsed JSON dict/list from the model, or None."""
    text = ask(prompt, system=system, max_tokens=max_tokens)
    if not text:
        return None
    try:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE).strip()
        return json.loads(cleaned)
    except Exception as e:
        print(f"[llm] JSON parse failed: {e}")
        return None