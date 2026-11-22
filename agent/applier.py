"""Browser form prefill (Playwright). Runs as a SEPARATE PROCESS so it never blocks/crashes the app.

Default behaviour: open the job page, prefill what it can, upload the tailored resume,
then LEAVE THE BROWSER OPEN for you to review and press Submit yourself.
Auto-submit exists but is OFF by default and only works on whitelisted domains.

Run manually:  python -m agent.applier --url URL --resume file.pdf --profile profile.json [--auto-submit]
"""
import argparse
import json
import sys
from urllib.parse import urlparse

from . import config

FIELD_KEYS = [
    (("first name", "firstname", "given name"), lambda p: (p.get("name", "").split() or [""])[0]),
    (("last name", "lastname", "surname", "family name"), lambda p: " ".join(p.get("name", "").split()[1:])),
    (("full name", "your name", "applicant name", "candidate name"), lambda p: p.get("name", "")),
    (("email", "e-mail"), lambda p: p.get("email", "")),
    (("phone", "mobile", "contact number"), lambda p: p.get("phone", "")),
    (("linkedin",), lambda p: p.get("linkedin", "")),
    (("city", "location", "current location"), lambda p: p.get("location", "")),
]
SKIP_WORDS = ("password", "captcha", "otp", "salary", "ctc", "date of birth", "dob", "gender", "aadhaar", "pan ")


def domain_allowed(url):
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in config.AUTO_SUBMIT_ALLOWED_DOMAINS)


def _label_text(page, el):
    try:
        raw = el.evaluate(
            """e => [e.getAttribute('aria-label'), e.placeholder, e.name, e.id,
                     (e.labels && e.labels[0] ? e.labels[0].innerText : '')].filter(Boolean).join(' ')"""
        ) or ""
        return raw.lower().replace("_", " ").replace("-", " ")
    except Exception:
        return ""


def prefill(page, profile, resume_path):
    filled = []
    for el in page.query_selector_all("input:not([type=hidden]):not([type=file]):not([type=checkbox]):not([type=radio]), textarea"):
        try:
            if not el.is_visible() or not el.is_enabled() or el.input_value():
                continue
            label = _label_text(page, el)
            if any(w in label for w in SKIP_WORDS):
                continue
            for keys, getter in FIELD_KEYS:
                if any(k in label for k in keys):
                    val = getter(profile)
                    if val:
                        el.fill(val)
                        filled.append(label.strip()[:40])
                    break
        except Exception:
            continue
    uploaded = False
    for fi in page.query_selector_all("input[type=file]"):
        try:
            fi.set_input_files(resume_path)
            uploaded = True
            break
        except Exception:
            continue
    return filled, uploaded


def run(url, resume_path, profile, auto_submit=False):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Run: pip install playwright && playwright install chromium")
        return 2
    if auto_submit and not domain_allowed(url):
        print(f"Auto-submit is blocked for this site. Falling back to prefill-only (you press Submit).")
        auto_submit = False
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=False)
            page = browser.new_page()
        except Exception as e:
            print(f"Could not launch the browser. Run 'playwright install chromium' and try again: {e}")
            return 1
        try:
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
        except Exception as e:
            print(f"Could not open page: {e}")
            browser.close()
            return 1
        filled, uploaded = prefill(page, profile, resume_path)
        print(f"Prefilled {len(filled)} field(s); resume uploaded: {uploaded}")
        if auto_submit:
            try:
                btn = page.query_selector("button[type=submit], input[type=submit]")
                if btn:
                    btn.click()
                    page.wait_for_timeout(4000)
                    print("Submit clicked. Verify the confirmation page, then mark as applied.")
            except Exception as e:
                print(f"Auto-submit failed: {e}")
        else:
            print("Review the form in the browser window, fix anything, and press Submit yourself. Close the window when done.")
        try:
            page.wait_for_event("close", timeout=15 * 60 * 1000)
        except Exception:
            pass
        browser.close()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--resume", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--auto-submit", action="store_true")
    a = ap.parse_args()
    with open(a.profile, encoding="utf-8") as f:
        profile = json.load(f)
    sys.exit(run(a.url, a.resume, profile, a.auto_submit))


if __name__ == "__main__":
    main()
