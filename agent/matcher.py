from .skills import canonical, find_skills


def score_job(profile, job):
    """Return (score 0-100, matched_skills, missing_skills). Deterministic and explainable.

    85% = share of the job's required skills that the candidate has
    15% = job title matches one of the target roles
    """
    text = f"{job.get('title','')} {job.get('description','')}"
    required = find_skills(text)
    have = {canonical(s) for s in profile.get("skills", [])}
    matched = [s for s in required if s in have]
    missing = [s for s in required if s not in have]
    skill_pct = (len(matched) / len(required)) if required else 0.0
    roles = [r.lower() for r in profile.get("prefs", {}).get("target_roles", []) if r.strip()]
    title = job.get("title", "").lower()
    title_hit = 1.0 if any(r in title or all(w in title for w in r.split()) for r in roles) else 0.0
    # a job with very few detectable skills is unreliable: cap its score
    cap = 100 if len(required) >= 3 else 60
    score = min(cap, round(85 * skill_pct + 15 * title_hit, 1))
    return score, matched, missing
