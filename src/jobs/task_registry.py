"""Task registry and end-to-end analysis orchestration."""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.core.logging import get_logger
from src.database.repositories import JobRepository, RecordingRepository
from src.database.models import AssessmentRecord

logger = get_logger(__name__)

PIPELINE_STAGES = [
    "validate_recording",
    "extract_frames",
    "estimate_pose",
    "detect_view",
    "detect_events",
    "segment_cycles",
    "extract_features",
    "quality_control",
    "assess",
    "generate_reports",
    "finalize",
]


def _stage_progress(stage_name: str) -> float:
    idx = PIPELINE_STAGES.index(stage_name) if stage_name in PIPELINE_STAGES else 0
    return round(idx / len(PIPELINE_STAGES) * 100, 1)


def run_analysis_pipeline(
    job_id: str,
    db,
    recording_path: str,
    session_id: str,
    subject_id: str,
    camera_view: str = "side",
    pose_model: str = "yolo",
    pose_model_version: str = "v8n-pose",
    recording_id: Optional[str] = None,
    **kwargs,
):
    """Full pipeline task. Executes real video pipeline and saves stage progress."""
    repo = JobRepository(db)
    rec_repo = RecordingRepository(db)
    partial_results: Dict[str, Any] = {
        "stages_completed": [],
        "features": {},
        "confidences": {},
        "assessment": None,
        "reports": [],
        "annotation_status": "not_applicable",
        "annotated_video_path": None,
    }

    def _update(stage: str, pct: Optional[float] = None, processed_frames: Optional[int] = None, total_frames: Optional[int] = None):
        p = pct if pct is not None else _stage_progress(stage)
        repo.update_status(
            job_id,
            "running",
            stage=stage,
            progress=p,
            result=partial_results,
            processed_frames=processed_frames,
            total_frames=total_frames,
        )

    poses: List[Any] = []
    n_cycles: int = 0
    effective_camera_view: str = camera_view

    try:
        # Stage 1: Validate recording
        _update("validate_recording")
        if recording_path:
            path_obj = Path(recording_path)
            from src.video.video_validator import validate_video
            val_result = validate_video(path_obj)

            # Persist validation status to Recording model
            if recording_id:
                meta = val_result.metadata
                rec_repo.update_validation(
                    recording_id=recording_id,
                    status="passed" if val_result.is_valid else "failed",
                    message="; ".join([i.message for i in val_result.issues]) if val_result.issues else None,
                    duration_seconds=meta.duration_seconds if meta else None,
                    fps=meta.fps if meta else None,
                    width=meta.width if meta else None,
                    height=meta.height if meta else None,
                )

            if not val_result.is_valid:
                critical_issues = [i.message for i in val_result.issues if i.severity == "critical"]
                all_issues = critical_issues or [i.message for i in val_result.issues] or ["Video failed validation"]
                err_msg = "; ".join(all_issues)
                partial_results["video_validation"] = {
                    "status": "failed",
                    "issues": [i.model_dump() for i in val_result.issues],
                }
                if recording_id:
                    rec_repo.update_annotation(
                        recording_id=recording_id,
                        annotated_video_path=None,
                        annotation_status="failed",
                    )
                partial_results["annotation_status"] = "failed"
                repo.update_status(
                    job_id,
                    "failed",
                    stage="validate_recording",
                    error=f"Video validation failed: {err_msg}",
                    result=partial_results,
                )
                logger.warning("Job %s stopped due to video validation failure: %s", job_id, err_msg)
                return

            partial_results["video_validation"] = {"status": "passed"}
            partial_results["stages_completed"].append("validate_recording")

            # Stages 2-8: Execute real video pipeline (pose estimation, view detection, events, cycles, features)
            _update("extract_frames")

            def on_frame_progress(proc_f: int, tot_f: int):
                # Calculate progress dynamically during pose estimation stage
                # Stage 3 'estimate_pose' is index 2 in PIPELINE_STAGES
                # We can calculate percentage between stage 2 and stage 4
                base_pct = _stage_progress("estimate_pose")
                next_pct = _stage_progress("detect_view")
                stage_range = next_pct - base_pct
                frac = (proc_f / tot_f) if tot_f and tot_f > 0 else 0.0
                current_pct = round(base_pct + (frac * stage_range), 1)
                _update(
                    stage="estimate_pose",
                    pct=current_pct,
                    processed_frames=proc_f,
                    total_frames=tot_f,
                )

            from src.video.video_pipeline_runner import process_video_pipeline
            pipeline_result = process_video_pipeline(
                video_path=path_obj,
                session_id=session_id,
                estimator_type=pose_model,
                progress_callback=on_frame_progress,
            )

            poses = pipeline_result.poses
            n_cycles = len(pipeline_result.gait_cycles)
            if pipeline_result.camera_view.predicted_view != "unknown":
                effective_camera_view = pipeline_result.camera_view.predicted_view

            for stage in PIPELINE_STAGES[1:8]:
                _update(stage)
                partial_results["stages_completed"].append(stage)

            # Map genuinely calculated metrics only — never hardcode fake values
            extracted_features: Dict[str, Any] = {}
            extracted_confidences: Dict[str, float] = {}
            for m in pipeline_result.measurements:
                if m.value is not None:
                    extracted_features[m.feature_name] = m.value
                    extracted_confidences[m.feature_name] = m.confidence
                    if m.feature_name == "cadence":
                        extracted_features["cadence_steps_per_min"] = m.value
                        extracted_confidences["cadence_steps_per_min"] = m.confidence
                    elif m.feature_name == "gait_cycle_duration":
                        extracted_features["stride_time_mean"] = m.value
                        extracted_confidences["stride_time_mean"] = m.confidence
                        if m.cycle_consistency_sd is not None:
                            extracted_features["stride_time_sd"] = m.cycle_consistency_sd
                            extracted_confidences["stride_time_sd"] = m.confidence
                    elif "knee_flexion_extension_rom" in m.feature_name:
                        if "knee_flexion_rom" not in extracted_features:
                            extracted_features["knee_flexion_rom"] = m.value
                            extracted_confidences["knee_flexion_rom"] = m.confidence

            partial_results["features"] = extracted_features
            partial_results["confidences"] = extracted_confidences

        else:
            # No video recording provided (e.g. lightweight session tests)
            for stage in PIPELINE_STAGES[0:8]:
                partial_results["stages_completed"].append(stage)
            partial_results["features"] = {}
            partial_results["confidences"] = {}

        # Stage 9: Assessment
        _update("assess")
        from src.assessment.assessment_schema import AssessmentContext
        from src.assessment.assessment_engine import AssessmentEngine
        ctx = AssessmentContext(
            subject_id=subject_id,
            session_id=session_id,
            camera_view=effective_camera_view,
            pose_model=pose_model,
            pose_model_version=pose_model_version,
        )
        engine = AssessmentEngine()
        assessment = engine.assess(
            context=ctx,
            features=partial_results["features"],
            confidences=partial_results["confidences"],
            n_cycles=n_cycles,
        )
        partial_results["assessment"] = assessment.model_dump(mode="json")
        partial_results["stages_completed"].append("assess")

        # Persist assessment record with json serializable data
        rec = AssessmentRecord(
            subject_id=subject_id,
            session_id=session_id,
            job_id=job_id,
            assessment_data=assessment.model_dump(mode="json"),
            overall_status=assessment.overall_status.value,
            pose_model=pose_model,
            rule_version=ctx.assessment_rule_version,
            created_at=datetime.utcnow(),
        )
        db.add(rec)
        db.commit()

        # Stage 10: Generate reports
        _update("generate_reports")
        from src.reporting.individual_report import generate_individual_report
        from src.reporting.professional_report import generate_professional_report
        from src.reporting.report_renderer import ReportRenderer
        renderer = ReportRenderer()
        ind_report = generate_individual_report(assessment)
        pro_report = generate_professional_report(assessment)
        ind_path = renderer.save(ind_report)
        pro_path = renderer.save(pro_report)
        partial_results["reports"] = [str(ind_path), str(pro_path)]
        partial_results["stages_completed"].append("generate_reports")

        # ------------------------------------------------------------------ #
        # Optional annotation stage — failure does NOT fail the whole job.   #
        # Reuses the exact poses from the single inference pass above.       #
        # ------------------------------------------------------------------ #
        if recording_path and recording_id:
            _annotate_recording(
                db=db,
                recording_path=recording_path,
                recording_id=recording_id,
                partial_results=partial_results,
                poses=poses,
            )

        # Stage 11: Finalize
        _update("finalize", pct=100.0)
        partial_results["stages_completed"].append("finalize")

        repo.update_status(job_id, "completed", stage="finalize", progress=100.0, result=partial_results)
        logger.info("Job %s completed successfully", job_id)

    except Exception as exc:
        logger.exception("Pipeline failed at stage for job %s: %s", job_id, exc)
        db.rollback()
        repo.update_status(job_id, "failed", error=str(exc), result=partial_results)
        if recording_id:
            try:
                rec_repo.update_annotation(
                    recording_id=recording_id,
                    annotated_video_path=None,
                    annotation_status="failed",
                )
            except Exception:
                pass
        raise


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _annotate_recording(
    db,
    recording_path: str,
    recording_id: str,
    partial_results: Dict[str, Any],
    poses: Optional[List[Any]] = None,
) -> None:
    """Run annotation reusing existing poses from the single inference pass.

    Populates partial_results["annotation_status"] and
    partial_results["annotated_video_path"]. Persists to DB via
    RecordingRepository. Any failure is caught, logged, and recorded
    as annotation_status="failed" — the job itself still completes.
    """
    from src.visualization.video_annotator import annotate_video
    from src.core.exceptions import VideoAnnotationError
    from src.database.repositories import RecordingRepository

    rec_repo = RecordingRepository(db)

    try:
        src_path = Path(recording_path)
        out_path = src_path.parent / f"annotated_{src_path.name}"

        poses_to_use = poses if poses is not None else []

        annotated_path = annotate_video(
            video_path=src_path,
            poses=poses_to_use,
            output_path=out_path,
        )

        partial_results["annotation_status"] = "completed"
        partial_results["annotated_video_path"] = str(annotated_path)

        rec_repo.update_annotation(
            recording_id=recording_id,
            annotated_video_path=str(annotated_path),
            annotation_status="completed",
        )
        logger.info("Annotation completed for recording %s → %s", recording_id, annotated_path)

    except (VideoAnnotationError, Exception) as ann_err:
        logger.warning("Annotation failed for recording %s: %s", recording_id, ann_err)
        partial_results["annotation_status"] = "failed"
        partial_results["annotation_error"] = str(ann_err)
        rec_repo.update_annotation(
            recording_id=recording_id,
            annotated_video_path=None,
            annotation_status="failed",
        )
