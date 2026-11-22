"""Skill dictionary + matcher. Works offline, no API needed."""
import re

SKILLS = {
    "sql": ["sql", "mysql", "postgresql", "postgres", "sqlite", "sql server", "t-sql"],
    "python": ["python"],
    "excel": ["excel", "advanced excel", "vlookup", "xlookup", "pivot table", "pivot tables"],
    "power bi": ["power bi", "powerbi"],
    "tableau": ["tableau"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "matplotlib": ["matplotlib"],
    "seaborn": ["seaborn"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "statistics": ["statistics", "statistical analysis", "hypothesis testing", "regression"],
    "data visualization": ["data visualization", "data visualisation", "dashboard", "dashboards"],
    "data cleaning": ["data cleaning", "data cleansing", "data wrangling", "data preparation", "data preprocessing"],
    "eda": ["eda", "exploratory data analysis"],
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning"],
    "nlp": ["nlp", "natural language processing"],
    "power query": ["power query"],
    "dax": ["dax"],
    "etl": ["etl", "data pipeline", "data pipelines"],
    "data modeling": ["data modeling", "data modelling"],
    "google sheets": ["google sheets"],
    "looker studio": ["looker studio", "data studio"],
    "bigquery": ["bigquery"],
    "snowflake": ["snowflake"],
    "spark": ["spark", "pyspark"],
    "aws": ["aws"],
    "azure": ["azure"],
    "git": ["git", "github"],
    "r": ["r programming", "rstudio"],
    "a/b testing": ["a/b testing", "ab testing"],
    "kpi": ["kpi", "kpis"],
    "reporting": ["reporting", "mis reporting", "mis"],
    "business analysis": ["business analysis", "business analytics", "business intelligence"],
    "forecasting": ["forecasting", "time series"],
    "communication": ["communication", "stakeholder"],
    "streamlit": ["streamlit"],
    "flask": ["flask"],
    "django": ["django"],
}

_PATTERNS = {}
for canon, aliases in SKILLS.items():
    alt = "|".join(re.escape(a) for a in sorted(set(aliases + [canon]), key=len, reverse=True))
    _PATTERNS[canon] = re.compile(r"(?<![a-z0-9+#])(?:" + alt + r")(?![a-z0-9+#])", re.I)


def find_skills(text):
    """Return canonical skill names found in text (stable order)."""
    if not text:
        return []
    return [c for c, p in _PATTERNS.items() if p.search(text)]


def canonical(skill):
    """Map any alias ('Power BI', 'sklearn') to its canonical name, else lowercase it."""
    s = (skill or "").strip().lower()
    for c in find_skills(s):
        return c
    return s
