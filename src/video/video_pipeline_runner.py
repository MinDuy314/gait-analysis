"""End-to-end video processing pipeline runner."""

from pathlib import Path
from typing import Dict, List, Optional
import json
import pandas as pd
from pydantic import BaseModel, Field

from src.core.config import AppConfig
from src.core.logging import get_logger
from src.feature_extraction.video_feature_extractor import VideoGaitFeature, extract_video_features
from src.gait_events.gait_cycle_segmenter import GaitCycle, segment_gait_cycles
from src.gait_events.gait_event_detector import GaitEvent, detect_gait_events_from_poses
from src.pose_estimation.landmark_schema import FramePose
from src.pose_estimation.pose_factory import create_pose_estimator
from src.video.frame_extractor import extract_frames
from src.video.video_metadata import VideoMetadata
from src.video.video_validator import validate_video
from src.view_detection.camera_view_classifier import CameraViewClassifier, ViewClassificationResult

logger = get_logger(__name__)


class VideoAnalysisResult(BaseModel):
    """Structured end-to-end result schema for a video processing session."""

    recording_id: str
    session_id: str
    input_type: str = "video"
    video_metadata: VideoMetadata
    camera_view: ViewClassificationResult
    model_name: str
    device: str
    total_frames_extracted: int
    gait_events: List[GaitEvent] = Field(default_factory=list)
    gait_cycles: List[GaitCycle] = Field(default_factory=list)
    measurements: List[VideoGaitFeature] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


def process_video_pipeline(
    video_path: Path,
    session_id: str = "default_session",
    estimator_type: str = "yolo",
    device: Optional[str] = None,
    frame_stride: int = 1,
    max_frames: Optional[int] = None,
    cfg: Optional[AppConfig] = None,
) -> VideoAnalysisResult:
    """Execute complete video processing pipeline from ingestion to feature extraction."""
    cfg = cfg or AppConfig()
    path_obj = Path(video_path)

    # 1. Validation
    val_res = validate_video(path_obj)
    if not val_res.is_valid or val_res.metadata is None:
        reasons = [i.message for i in val_res.issues]
        raise ValueError(f"Video validation failed for {path_obj.name}: {'; '.join(reasons)}")

    meta = val_res.metadata

    # 2. Pose estimation initialization
    estimator = create_pose_estimator(estimator_type=estimator_type, device=device)

    poses: List[FramePose] = []
    for frame_obj in extract_frames(
        video_path=path_obj,
        frame_stride=frame_stride,
        max_frames=max_frames,
    ):
        pose = estimator.estimate_frame(
            frame_bgr=frame_obj.image_bgr,
            frame_index=frame_obj.frame_index,
            timestamp_s=frame_obj.timestamp_s,
            orig_width=frame_obj.orig_width,
            orig_height=frame_obj.orig_height,
        )
        poses.append(pose)

    # 3. Camera view classification
    classifier = CameraViewClassifier()
    view_res = classifier.classify_sequence(poses)

    # 4. Gait event detection
    events = detect_gait_events_from_poses(
        poses=poses,
        camera_view=view_res.predicted_view,
        fps=meta.fps / frame_stride if meta.fps > 0 else 30.0,
    )

    # 5. Cycle segmentation & normalisation
    cycles = segment_gait_cycles(events)

    # 6. View-supported feature extraction
    features = extract_video_features(
        poses=poses,
        cycles=cycles,
        camera_view=view_res.predicted_view,
    )

    limitations = [
        "Monocular video provides 2D image-plane estimates, NOT calibrated 3D laboratory motion capture.",
        "Angles represent planar projections and depend on camera perspective angle.",
        "This is a monitoring and research support tool, not a medical diagnostic device.",
    ]
    if view_res.predicted_view == "unknown":
        limitations.append("Camera view could not be identified with confidence; frontal/sagittal features limited.")

    result = VideoAnalysisResult(
        recording_id=path_obj.stem,
        session_id=session_id,
        video_metadata=meta,
        camera_view=view_res,
        model_name=estimator.model_name,
        device=estimator.device,
        total_frames_extracted=len(poses),
        gait_events=events,
        gait_cycles=cycles,
        measurements=features,
        limitations=limitations,
    )

    # Save output artifacts under data/video/processed/
    proc_dir = cfg.project_root / "data" / "video" / "processed"
    (proc_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (proc_dir / "features").mkdir(parents=True, exist_ok=True)

    out_json = proc_dir / "metadata" / f"{path_obj.stem}_analysis.json"
    with open(out_json, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))

    if features:
        feat_df = pd.DataFrame([m.model_dump(exclude={"normalized_101_curve"}) for m in features])
        feat_df.to_csv(proc_dir / "features" / f"{path_obj.stem}_features.csv", index=False)

    return result
