"""Job Application Agent - Streamlit UI.  Run:  streamlit run app.py"""
import json
import subprocess
import sys

import pandas as pd
import streamlit as st

from agent import config, db, jobs, llm, pdfgen, pipeline, resume, tailor

def _profile_widget_values(profile):
    prefs = profile.get("prefs", {})
    return {
        "profile_name": profile.get("name", ""),
        "profile_email": profile.get("email", ""),
        "profile_phone": profile.get("phone", ""),
        "profile_location": profile.get("location", ""),
        "profile_linkedin": profile.get("linkedin", ""),
        "profile_summary": profile.get("summary", ""),
        "profile_skills": ", ".join(profile.get("skills", [])),
        "profile_education": "\n".join(profile.get("education", [])),
        "profile_experience": "\n".join(profile.get("experience", [])),
        "profile_projects": resume.projects_to_text(profile.get("projects", [])),
        "profile_target_roles": ", ".join(prefs.get("target_roles", [])),
        "profile_locations": ", ".join(prefs.get("locations", [])),
        "profile_min_score": int(prefs.get("min_score", 50)),
    }


st.set_page_config(page_title="Job Application Agent", page_icon="💼", layout="wide")
db.init()

if "profile" not in st.session_state:
    st.session_state.profile = db.get_profile() or json.loads(json.dumps(resume.EMPTY_PROFILE))
profile = st.session_state.profile
profile.setdefault("prefs", dict(resume.EMPTY_PROFILE["prefs"]))
for widget_key, value in _profile_widget_values(profile).items():
    st.session_state.setdefault(widget_key, value)

st.title("💼 Job Application Agent")
c1, c2, c3 = st.columns(3)
c1.caption(f"AI writing: {'ON' if llm.available() else 'OFF (offline mode)'}")
c2.caption(f"Job search API: {'credentials set (checked on search)' if jobs.configured() else 'keys missing'}")
c3.caption(f"Applications today: {db.applied_today()} / {config.MAX_APPLICATIONS_PER_DAY}")

t1, t2, t3, t4 = st.tabs(["1. Profile", "2. Find jobs", "3. Review & apply", "4. Tracker"])

