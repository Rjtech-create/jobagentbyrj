"""Resume tailoring with a hard TRUTHFULNESS GUARD.

The tailored resume may only REORDER and REPHRASE what is already in the profile.
It can never add a skill the candidate did not list.
"""
from . import llm
from .skills import canonical, find_skills


def _allowed(profile):
    return {canonical(s) for s in profile.get("skills", [])}


def _is_truthful(text, profile):
    """True if every known skill mentioned in `text` is in the candidate's profile."""
    return all(s in _allowed(profile) for s in find_skills(text))


def _template_summary(profile, job, matched):
    skills = matched[:5] or [s for s in profile.get("skills", [])][:5]
    skill_txt = ", ".join(skills)
    role = job.get("title") or "this role"
    base = f"Motivated candidate with hands-on skills in {skill_txt}." if skill_txt else "Motivated candidate."
    return f"{base} Looking to contribute as a {role} and keep growing in data analysis."


def tailored_summary(profile, job, matched):
    out = llm.ask(
        "Write a 2-3 sentence professional resume summary for a candidate applying to the job below.\n"
        "STRICT RULES: use ONLY the facts in CANDIDATE. Do not mention any skill, tool, company, "
        "degree or number that is not in CANDIDATE. No first person. No buzzword padding.\n\n"
        f"CANDIDATE:\nSkills: {', '.join(profile.get('skills', []))}\nEducation: {'; '.join(profile.get('education', []))}\n"
        f"Experience: {'; '.join(profile.get('experience', []))}\n"
        f"Projects: {'; '.join(p.get('name','') + ' ' + p.get('description','') for p in profile.get('projects', []))}\n\n"
        f"JOB: {job.get('title','')} at {job.get('company','')}\n{job.get('description','')[:2500]}",
        system="You write honest, concise resume summaries and never invent facts.", max_tokens=300,
    )
    if out and _is_truthful(out, profile):
        return out.strip()
    return _template_summary(profile, job, matched)  # guard failed or no LLM


def tailor_profile(profile, job, matched):
    """Return a NEW profile dict optimized for this job. Original is never modified."""
    mset = {canonical(s) for s in matched}
    skills = sorted(profile.get("skills", []), key=lambda s: canonical(s) not in mset)  # stable: matched first

    def relevance(p):
        return -len(set(find_skills(f"{p.get('name','')} {p.get('description','')}")) & mset)

    projects = sorted(profile.get("projects", []), key=relevance)
    new = dict(profile)
    new["skills"] = skills
    new["projects"] = projects
    new["summary"] = tailored_summary(profile, job, matched)
    return new
