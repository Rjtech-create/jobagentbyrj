import io
import re

from . import llm
from .skills import find_skills

EMPTY_PROFILE = {
    "name": "", "email": "", "phone": "", "location": "", "linkedin": "", "summary": "",
    "skills": [], "education": [], "experience": [], "projects": [],
    "prefs": {"target_roles": ["data analyst"], "locations": [], "min_score": 50},
}

_SECTION_ALIASES = {
    "summary": {"summary", "profile", "professional summary", "career summary", "objective", "career objective", "about me"},
    "skills": {"skills", "technical skills", "core skills", "key skills", "competencies", "core competencies", "technical expertise"},
    "education": {"education", "academic background", "educational background", "qualifications"},
    "experience": {"experience", "work experience", "professional experience", "employment history", "work history", "internships"},
    "projects": {"projects", "personal projects", "academic projects", "key projects", "project experience"},
}
_HEADING_LOOKUP = {alias: section for section, aliases in _SECTION_ALIASES.items() for alias in aliases}


def extract_text(data: bytes, filename: str) -> str:
    """Get text from a PDF / TXT resume. Raises ValueError with a clear message on failure."""
    name = filename.lower()
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        text = ""
        try:
            try:
                import fitz  # PyMuPDF
                with fitz.open(stream=data, filetype="pdf") as doc:
                    text = "\n".join(page.get_text() for page in doc)
            except ImportError:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(data))
                text = "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as e:
            raise ValueError(f"Could not read this PDF ({e}). Try exporting it again or upload a .txt.")
        if len(text.strip()) < 50:
            raise ValueError("No text found in the PDF. It may be a scanned image. Upload a text-based PDF or a .txt file.")
        return text
    raise ValueError("Only .pdf and .txt resumes are supported.")


def _heuristic_profile(text):
    p = {k: (list(v) if isinstance(v, list) else (dict(v) if isinstance(v, dict) else v)) for k, v in EMPTY_PROFILE.items()}
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    def normalized_heading(line):
        return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", line.lower())).strip()

    sections = {section: [] for section in _SECTION_ALIASES}
    current_section = None
    for line in lines:
        clean = re.sub(r"^[\s•*\-\u2022]+", "", line).strip()
        section = _HEADING_LOOKUP.get(normalized_heading(clean))
        if section:
            current_section = section
            continue
        inline = re.match(r"^([^:]{2,45})\s*:\s*(.+)$", clean)
        if inline:
            inline_section = _HEADING_LOOKUP.get(normalized_heading(inline.group(1)))
            if inline_section:
                current_section = inline_section
                sections[current_section].append(inline.group(2).strip())
                continue
        if current_section:
            sections[current_section].append(clean)

    for line in lines:
        candidate = re.sub(r"^[\s•*\-\u2022]+", "", line).strip()
        labeled_name = re.match(r"(?i)^(?:full\s+)?name\s*:\s*(.+)$", candidate)
        if labeled_name:
            p["name"] = labeled_name.group(1).strip()[:60]
            break
        if (candidate and not re.search(
                r"@|linkedin\.com|(?:\+?91[\s-]?)?[6-9]\d{4}|\b(?:location|city|based in|email|phone|mobile|address)\s*:",
                candidate, re.I)
                and normalized_heading(candidate) not in _HEADING_LOOKUP
                and normalized_heading(candidate) not in {"resume", "curriculum vitae", "cv"}):
            p["name"] = candidate[:60]
            break
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    if m:
        p["email"] = m.group(0)
    m = re.search(r"(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}", text)
    if m:
        p["phone"] = m.group(0).strip()
    m = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+/?", text, re.I)
    if m:
        p["linkedin"] = m.group(0)
    m = re.search(r"(?im)^\s*(?:location|city|based in)\s*[:\-]\s*(.+?)\s*$", text)
    if m:
        p["location"] = m.group(1).strip()
    p["skills"] = find_skills(text)
    for field in ("summary", "education", "experience"):
        if sections[field]:
            p[field] = " ".join(sections[field]) if field == "summary" else sections[field]
    projects = []
    for line in sections["projects"]:
        parts = re.split(r"\s*[:\u2013\u2014]\s*|\s+-\s+", line, maxsplit=1)
        if len(parts) == 2:
            projects.append({"name": parts[0].strip(), "description": parts[1].strip()})
        else:
            projects.append({"name": "", "description": line.strip()})
    p["projects"] = projects
    return p


def parse_profile(text):
    """Structured profile from resume text. Uses the LLM when available, else heuristics."""
    base = _heuristic_profile(text)
    data = llm.ask_json(
        "Extract this resume into JSON with keys: name, email, phone, location, linkedin, summary, "
        "skills (list of strings), education (list of strings), experience (list of strings), "
        "projects (list of objects with name and description). Use ONLY information present in the "
        "resume. Use empty strings/lists for anything missing. Return JSON only.\n\nRESUME:\n" + text,
        system="You extract structured data from resumes. You never invent facts.",
    )
    if not isinstance(data, dict):
        return base
    for key in ("name", "email", "phone", "location", "linkedin", "summary"):
        if isinstance(data.get(key), str) and data[key].strip():
            base[key] = data[key].strip()
    for key in ("skills", "education", "experience"):
        if isinstance(data.get(key), list):
            vals = [str(x).strip() for x in data[key] if str(x).strip()]
            if vals:
                base[key] = vals
    if isinstance(data.get("projects"), list):
        projs = []
        for pr in data["projects"]:
            if isinstance(pr, dict) and (pr.get("name") or pr.get("description")):
                projs.append({"name": str(pr.get("name", "")).strip(), "description": str(pr.get("description", "")).strip()})
        if projs:
            base["projects"] = projs
    # keep dictionary-detected skills the LLM may have missed (they ARE in the resume text)
    have = {s.lower() for s in base["skills"]}
    base["skills"] += [s for s in find_skills(text) if s.lower() not in have]
    return base


# ---- helpers for the editable text boxes in the UI ----
def split_csv(s):
    return [x.strip() for x in re.split(r"[,\n]", s or "") if x.strip()]


def split_lines(s):
    return [x.strip() for x in (s or "").splitlines() if x.strip()]


def projects_to_text(projects):
    return "\n".join(f"{p.get('name','')}: {p.get('description','')}".strip(": ") for p in projects or [])


def text_to_projects(s):
    out = []
    for line in split_lines(s):
        name, _, desc = line.partition(":")
        out.append({"name": name.strip(), "description": desc.strip()} if desc else {"name": "", "description": name.strip()})
    return out
