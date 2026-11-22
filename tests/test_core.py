"""Run:  python -m pytest -q     (or)     python tests/test_core.py"""
import sys, tempfile
from contextvars import Context
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent import config

_tmp = Path(tempfile.mkdtemp())
config.DB_PATH = _tmp / "t.db"
config.RESUME_DIR = _tmp

from agent import applier, db, jobs, llm, matcher, pdfgen, pipeline, resume, tailor  # noqa: E402
from agent.skills import canonical, find_skills  # noqa: E402

RESUME = """Rupak Sharma
rupak@example.com | +91 98765 43210 | linkedin.com/in/rupak-s
Skills: SQL, Python (pandas), Excel, Power BI
Projects: Sales dashboard - built Power BI dashboard from SQL data
Education: BCA, NGF College
"""


def profile():
    p = resume._heuristic_profile(RESUME)
    p["prefs"]["target_roles"] = ["data analyst"]
    p["projects"] = [{"name": "Chat bot", "description": "simple python bot"},
                     {"name": "Sales dashboard", "description": "Power BI dashboard on SQL data"}]
    p["education"] = ["BCA, NGF College"]
    return p


def test_find_skills_boundaries():
    assert "sql" in find_skills("Strong SQL needed")
    assert "r" not in find_skills("our team")           # no false positive for single letter R
    assert "python" not in find_skills("pythonic")      # word boundary
    assert canonical("Power BI") == "power bi" and canonical("sklearn") == "scikit-learn"


def test_heuristic_resume():
    p = resume._heuristic_profile(RESUME)
    assert p["email"] == "rupak@example.com" and "sql" in p["skills"] and p["phone"]


def test_heuristic_resume_extracts_sections():
    text = """Rupak Sharma
rupak@example.com | +91 98765 43210
Location: Gurgaon
Professional Summary
Data analyst experienced in building business dashboards.
Technical Skills: SQL, Python (pandas), Excel, Power BI
Work Experience
Data Analyst Intern, Acme, 2024
Created monthly sales reports.
Education
BCA, NGF College, 2023
Projects
Sales dashboard: Built a dashboard using SQL and Power BI.
"""
    p = resume._heuristic_profile(text)
    assert p["name"] == "Rupak Sharma"
    assert p["location"] == "Gurgaon"
    assert "business dashboards" in p["summary"]
    assert p["experience"] == ["Data Analyst Intern, Acme, 2024", "Created monthly sales reports."]
    assert p["education"] == ["BCA, NGF College, 2023"]
    assert p["projects"] == [{"name": "Sales dashboard", "description": "Built a dashboard using SQL and Power BI."}]


def test_resume_parser_uses_full_text_and_llm_results():
    long_resume = RESUME + "\n" + ("Additional resume details. " * 1000)
    with patch.object(llm, "ask_json", return_value={"summary": "Parsed summary", "experience": ["Parsed role"]}) as ask:
        p = resume.parse_profile(long_resume)
    assert ask.call_args.args[0].endswith(long_resume)
    assert p["summary"] == "Parsed summary" and p["experience"] == ["Parsed role"]


def test_llm_uses_configured_model():
    class Models:
        def generate_content(self, **kwargs):
            self.kwargs = kwargs
            return type("Response", (), {"text": "generated"})()

    class Client:
        def __init__(self, api_key):
            self.models = Models()

    with patch.object(config, "GEMINI_API_KEY", "test-key"), \
            patch.object(config, "LLM_MODEL", "gemini-test-model"), \
            patch.object(llm.genai, "Client", Client):
        assert llm.ask("prompt") == "generated"


def test_llm_parses_fenced_json():
    with patch.object(llm, "ask", return_value='```json\n{"name": "Rupak"}\n```'):
        assert llm.ask_json("prompt") == {"name": "Rupak"}


