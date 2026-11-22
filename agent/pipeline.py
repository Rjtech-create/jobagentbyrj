from . import db, jobs, matcher


def add_and_score(profile, job_list):
    """Score and store jobs; duplicates are skipped. Returns (added, duplicates)."""
    added = dup = 0
    for j in job_list:
        if not j.get("title"):
            continue
        score, matched, missing = matcher.score_job(profile, j)
        if db.add_job(j, score, matched, missing):
            added += 1
        else:
            dup += 1
    return added, dup


def search_and_score(profile):
    """Run Adzuna search for every (role x location). Returns (added, dup, errors)."""
    prefs = profile.get("prefs", {})
    roles = prefs.get("target_roles") or ["data analyst"]
    locs = prefs.get("locations") or [""]
    added = dup = 0
    errors = []
    for role in roles:
        for loc in locs:
            found, err = jobs.search_adzuna(role, loc)
            if err:
                errors.append(err)
            a, d = add_and_score(profile, found)
            added += a
            dup += d
    return added, dup, sorted(set(errors))


def rescore_all(profile):
    n = 0
    for j in db.get_jobs():
        s, m, x = matcher.score_job(profile, j)
        db.update_score(j["id"], s, m, x)
        n += 1
    return n
