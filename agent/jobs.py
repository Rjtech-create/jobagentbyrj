from urllib.parse import urlparse

import requests

from . import config

SAMPLE_JOBS = [
    {"source": "sample", "title": "Data Analyst", "company": "Acme Retail (sample)", "location": "Gurgaon",
     "url": "https://example.com/jobs/1", "salary": "",
     "description": "We need a Data Analyst with strong SQL, Excel and Power BI. Build dashboards, KPI reporting, data cleaning. Python (pandas) is a plus."},
    {"source": "sample", "title": "Junior Business Analyst", "company": "FinServe (sample)", "location": "Noida",
     "url": "https://example.com/jobs/2", "salary": "",
     "description": "Looking for a Business Analyst. Tableau, SQL, stakeholder communication, MIS reporting and Excel pivot tables required."},
    {"source": "sample", "title": "Machine Learning Engineer", "company": "DeepCo (sample)", "location": "Gurgaon",
     "url": "https://example.com/jobs/3", "salary": "",
     "description": "Deep learning, PyTorch, TensorFlow, AWS, Spark and strong Python required."},
    {"source": "sample", "title": "Data Analyst Intern", "company": "StartupX (sample)", "location": "Remote",
     "url": "https://example.com/jobs/4", "salary": "",
     "description": "Intern for data analysis: Python, pandas, matplotlib, Excel, exploratory data analysis and data visualization."},
]


def configured():
    return bool(config.ADZUNA_APP_ID and config.ADZUNA_APP_KEY)


def is_placeholder_url(url):
    host = (urlparse(url or "").hostname or "").lower()
    return host == "example.com" or host.endswith(".example.com")


def search_adzuna(query, location="", pages=1, per_page=20):
    """Return (jobs, error_message). Never raises."""
    if not configured():
        return [], "Adzuna keys missing. Add ADZUNA_APP_ID and ADZUNA_APP_KEY to your app secrets or .env file."
    jobs, err = [], ""
    for page in range(1, pages + 1):
        url = f"https://api.adzuna.com/v1/api/jobs/{config.ADZUNA_COUNTRY}/search/{page}"
        params = {"app_id": config.ADZUNA_APP_ID, "app_key": config.ADZUNA_APP_KEY,
                  "what": query, "results_per_page": per_page, "content-type": "application/json"}
        if location:
            params["where"] = location
        try:
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 401:
                return jobs, (
                    "Adzuna authentication failed (HTTP 401): the configured App ID/App Key pair was rejected. "
                    "Check both values in .env or generate a new pair in your Adzuna developer account."
                )
            if r.status_code == 403:
                return jobs, (
                    "Adzuna denied this request (HTTP 403). Check that the app is active and allowed to search "
                    f"the configured country ({config.ADZUNA_COUNTRY})."
                )
            if r.status_code == 429:
                return jobs, "Adzuna rate limit reached. Try again later."
            if not r.ok:
                return jobs, f"Adzuna returned HTTP {r.status_code}. Check your API access and try again."
            for it in r.json().get("results", []):
                sal = ""
                if it.get("salary_min"):
                    sal = f"{int(it['salary_min'])}-{int(it.get('salary_max') or it['salary_min'])}"
                jobs.append({
                    "source": "adzuna", "title": it.get("title", "").strip(),
                    "company": (it.get("company") or {}).get("display_name", ""),
                    "location": (it.get("location") or {}).get("display_name", ""),
                    "description": it.get("description", ""), "url": it.get("redirect_url", ""),
                    "salary": sal,
                })
        except ValueError:
            err = "Adzuna returned an unreadable response."
            break
        except requests.RequestException as e:
            err = f"Network/API error ({type(e).__name__}). Check your connection and try again."
            break
    return jobs, err