def test_pdf_text_extraction_errors():
    try:
        resume.extract_text(b"junk", "x.docx"); assert False
    except ValueError:
        pass
    try:
        resume.extract_text(b"%PDF-1.4 not really", "x.pdf"); assert False
    except ValueError:
        pass


def test_scoring_good_vs_bad_job():
    p = profile()
    good, m, x = matcher.score_job(p, jobs.SAMPLE_JOBS[0])
    bad, _, _ = matcher.score_job(p, jobs.SAMPLE_JOBS[2])
    assert good > 60 and "sql" in m and good > bad
    assert bad < 40
    s, _, _ = matcher.score_job(p, {"title": "Data Analyst", "description": "Join us!"})
    assert s <= 60                                      # no detectable skills -> capped


def test_tailor_never_adds_skills():
    p = profile()
    job = {"title": "Data Analyst", "company": "X", "description": "SQL Tableau Spark AWS"}
    t = tailor.tailor_profile(p, job, ["sql"])
    assert {canonical(s) for s in t["skills"]} == {canonical(s) for s in p["skills"]}
    assert "tableau" not in t["summary"].lower() and "spark" not in t["summary"].lower()
    assert canonical(t["skills"][0]) == "sql"           # matched skill moved first
    assert t["projects"][0]["name"] == "Sales dashboard"  # relevant project first
    assert p["skills"] == resume._heuristic_profile(RESUME)["skills"]  # original untouched


def test_guard_rejects_lying_summary():
    p = profile()
    assert tailor._is_truthful("Expert in SQL and Excel.", p)
    assert not tailor._is_truthful("Expert in SQL and Tableau.", p)


def test_pdf_generation_with_odd_characters():
    p = profile(); p["name"] = "Rupak \u2013 R\u00e9sum\u00e9 <b>&</b> \u4e2d"; p["summary"] = "Uses SQL & Excel \u2022 great"
    path = pdfgen.build_resume_pdf(p, "abcdef123456", "Data/Analyst: Sr.")
    assert Path(path).exists() and Path(path).stat().st_size > 1000
    from pypdf import PdfReader
    assert "SQL" in PdfReader(path).pages[0].extract_text()


def test_db_dedupe_and_status():
    db.init()
    j = dict(jobs.SAMPLE_JOBS[0])
    assert db.add_job(j, 80) is True and db.add_job(j, 80) is False
    jid = db.job_id(j)
    db.set_status(jid, "applied")
    assert db.get_jobs(statuses=["applied"])[0]["id"] == jid and db.applied_today() >= 1
    try:
        db.set_status(jid, "bogus"); assert False
    except ValueError:
        pass


def test_pipeline_and_profile_roundtrip():
    p = profile(); db.init(); db.save_profile(p)
    assert db.get_profile()["email"] == p["email"]
    a, d = pipeline.add_and_score(p, jobs.SAMPLE_JOBS)
    assert a + d == len(jobs.SAMPLE_JOBS)
    assert pipeline.rescore_all(p) >= 1


def test_runtime_storage_is_isolated_between_sessions():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        first = Context()
        second = Context()
        first_dir = root / "first"
        second_dir = root / "second"
        first.run(config.configure_runtime_storage, first_dir)
        first.run(db.init)
        first.run(db.save_profile, {"name": "First visitor"})
        second.run(config.configure_runtime_storage, second_dir)
        second.run(db.init)
        assert first.run(db.get_profile)["name"] == "First visitor"
        assert second.run(db.get_profile) == {}
        assert first.run(config.get_resume_dir) != second.run(config.get_resume_dir)


def test_search_without_keys_is_safe():
    config.ADZUNA_APP_ID = config.ADZUNA_APP_KEY = ""
    found, err = jobs.search_adzuna("data analyst")
    assert found == [] and "keys" in err.lower()


