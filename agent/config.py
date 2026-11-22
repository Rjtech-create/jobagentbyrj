import os
from contextvars import ContextVar
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # dotenv is optional
    pass


def _setting(name, default=""):
    value = os.getenv(name, "")
    if value.strip():
        return value.strip()
    try:
        import streamlit as st
        value = st.secrets.get(name, default)
    except FileNotFoundError:
        value = default
    return str(value).strip()


APP_ENV = _setting("APP_ENV", "local").lower()
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RESUME_DIR = DATA_DIR / "resumes"
DB_PATH = DATA_DIR / "jobs.db"
_runtime_db_path = ContextVar("jobagent_db_path", default=None)
_runtime_resume_dir = ContextVar("jobagent_resume_dir", default=None)

if APP_ENV != "cloud":
    DATA_DIR.mkdir(exist_ok=True)
    RESUME_DIR.mkdir(parents=True, exist_ok=True)


def configure_runtime_storage(directory):
    directory = Path(directory)
    resume_dir = directory / "resumes"
    directory.mkdir(parents=True, exist_ok=True)
    resume_dir.mkdir(parents=True, exist_ok=True)
    _runtime_db_path.set(directory / "jobs.db")
    _runtime_resume_dir.set(resume_dir)


def get_db_path():
    return _runtime_db_path.get() or DB_PATH


def get_resume_dir():
    return _runtime_resume_dir.get() or RESUME_DIR

ANTHROPIC_API_KEY = _setting("ANTHROPIC_API_KEY")
GEMINI_API_KEY = _setting("GEMINI_API_KEY")
LLM_MODEL = _setting("LLM_MODEL", "gemini-3.1-flash-lite")
if LLM_MODEL == "gemini-2.5-flash":
    LLM_MODEL = "gemini-3.1-flash-lite"
ADZUNA_APP_ID = _setting("ADZUNA_APP_ID")
ADZUNA_APP_KEY = _setting("ADZUNA_APP_KEY")
ADZUNA_COUNTRY = _setting("ADZUNA_COUNTRY", "in") or "in"

try:
    MAX_APPLICATIONS_PER_DAY = int(_setting("MAX_APPLICATIONS_PER_DAY", "10"))
except ValueError:
    MAX_APPLICATIONS_PER_DAY = 10

# Auto-submit is only ever allowed on these domains (their terms permit applications
# through the standard form). Everything else is "prefill only, you click Submit".
AUTO_SUBMIT_ALLOWED_DOMAINS = ("greenhouse.io", "lever.co")
