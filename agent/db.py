import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

STATUSES = ["new", "matched", "tailored", "opened", "applied", "skipped"]


@contextmanager
def _conn():
    con = sqlite3.connect(config.get_db_path())
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init():
    with _conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT)")
        c.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, source TEXT, title TEXT, company TEXT, location TEXT,
            description TEXT, url TEXT, salary TEXT, score REAL DEFAULT 0,
            matched TEXT DEFAULT '[]', missing TEXT DEFAULT '[]',
            status TEXT DEFAULT 'new', resume_path TEXT, notes TEXT,
            created_at TEXT, updated_at TEXT, applied_at TEXT)"""
        )


def job_id(job):
    key = (job.get("url") or "") or f"{job.get('title','')}|{job.get('company','')}|{job.get('location','')}"
    return hashlib.sha1(key.strip().lower().encode()).hexdigest()[:16]


def save_profile(profile):
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO kv VALUES ('profile', ?)", (json.dumps(profile),))


def get_profile():
    with _conn() as c:
        row = c.execute("SELECT value FROM kv WHERE key='profile'").fetchone()
    if not row:
        return {}
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return {}


def add_job(job, score=0, matched=None, missing=None):
    """Insert a job. Returns True if new, False if it was already stored (duplicate)."""
    jid = job_id(job)
    with _conn() as c:
        cur = c.execute(
            """INSERT OR IGNORE INTO jobs (id, source, title, company, location, description, url,
            salary, score, matched, missing, status, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (jid, job.get("source", ""), job.get("title", ""), job.get("company", ""),
             job.get("location", ""), job.get("description", ""), job.get("url", ""),
             job.get("salary", ""), score, json.dumps(matched or []), json.dumps(missing or []),
             "new", _now(), _now()),
        )
        return cur.rowcount == 1


def update_score(jid, score, matched, missing):
    with _conn() as c:
        c.execute("UPDATE jobs SET score=?, matched=?, missing=?, updated_at=? WHERE id=?",
                  (score, json.dumps(matched), json.dumps(missing), _now(), jid))


def set_status(jid, status, resume_path=None):
    if status not in STATUSES:
        raise ValueError(f"bad status {status}")
    with _conn() as c:
        if resume_path is not None:
            c.execute("UPDATE jobs SET resume_path=? WHERE id=?", (resume_path, jid))
        applied = _now() if status == "applied" else None
        c.execute("UPDATE jobs SET status=?, updated_at=?, applied_at=COALESCE(?, applied_at) WHERE id=?",
                  (status, _now(), applied, jid))


def get_jobs(statuses=None, min_score=None):
    q, args = "SELECT * FROM jobs WHERE 1=1", []
    if statuses:
        q += f" AND status IN ({','.join('?' * len(statuses))})"
        args += list(statuses)
    if min_score is not None:
        q += " AND score >= ?"
        args.append(min_score)
    q += " ORDER BY score DESC, created_at DESC"
    with _conn() as c:
        rows = [dict(r) for r in c.execute(q, args).fetchall()]
    for r in rows:
        r["matched"] = json.loads(r["matched"] or "[]")
        r["missing"] = json.loads(r["missing"] or "[]")
    return rows


def applied_today():
    today = datetime.now(timezone.utc).date().isoformat()
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('applied','opened') AND substr(updated_at,1,10)=?",
                         (today,)).fetchone()[0]
