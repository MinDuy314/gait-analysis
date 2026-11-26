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
from src.api.schemas.requests import ReportRequest, ReportUpdateRequest
from src.assessment.assessment_engine import AssessmentEngine
from src.assessment.assessment_schema import AssessmentContext
from src.database.models import AssessmentRecord, ReportRecord, Subject, User
from src.database.repositories import SessionRepository, SubjectRepository
from src.progress.longitudinal_service import build_longitudinal_progress
from src.reporting.individual_report import generate_individual_report
from src.reporting.professional_report import generate_professional_report
from src.reporting.report_renderer import ReportRenderer
import uuid
from datetime import datetime

router = APIRouter(tags=["reports"])


def _require_clinician(user: User, action: str = "perform this action"):
    if user.role not in ("professional", "administrator"):
        raise HTTPException(status_code=403, detail=f"Only authorized clinicians can {action}")


def _build_report_from_record(db: Session, record: ReportRecord, clinician_name: Optional[str] = None):
    """Regenerate report markdown and structured data preserving clinician edits."""
    sess = SessionRepository(db).get(record.session_id)
    assessment_record = db.query(AssessmentRecord).filter(
        AssessmentRecord.session_id == record.session_id
    ).order_by(AssessmentRecord.created_at.desc()).first()

    if assessment_record and assessment_record.assessment_data:
        from src.assessment.assessment_schema import GaitAssessment
        assessment = GaitAssessment.model_validate(assessment_record.assessment_data)
    else:
        ctx = AssessmentContext(
            subject_id=record.subject_id,
            session_id=record.session_id,
            camera_view=sess.camera_view if sess else None,
            walking_speed_ms=sess.walking_speed_ms if sess else None,
        )
        assessment = AssessmentEngine().assess(context=ctx, features={})

    longitudinal = build_longitudinal_progress(db, record.subject_id)
    renderer = ReportRenderer()
    if record.report_type == "individual":
        report = generate_individual_report(
            assessment,
            longitudinal=longitudinal,
            clinician_notes=record.clinician_notes,
            rehabilitation_priorities=record.rehabilitation_priorities,
            recommendations=record.recommendations,
        )
    else:
        report = generate_professional_report(
            assessment,
            longitudinal=longitudinal,
            clinician_name=clinician_name or record.approved_by,
            clinician_notes=record.clinician_notes,
            rehabilitation_priorities=record.rehabilitation_priorities,
            recommendations=record.recommendations,
        )
    report.report_id = record.id
    file_path = renderer.save(report)
    record.file_path = str(file_path)
    record.report_data = report.report_data


