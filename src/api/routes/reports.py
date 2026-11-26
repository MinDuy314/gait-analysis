import html
import re
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.auth.dependencies import get_current_user, verify_subject_access
from src.api.schemas.api_responses import ReportResponse
from src.api.schemas.requests import ReportRequest
from src.assessment.assessment_engine import AssessmentEngine
from src.assessment.assessment_schema import AssessmentContext
from src.database.models import AssessmentRecord, ReportRecord, User
from src.database.repositories import SessionRepository, SubjectRepository
from src.reporting.individual_report import generate_individual_report
from src.reporting.professional_report import generate_professional_report
from src.reporting.report_renderer import ReportRenderer
import uuid
from datetime import datetime

router = APIRouter(tags=["reports"])


@router.post("/api/v1/sessions/{session_id}/reports", response_model=ReportResponse, status_code=201)
def generate_report(
    session_id: str,
    payload: ReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sess = SessionRepository(db).get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    subj = SubjectRepository(db).get(sess.subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subj, current_user)
    if payload.report_type == "professional" and current_user.role == "individual":
        raise HTTPException(status_code=403, detail="Patients cannot generate clinician reports")

    assessment_record = db.query(AssessmentRecord).filter(
        AssessmentRecord.session_id == session_id
    ).order_by(AssessmentRecord.created_at.desc()).first()

    if assessment_record and assessment_record.assessment_data:
        from src.assessment.assessment_schema import GaitAssessment
        assessment = GaitAssessment.model_validate(assessment_record.assessment_data)
    else:
        ctx = AssessmentContext(
            subject_id=sess.subject_id,
            session_id=session_id,
            camera_view=sess.camera_view,
            walking_speed_ms=sess.walking_speed_ms,
        )
        engine = AssessmentEngine()
        assessment = engine.assess(context=ctx, features={})

    renderer = ReportRenderer()
    if payload.report_type == "individual":
        report = generate_individual_report(assessment)
    elif payload.report_type == "professional":
        report = generate_professional_report(assessment)
    else:
        raise HTTPException(status_code=400, detail="report_type must be 'individual' or 'professional'")

    file_path = renderer.save(report)

    record = ReportRecord(
        id=report.report_id,
        subject_id=sess.subject_id,
        session_id=session_id,
        report_type=payload.report_type,
        assessment_id=assessment.assessment_id,
        file_path=str(file_path),
        status="generated",
        generated_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/api/v1/reports/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = db.query(ReportRecord).filter(ReportRecord.id == report_id, ReportRecord.is_deleted == False).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    subj = SubjectRepository(db).get(r.subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subj, current_user)
    if r.report_type == "professional" and current_user.role == "individual":
        raise HTTPException(status_code=403, detail="Patients cannot access clinician reports")
    return r


def _markdown_to_html(md_text: str, report_type: str) -> str:
    """Render markdown report content into a clean, standalone, viewable HTML document."""
    escaped_lines = []
    in_table = False
    in_list = False

    for line in md_text.splitlines():
        trimmed = line.strip()
        if not trimmed:
            if in_list:
                escaped_lines.append("</ul>")
                in_list = False
            if in_table:
                escaped_lines.append("</table>")
                in_table = False
            continue

        if trimmed.startswith("---"):
            if in_list:
                escaped_lines.append("</ul>")
                in_list = False
            if in_table:
                escaped_lines.append("</table>")
                in_table = False
            escaped_lines.append("<hr/>")
            continue

        if trimmed.startswith("# "):
            escaped_lines.append(f"<h1>{html.escape(trimmed[2:])}</h1>")
            continue
        if trimmed.startswith("## "):
            escaped_lines.append(f"<h2>{html.escape(trimmed[3:])}</h2>")
            continue
        if trimmed.startswith("### "):
            escaped_lines.append(f"<h3>{html.escape(trimmed[4:])}</h3>")
            continue

        if trimmed.startswith("- "):
            if in_table:
                escaped_lines.append("</table>")
                in_table = False
            if not in_list:
                escaped_lines.append("<ul>")
                in_list = True
            item_text = html.escape(trimmed[2:])
            item_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', item_text)
            item_text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', item_text)
            escaped_lines.append(f"<li>{item_text}</li>")
            continue

        if trimmed.startswith("|") and trimmed.endswith("|"):
            if in_list:
                escaped_lines.append("</ul>")
                in_list = False
            # Check for header separator e.g. |---|---|
            stripped_border = trimmed.replace("|", "").replace("-", "").strip()
            if not stripped_border:
                continue
            cells = [c.strip() for c in trimmed.split("|")[1:-1]]
            tag = "th" if not in_table else "td"
            if not in_table:
                escaped_lines.append("<table>")
                in_table = True
            row_html = "".join(f"<{tag}>{html.escape(c)}</{tag}>" for c in cells)
            escaped_lines.append(f"<tr>{row_html}</tr>")
            continue

        if in_list:
            escaped_lines.append("</ul>")
            in_list = False
        if in_table:
            escaped_lines.append("</table>")
            in_table = False

        para_text = html.escape(trimmed)
        para_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', para_text)
        para_text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', para_text)
        escaped_lines.append(f"<p>{para_text}</p>")

    if in_list:
        escaped_lines.append("</ul>")
    if in_table:
        escaped_lines.append("</table>")

    body_content = "\n".join(escaped_lines)
    title = f"{report_type.capitalize()} Gait Analysis Report"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{title}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
h1 {{ color: #0f172a; border-bottom: 2px solid #0d9488; padding-bottom: 8px; font-size: 24px; }}
h2 {{ color: #134e4a; margin-top: 24px; font-size: 18px; }}
h3 {{ color: #334155; font-size: 15px; margin-top: 16px; }}
table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px; }}
th, td {{ border: 1px solid #cbd5e1; padding: 8px 12px; text-align: left; }}
th {{ background-color: #f8fafc; font-weight: 600; color: #0f172a; }}
ul {{ padding-left: 20px; }}
li {{ margin-bottom: 4px; }}
p {{ margin: 8px 0; font-size: 14px; }}
hr {{ border: 0; border-top: 1px solid #e2e8f0; margin: 24px 0; }}
strong {{ color: #0f172a; }}
</style>
</head>
<body>
{body_content}
</body>
</html>"""


@router.get("/api/v1/reports/{report_id}/download")
def download_report(
    report_id: str,
    format: str = Query("md", pattern="^(md|html)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = db.query(ReportRecord).filter(ReportRecord.id == report_id, ReportRecord.is_deleted == False).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    subj = SubjectRepository(db).get(r.subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subj, current_user)
    if r.report_type == "professional" and current_user.role == "individual":
        raise HTTPException(status_code=403, detail="Patients cannot download clinician reports")
    if not r.file_path or not Path(r.file_path).exists():
        raise HTTPException(status_code=404, detail="Report file not found on disk")

    path_obj = Path(r.file_path)
    if path_obj.stat().st_size == 0:
        raise HTTPException(status_code=500, detail="Report file is empty")

    content_md = path_obj.read_text(encoding="utf-8")

    if format.lower() == "html":
        html_content = _markdown_to_html(content_md, r.report_type)
        return Response(
            content=html_content,
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{r.report_type}_report_{report_id}.html"'
            },
        )

    return FileResponse(
        path=str(path_obj),
        media_type="text/markdown; charset=utf-8",
        filename=f"{r.report_type}_report_{report_id}.md",
    )