# ---------------- 1. PROFILE ----------------
with t1:
    up = st.file_uploader("Upload your resume (PDF or TXT)", type=["pdf", "txt"])
    if up and st.button("Read my resume", key="read_resume"):
        try:
            with st.spinner("Reading resume..."):
                text = resume.extract_text(up.getvalue(), up.name)
                parsed = resume.parse_profile(text)
                parsed["prefs"] = profile.get("prefs", parsed["prefs"])
                st.session_state.profile = parsed
                for widget_key, value in _profile_widget_values(parsed).items():
                    st.session_state[widget_key] = value
                db.save_profile(parsed)
            st.success("Resume read. Check every field below, fix mistakes, then press Save.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    st.subheader("Your details (edit anything)")
    a, b = st.columns(2)
    name = a.text_input("Full name", key="profile_name")
    email = b.text_input("Email", key="profile_email")
    phone = a.text_input("Phone", key="profile_phone")
    location = b.text_input("Your city", key="profile_location")
    linkedin = a.text_input("LinkedIn URL", key="profile_linkedin")
    summary = st.text_area("Summary", key="profile_summary", height=80)
    skills = st.text_area("Skills (comma separated). ONLY list skills you really have.", key="profile_skills")
    education = st.text_area("Education (one per line)", key="profile_education")
    experience = st.text_area("Experience / internships (one per line)", key="profile_experience")
    projects = st.text_area("Projects (one per line as  Name: what you did)", key="profile_projects")
    st.subheader("What jobs do you want?")
    roles = st.text_input("Target roles (comma separated)", key="profile_target_roles")
    locs = st.text_input("Cities (comma separated, blank = anywhere)", key="profile_locations")
    min_score = st.slider("Minimum match score to show", 0, 100, key="profile_min_score")

    if st.button("💾 Save profile", type="primary", key="save_profile"):
        new = {"name": name, "email": email, "phone": phone, "location": location, "linkedin": linkedin,
               "summary": summary, "skills": resume.split_csv(skills), "education": resume.split_lines(education),
               "experience": resume.split_lines(experience), "projects": resume.text_to_projects(projects),
               "prefs": {"target_roles": resume.split_csv(roles), "locations": resume.split_csv(locs), "min_score": min_score}}
        problems = []
        if not new["name"]:
            problems.append("name")
        if not new["email"] or "@" not in new["email"]:
            problems.append("a valid email")
        if not new["skills"]:
            problems.append("at least one skill")
        if problems:
            st.error("Please add: " + ", ".join(problems))
        else:
            st.session_state.profile = new
            profile = new
            db.save_profile(new)
            st.success(f"Saved. Re-scored {pipeline.rescore_all(new)} stored job(s).")

# ---------------- 2. FIND JOBS ----------------
with t2:
    ready = bool(profile.get("skills") and profile.get("name"))
    if not ready:
        st.info("Complete and save your profile in tab 1 first.")
    else:
        if st.button("🔎 Search jobs now", type="primary", disabled=not jobs.configured()):
            with st.spinner("Searching..."):
                added, dup, errs = pipeline.search_and_score(profile)
            st.success(f"Added {added} new job(s). {dup} duplicate(s) skipped.")
            for e in errs:
                st.warning(e)
        if not jobs.configured():
            st.caption("Automatic search needs free Adzuna keys in app secrets or your .env file (see README). You can still add jobs manually or load the demo jobs.")
        if st.button("Load demo jobs (no keys needed)"):
            a, d = pipeline.add_and_score(profile, jobs.SAMPLE_JOBS)
            st.success(f"Added {a} demo job(s).")
        with st.expander("➕ Add a job manually (paste the full description for best matching)"):
            mt = st.text_input("Job title", key="mt")
            mc = st.text_input("Company", key="mc")
            ml = st.text_input("Location", key="ml")
            mu = st.text_input("Application URL", key="mu")
            md = st.text_area("Full job description", key="md", height=160)
            if st.button("Add job"):
                if not (mt and md):
                    st.error("Title and description are required.")
                else:
                    a, d = pipeline.add_and_score(profile, [{"source": "manual", "title": mt, "company": mc, "location": ml, "url": mu, "description": md}])
                    st.success("Added." if a else "That job is already in your list.")
        st.caption("Note: job APIs often return only a short description snippet, so scores are estimates. For jobs you like, paste the full description with the manual form.")

# ---------------- 3. REVIEW & APPLY ----------------
with t3:
    min_s = profile.get("prefs", {}).get("min_score", 50)
    todo = db.get_jobs(statuses=["new", "tailored", "opened"], min_score=min_s)
    st.write(f"{len(todo)} job(s) at or above your minimum score ({min_s}).")
    left = config.MAX_APPLICATIONS_PER_DAY - db.applied_today()
    for j in todo:
        with st.expander(f"{j['score']:.0f}%  |  {j['title']}  -  {j['company']}  ({j['location']})  [{j['status']}]"):
            st.write(f"**You have:** {', '.join(j['matched']) or '-'}")
            st.write(f"**Job wants (you don't list):** {', '.join(j['missing']) or '-'}")
            st.caption(j["description"][:700] + ("..." if len(j["description"]) > 700 else ""))
            job_url = (j.get("url") or "").strip()
            can_open_job = bool(job_url) and not jobs.is_placeholder_url(job_url)
            if can_open_job:
                st.link_button("Open job page", job_url)
            elif job_url:
                st.caption("Demo listing only: example.com is a placeholder, not a real job or application page.")
            else:
                st.caption("No application link is available for this job.")
            k = j["id"]
            b1, b2, b3, b4 = st.columns(4)
            if b1.button("1) Tailor resume", key=f"t{k}"):
                try:
                    tp = tailor.tailor_profile(profile, j, j["matched"])
                    path = pdfgen.build_resume_pdf(tp, k, j["title"])
                    db.set_status(k, "tailored", resume_path=path)
                    st.success("Tailored resume created.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not create resume: {e}")
            if j.get("resume_path"):
                try:
                    with open(j["resume_path"], "rb") as f:
                        b2.download_button("Download PDF", f.read(), file_name=j["resume_path"].split("/")[-1].split("\\")[-1],
                                           mime="application/pdf", key=f"d{k}")
                except OSError:
                    b2.caption("PDF missing - tailor again")
                if b3.button("2) Open & prefill form", key=f"o{k}", disabled=not can_open_job or config.APP_ENV == "cloud"):
                    if left <= 0:
                        st.error("Daily limit reached. This protects your accounts. Try again tomorrow.")
                    else:
                        pf = config.DATA_DIR / "_apply_profile.json"
                        try:
                            pf.write_text(json.dumps(profile), encoding="utf-8")
                            subprocess.Popen([sys.executable, "-m", "agent.applier", "--url", job_url,
                                              "--resume", j["resume_path"], "--profile", str(pf)], cwd=str(config.BASE_DIR))
                        except OSError as e:
                            st.error(f"Could not start the browser helper: {e}")
                        else:
                            db.set_status(k, "opened")
                            st.info("A browser window is opening. Review the form and press Submit yourself.")
                if config.APP_ENV == "cloud":
                    st.caption("The hosted app cannot open a browser on your device. Use Open job page and Download PDF, then submit manually.")
            if b4.button("✅ I applied", key=f"a{k}"):
                db.set_status(k, "applied")
                st.rerun()
            if st.button("Skip this job", key=f"s{k}"):
                db.set_status(k, "skipped")
                st.rerun()

# ---------------- 4. TRACKER ----------------
with t4:
    allj = db.get_jobs()
    if not allj:
        st.info("No jobs yet.")
    else:
        df = pd.DataFrame(allj)[["title", "company", "location", "score", "status", "applied_at", "url"]]
        st.dataframe(df, width="stretch")
        st.bar_chart(df["status"].value_counts())
        st.download_button("Download tracker (CSV)", df.to_csv(index=False).encode(), "applications.csv", "text/csv")