def test_adzuna_401_explains_credentials_rejection():
    class Response:
        status_code = 401
        ok = False

    with patch.object(config, "ADZUNA_APP_ID", "test-id"), \
            patch.object(config, "ADZUNA_APP_KEY", "test-key"), \
            patch.object(jobs.requests, "get", return_value=Response()):
        found, err = jobs.search_adzuna("data analyst")
    assert found == []
    assert "HTTP 401" in err and "App ID/App Key pair was rejected" in err
    assert "test-key" not in err


def test_example_domain_is_not_a_real_job_link():
    assert jobs.is_placeholder_url("https://example.com/jobs/1")
    assert jobs.is_placeholder_url("https://careers.example.com/jobs/1")
    assert not jobs.is_placeholder_url("https://boards.greenhouse.io/acme/jobs/1")
    assert not jobs.is_placeholder_url("https://example.com.attacker.test/jobs/1")


def test_autosubmit_domain_whitelist():
    assert applier.domain_allowed("https://boards.greenhouse.io/acme/jobs/1")
    assert applier.domain_allowed("https://jobs.lever.co/acme/1")
    assert not applier.domain_allowed("https://www.linkedin.com/jobs/view/1")
    assert not applier.domain_allowed("https://evil-greenhouse.io.attacker.com/x")


def test_text_helpers():
    assert resume.split_csv("a, b\nc") == ["a", "b", "c"]
    assert resume.text_to_projects("Bot: does x")[0] == {"name": "Bot", "description": "does x"}


def test_uploading_new_resume_refreshes_profile_widgets():
    from streamlit.testing.v1 import AppTest

    db.init()
    old = resume._heuristic_profile(RESUME)
    old["prefs"] = {"target_roles": ["data analyst"], "locations": ["Mumbai"], "min_score": 55}
    db.save_profile(old)
    updated = {
        "name": "New Candidate",
        "email": "new@example.com",
        "phone": "9876543210",
        "location": "Delhi",
        "linkedin": "",
        "summary": "New summary",
        "skills": ["Python", "SQL"],
        "education": ["New degree"],
        "experience": ["New role"],
        "projects": [{"name": "New project", "description": "New description"}],
        "prefs": {"target_roles": ["product analyst"], "locations": ["Delhi"], "min_score": 70},
    }
    app_path = Path(__file__).resolve().parent.parent / "app.py"
    with patch.object(resume, "parse_profile", return_value=updated):
        app = AppTest.from_file(str(app_path)).run(timeout=20)
        app.file_uploader[0].upload("new_resume.txt", b"Resume content that is long enough to parse.")
        app.run()
        app.button(key="read_resume").click().run()
    assert not app.exception
    assert app.text_input(key="profile_name").value == "New Candidate"
    assert app.text_input(key="profile_email").value == "new@example.com"
    assert app.text_input(key="profile_phone").value == "9876543210"
    assert app.text_input(key="profile_location").value == "Delhi"
    assert app.text_input(key="profile_linkedin").value == ""
    assert app.text_area(key="profile_summary").value == "New summary"
    assert app.text_area(key="profile_skills").value == "Python, SQL"
    assert app.text_area(key="profile_education").value == "New degree"
    assert app.text_area(key="profile_experience").value == "New role"
    assert app.text_area(key="profile_projects").value == "New project: New description"
    assert app.text_input(key="profile_target_roles").value == "data analyst"
    assert app.text_input(key="profile_locations").value == "Mumbai"
    assert app.slider(key="profile_min_score").value == 55
    assert db.get_profile()["name"] == "New Candidate"


def test_app_runs_in_cloud_mode():
    from streamlit.testing.v1 import AppTest

    app_path = Path(__file__).resolve().parent.parent / "app.py"
    with patch.object(config, "APP_ENV", "cloud"):
        app = AppTest.from_file(str(app_path)).run(timeout=20)
    assert not app.exception
    assert any("temporary storage" in element.value for element in app.info)


if __name__ == "__main__":
    fails = 0
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            try:
                f(); print("PASS", n)
            except Exception as e:
                fails += 1; print("FAIL", n, repr(e))
    sys.exit(1 if fails else 0)
