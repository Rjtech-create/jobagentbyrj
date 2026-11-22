import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from . import config


def _safe_name(text):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")[:40] or "job"


def _clean(text):
    # reportlab's built-in fonts only support Latin-1; replace the rest instead of crashing
    text = (text or "").replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2022", "-")
    return escape(text.encode("latin-1", "replace").decode("latin-1"))


def build_resume_pdf(profile, job_id, job_title=""):
    """Write a clean one-column ATS-friendly PDF. Returns the file path as a string."""
    path = config.get_resume_dir() / f"resume_{_safe_name(profile.get('name', 'me'))}_{_safe_name(job_title)}_{job_id[:6]}.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm,
                            title=f"{profile.get('name','Resume')} - Resume", author=profile.get("name", ""))
    name_s = ParagraphStyle("n", fontName="Helvetica-Bold", fontSize=20, leading=24, spaceAfter=2)
    contact_s = ParagraphStyle("c", fontName="Helvetica", fontSize=9.5, leading=12, textColor=colors.HexColor("#444444"))
    h_s = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=9, spaceAfter=2,
                         textColor=colors.HexColor("#1a3c6e"))
    body_s = ParagraphStyle("b", fontName="Helvetica", fontSize=10, leading=13.5)
    bullet_s = ParagraphStyle("bl", parent=body_s, leftIndent=10, bulletIndent=0)

    story = [Paragraph(_clean(profile.get("name") or "Your Name"), name_s)]
    contact = " | ".join(x for x in [profile.get("email"), profile.get("phone"), profile.get("location"), profile.get("linkedin")] if x)
    if contact:
        story.append(Paragraph(_clean(contact), contact_s))

    def section(title):
        story.append(Paragraph(title.upper(), h_s))
        story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#1a3c6e"), spaceAfter=3))

    if profile.get("summary"):
        section("Summary")
        story.append(Paragraph(_clean(profile["summary"]), body_s))
    if profile.get("skills"):
        section("Skills")
        story.append(Paragraph(_clean(", ".join(s.strip() for s in profile["skills"])), body_s))
    if profile.get("projects"):
        section("Projects")
        for p in profile["projects"]:
            head = f"<b>{_clean(p.get('name',''))}</b>" if p.get("name") else ""
            desc = _clean(p.get("description", ""))
            story.append(Paragraph(f"{head}{' - ' if head and desc else ''}{desc}", bullet_s, bulletText="-"))
    if profile.get("experience"):
        section("Experience")
        for e in profile["experience"]:
            story.append(Paragraph(_clean(e), bullet_s, bulletText="-"))
    if profile.get("education"):
        section("Education")
        for e in profile["education"]:
            story.append(Paragraph(_clean(e), bullet_s, bulletText="-"))
    story.append(Spacer(1, 2))
    doc.build(story)
    return str(path)
