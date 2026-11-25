"""Tests for Milestone 5: Report generation."""
import pytest
import tempfile
from pathlib import Path
from src.assessment.assessment_schema import AssessmentContext, GaitAssessment, AssessmentStatus
from src.assessment.assessment_engine import AssessmentEngine
from src.reporting.individual_report import generate_individual_report
from src.reporting.professional_report import generate_professional_report
from src.reporting.report_renderer import ReportRenderer
from src.reporting.report_schema import ReportType


def _make_assessment(camera_view="side"):
    ctx = AssessmentContext(
        subject_id="S001",
        session_id="SES001",
        camera_view=camera_view,
        calibration_status="uncalibrated",
    )
    engine = AssessmentEngine()
    return engine.assess(
        context=ctx,
        features={"knee_flexion_rom": 60.0, "cadence_steps_per_min": 115.0},
        confidences={"knee_flexion_rom": 0.8, "cadence_steps_per_min": 0.9},
        n_cycles=4,
    )


def test_individual_report_generated():
    assessment = _make_assessment()
    report = generate_individual_report(assessment)
    assert report.report_type == ReportType.individual
    assert "Gait Analysis Summary" in report.content_md
    assert len(report.content_md) > 100
    assert "clinical" in report.content_md.lower() or "limitation" in report.content_md.lower()


def test_professional_report_generated():
    assessment = _make_assessment()
    report = generate_professional_report(assessment)
    assert report.report_type == ReportType.professional
    assert "Professional" in report.content_md
    assert "Session Context" in report.content_md


def test_report_contains_limitations():
    assessment = _make_assessment()
    ind = generate_individual_report(assessment)
    pro = generate_professional_report(assessment)
    assert len(ind.limitations) > 0
    assert len(pro.limitations) > 0


def test_report_renderer_saves_file():
    assessment = _make_assessment()
    report = generate_individual_report(assessment)
    with tempfile.TemporaryDirectory() as tmpdir:
        renderer = ReportRenderer.__new__(ReportRenderer)
        renderer._individual_dir = Path(tmpdir) / "individual"
        renderer._professional_dir = Path(tmpdir) / "professional"
        renderer._individual_dir.mkdir(parents=True)
        renderer._professional_dir.mkdir(parents=True)
        path = renderer.save(report)
        assert path.exists()
        assert path.read_text(encoding="utf-8") == report.content_md


def test_report_has_provenance():
    assessment = _make_assessment()
    report = generate_professional_report(assessment)
    assert "pose_model" in report.provenance