@router.get("/api/v1/reports", response_model=list[ReportResponse])
def list_reports(
    subject_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(ReportRecord).filter(ReportRecord.is_deleted == False)
    if subject_id:
        subj = SubjectRepository(db).get(subject_id)
        if not subj:
            raise HTTPException(status_code=404, detail="Subject not found")
        verify_subject_access(subj, current_user)
        q = q.filter(ReportRecord.subject_id == subject_id)

    reports = q.order_by(ReportRecord.generated_at.desc()).all()
    visible = []
    for r in reports:
        subj = SubjectRepository(db).get(r.subject_id)
        if not subj:
            continue
        if current_user.role == "individual":
            if subj.owner_id != current_user.id:
                continue
            if r.report_type != "individual" or r.status != "published":
                continue
        else:
            if not current_user.organization_id or subj.organization_id != current_user.organization_id:
                continue
        visible.append(r)
    return visible


@router.get("/api/v1/sessions/{session_id}/reports", response_model=list[ReportResponse])
def list_session_reports(
    session_id: str,
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

    q = db.query(ReportRecord).filter(
        ReportRecord.session_id == session_id,
        ReportRecord.is_deleted == False,
    )
    if current_user.role == "individual":
        q = q.filter(ReportRecord.report_type == "individual", ReportRecord.status == "published")
    return q.order_by(ReportRecord.generated_at.desc()).all()


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
    if current_user.role == "individual":
        raise HTTPException(status_code=403, detail="Only clinicians can generate reports")

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

    longitudinal = build_longitudinal_progress(db, sess.subject_id)
    renderer = ReportRenderer()
    if payload.report_type == "individual":
        report = generate_individual_report(
            assessment,
            longitudinal=longitudinal,
            clinician_notes=payload.clinician_notes,
            rehabilitation_priorities=payload.rehabilitation_priorities,
            recommendations=payload.recommendations,
        )
    elif payload.report_type == "professional":
        report = generate_professional_report(
            assessment,
            longitudinal=longitudinal,
            clinician_name=current_user.username,
            clinician_notes=payload.clinician_notes,
            rehabilitation_priorities=payload.rehabilitation_priorities,
            recommendations=payload.recommendations,
        )
    else:
        raise HTTPException(status_code=400, detail="report_type must be 'individual' or 'professional'")

    file_path = renderer.save(report)
    now = datetime.utcnow()
    default_title = (
        payload.title
        or (f"Clinical Gait Report — {subj.display_name or sess.subject_id[:8]}"
            if payload.report_type == "professional"
            else f"Patient Walking Progress Report — {subj.display_name or sess.subject_id[:8]}")
    )

    record = ReportRecord(
        id=report.report_id,
        subject_id=sess.subject_id,
        session_id=session_id,
        report_type=payload.report_type,
        title=default_title,
        assessment_id=assessment.assessment_id,
        file_path=str(file_path),
        status="draft",
        clinician_notes=payload.clinician_notes,
        rehabilitation_priorities=payload.rehabilitation_priorities or [],
        recommendations=payload.recommendations,
        report_data=report.report_data,
        revision_history=[
            {
                "timestamp": now.isoformat(),
                "actor": current_user.username,
                "action": "created",
                "status": "draft",
            }
        ],
        generated_at=now,
        updated_at=now,
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
    if current_user.role == "individual":
        if r.report_type == "professional":
            raise HTTPException(status_code=403, detail="Patients cannot access clinician reports")
        if r.status != "published":
            raise HTTPException(status_code=403, detail="Report is not published yet")
    return r


@router.patch("/api/v1/reports/{report_id}", response_model=ReportResponse)
def update_report(
    report_id: str,
    payload: ReportUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_clinician(current_user, "edit reports")
    r = db.query(ReportRecord).filter(ReportRecord.id == report_id, ReportRecord.is_deleted == False).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    subj = SubjectRepository(db).get(r.subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subj, current_user)

    if payload.title is not None:
        r.title = payload.title
    if payload.clinician_notes is not None:
        r.clinician_notes = payload.clinician_notes
    if payload.rehabilitation_priorities is not None:
        r.rehabilitation_priorities = payload.rehabilitation_priorities
    if payload.recommendations is not None:
        r.recommendations = payload.recommendations
    if payload.status is not None:
        if payload.status not in ("draft", "pending_review"):
            raise HTTPException(status_code=400, detail="Use approve/publish endpoints to approve or publish reports")
        r.status = payload.status

    _build_report_from_record(db, r, clinician_name=current_user.username)
    now = datetime.utcnow()
    history = list(r.revision_history or [])
    history.append({
        "timestamp": now.isoformat(),
        "actor": current_user.username,
        "action": "edited",
        "status": r.status,
    })
    r.revision_history = history
    r.updated_at = now
    db.commit()
    db.refresh(r)
    return r


@router.post("/api/v1/reports/{report_id}/approve", response_model=ReportResponse)
def approve_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_clinician(current_user, "approve reports")
    r = db.query(ReportRecord).filter(ReportRecord.id == report_id, ReportRecord.is_deleted == False).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    subj = SubjectRepository(db).get(r.subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subj, current_user)

    now = datetime.utcnow()
    r.status = "approved"
    r.approved_by = current_user.username
    r.approved_at = now
    _build_report_from_record(db, r, clinician_name=current_user.username)
    history = list(r.revision_history or [])
    history.append({
        "timestamp": now.isoformat(),
        "actor": current_user.username,
        "action": "approved",
        "status": "approved",
    })
    r.revision_history = history
    r.updated_at = now
    db.commit()
    db.refresh(r)
    return r


@router.post("/api/v1/reports/{report_id}/publish", response_model=ReportResponse)
def publish_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_clinician(current_user, "publish reports")
    r = db.query(ReportRecord).filter(ReportRecord.id == report_id, ReportRecord.is_deleted == False).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    subj = SubjectRepository(db).get(r.subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subj, current_user)

    now = datetime.utcnow()
    if not r.approved_by:
        r.approved_by = current_user.username
        r.approved_at = now
    r.status = "published"
    r.published_at = now
    _build_report_from_record(db, r, clinician_name=r.approved_by)
    history = list(r.revision_history or [])
    history.append({
        "timestamp": now.isoformat(),
        "actor": current_user.username,
        "action": "published",
        "status": "published",
    })
    r.revision_history = history
    r.updated_at = now
    db.commit()
    db.refresh(r)
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
    if current_user.role == "individual":
        if r.report_type == "professional":
            raise HTTPException(status_code=403, detail="Patients cannot download clinician reports")
        if r.status != "published":
            raise HTTPException(status_code=403, detail="Unpublished reports cannot be downloaded by patients")
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
