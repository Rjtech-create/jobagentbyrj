# Job Application Agent

Upload your resume once. The app finds data analyst jobs, scores each against your skills,
writes a tailored resume PDF per job, prefills the application form, and tracks everything.
**You press Submit** (see "Why not 100% automatic").

## Setup (Windows / Mac / Linux)
```
python -m venv .venv
.venv\Scripts\activate          # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
copy .env.example .env          # Mac/Linux: cp .env.example .env
streamlit run app.py
```
Edit `.env`: add free Adzuna keys (developer.adzuna.com) for job search. The Gemini key is optional.
No keys at all? Use "Load demo jobs" to try everything.
If job search returns HTTP 401, the App ID/Key pair in `.env` was rejected; generate or copy a valid pair, then restart the app. A 403 usually means the app or selected country is not permitted.

## Deploy the existing app on Streamlit Community Cloud
1. Push this project folder to the GitHub repository you want to deploy. This project’s selected `jobagentbyrj` repository is public, so its source code will be visible to everyone. The `.gitignore` excludes `.env`, the local `data/` database/resumes, `.venv/`, and Streamlit secrets; do not force-add them.
2. In [Streamlit Community Cloud](https://share.streamlit.io/), choose **Create app**, select that repository and branch, and set the app file to `app.py`.
3. In **Advanced settings → Secrets**, paste [.streamlit/secrets.toml.example](./.streamlit/secrets.toml.example), then replace the blank API credentials with valid values. Keep actual credentials in Streamlit Cloud settings, never in Git:
   ```toml
   APP_ENV = "cloud"
   ADZUNA_COUNTRY = "in"
   MAX_APPLICATIONS_PER_DAY = 10
   GEMINI_API_KEY = ""
   ADZUNA_APP_ID = ""
   ADZUNA_APP_KEY = ""
   ```
   Gemini is optional. Adzuna credentials are required for live job search; without them, use demo jobs or add jobs manually. The existing Adzuna credentials were rejected with HTTP 401, so generate a valid pair before expecting live search to work.

The hosted app keeps each visitor's profile, tracker, and generated PDFs in separate temporary storage. Community Cloud may discard this data when the app restarts; download the tracker CSV and PDFs you need to keep. For durable or multi-device storage, connect a hosted database before using this for production. The hosted app cannot open a browser on your device, so use **Open job page** and **Download PDF**, then review and submit manually. Local use continues to support form prefill.

Choose the app's sharing visibility deliberately in Streamlit Community Cloud; a private GitHub repository does not automatically make the deployed app private.

## How to use
1. **Profile:** upload resume, check every field, Save.
2. **Find jobs:** Search (or add a job manually with its full description).
3. **Review & apply:** Tailor resume -> Open & prefill -> review in browser -> Submit -> "I applied".
4. **Tracker:** status of every job, CSV download.

## Safety built in
- Truthfulness guard: tailored resumes only reorder/rephrase skills YOU listed. A summary that mentions an unlisted skill is rejected and replaced.
- Duplicate jobs are skipped; daily limit (default 10) protects your accounts.
- Auto-submit is OFF in the UI. CLI-only flag `--auto-submit`, works only on greenhouse.io / lever.co.
- Never automates LinkedIn/Naukri/Indeed logins. Uses the Adzuna API instead of scraping.
- Every API/network/PDF failure shows a message instead of crashing.

## Why not 100% automatic
Job sites ban bots, many forms have CAPTCHAs and custom questions, and a wrong answer goes out under your name.

## Known limits (be honest in your viva)
- Adzuna returns short description snippets, so scores are estimates. Paste full JDs for jobs you like.
- Demo jobs use `example.com` placeholder URLs and cannot be applied to. Use real Adzuna results or add a job manually with its actual application URL.
- Form prefill uses label matching; it works on simple forms, not every site. Always review.
- Resume PDF is a clean single-column template (ATS friendly), not a copy of your original design.
- Run tests: `python -m pytest -q`
