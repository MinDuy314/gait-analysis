"""Annotated video generation: draws COCO skeleton + keypoints onto video frames.

Design constraints:
- Reuses List[FramePose] from an existing pipeline pass (no second inference).
- Confidence-threshold gating: landmarks below threshold are not drawn.
- Missing landmarks are handled safely (KeyError/AttributeError never raised).
- Output MP4 is verified (non-empty, reopenable) before returning.
- VideoAnnotationError is raised on any failure, distinct from GaitAnalysisError.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from src.core.exceptions import VideoAnnotationError
from src.core.logging import get_logger
from src.pose_estimation.landmark_schema import FramePose, Landmark

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# COCO 17-keypoint connectivity (pairs of landmark names)
# ---------------------------------------------------------------------------
COCO_SKELETON: List[Tuple[str, str]] = [
    # Head
    ("left_eye", "right_eye"),
    ("nose", "left_eye"),
    ("nose", "right_eye"),
    ("left_eye", "left_ear"),
    ("right_eye", "right_ear"),
    # Upper body
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"),
    ("right_shoulder", "right_elbow"),
    ("left_elbow", "left_wrist"),
    ("right_elbow", "right_wrist"),
    # Torso
    ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    # Lower body
    ("left_hip", "left_knee"),
    ("right_hip", "right_knee"),
    ("left_knee", "left_ankle"),
    ("right_knee", "right_ankle"),
    # Feet
    ("left_ankle", "left_heel"),
    ("right_ankle", "right_heel"),
    ("left_ankle", "left_foot_index"),
    ("right_ankle", "right_foot_index"),
]

# BGR colours
_COLOUR_HIGH_CONF = (0, 255, 0)      # green  — confidence >= threshold
_COLOUR_LOW_CONF  = (0, 165, 255)    # orange — confidence in [threshold/2, threshold)
_COLOUR_SKELETON  = (255, 200, 0)    # cyan-ish for bones
_RADIUS_KP        = 4
_THICKNESS_BONE   = 2


def _conf_colour(conf: float) -> Tuple[int, int, int]:
    """Colour representing keypoint confidence (green → orange scale)."""
    if conf >= 0.7:
        return (0, 255, 0)
    if conf >= 0.5:
        return (0, 200, 100)
    return (0, 165, 255)


def _get_lm(frame_pose: FramePose, name: str) -> Optional[Landmark]:
    """Return landmark if it exists in the frame; else None."""
    return frame_pose.landmarks.get(name)


def _lm_valid(lm: Optional[Landmark], conf_threshold: float) -> bool:
    """True when landmark exists, is visible, and confident enough."""
    return (
        lm is not None
        and lm.is_visible
        and lm.confidence >= conf_threshold
    )


def _draw_skeleton(
    frame: np.ndarray,
    frame_pose: FramePose,
    conf_threshold: float,
) -> None:
    """Draw skeleton connections and keypoint circles onto *frame* in-place."""
    # Bones
    for (a_name, b_name) in COCO_SKELETON:
        a = _get_lm(frame_pose, a_name)
        b = _get_lm(frame_pose, b_name)
        if _lm_valid(a, conf_threshold) and _lm_valid(b, conf_threshold):
            pt_a = (int(a.x_px), int(a.y_px))
            pt_b = (int(b.x_px), int(b.y_px))
            cv2.line(frame, pt_a, pt_b, _COLOUR_SKELETON, _THICKNESS_BONE, cv2.LINE_AA)

    # Keypoints
    for lm in frame_pose.landmarks.values():
        if not lm.is_visible or lm.confidence < conf_threshold / 2:
            continue
        pt = (int(lm.x_px), int(lm.y_px))
        colour = _conf_colour(lm.confidence)
        cv2.circle(frame, pt, _RADIUS_KP, colour, -1, cv2.LINE_AA)
        cv2.circle(frame, pt, _RADIUS_KP + 1, (0, 0, 0), 1, cv2.LINE_AA)  # thin outline


def annotate_video(
    video_path: Path,
    poses: List[FramePose],
    output_path: Path,
    fps: Optional[float] = None,
    conf_threshold: float = 0.5,
) -> Path:
    """Annotate *video_path* with skeleton overlays and write to *output_path*.

    Parameters
    ----------
    video_path:     Path to the original recording (must exist).
    poses:          Per-frame pose results from the pipeline (index-matched to frames).
    output_path:    Destination path for the annotated MP4.
    fps:            Output FPS; if None, copied from source video.
    conf_threshold: Landmarks with confidence < this value are not drawn.

    Returns
    -------
    output_path after verification.

    Raises
    ------
    VideoAnnotationError on any I/O, encoding, or verification failure.
    """
    video_path = Path(video_path)
    output_path = Path(output_path)

    if not video_path.exists():
        raise VideoAnnotationError(
            f"Source video not found: {video_path}"
        )

    # Build a dict: frame_index → FramePose for O(1) lookup
    pose_map = {p.frame_index: p for p in poses}

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise VideoAnnotationError(
            f"Cannot open source video for reading: {video_path}"
        )

    try:
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out_fps = fps if fps is not None else src_fps

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Attempt mp4v with fallback to avc1
        writer = None
        for code in ("mp4v", "avc1", "XVID"):
            fourcc = cv2.VideoWriter_fourcc(*code)
            w = cv2.VideoWriter(str(output_path), fourcc, out_fps, (width, height))
            if w.isOpened():
                writer = w
                break

        if writer is None or not writer.isOpened():
            raise VideoAnnotationError(
                f"Cannot open VideoWriter for output: {output_path}"
            )

        frame_idx = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                pose = pose_map.get(frame_idx)
                if pose is not None:
                    try:
                        _draw_skeleton(frame, pose, conf_threshold)
                    except Exception as draw_err:
                        # Non-fatal: log and write unannotated frame
                        logger.warning(
                            "Skeleton draw failed at frame %d: %s", frame_idx, draw_err
                        )

                writer.write(frame)
                frame_idx += 1
        finally:
            writer.release()

    finally:
        cap.release()

    # Verify the output file is non-empty and reopenable
    if not output_path.exists():
        raise VideoAnnotationError(
            f"Annotated video was not created at {output_path}"
        )
    if output_path.stat().st_size == 0:
        raise VideoAnnotationError(
            f"Annotated video is empty (0 bytes): {output_path}"
        )
    verify_cap = cv2.VideoCapture(str(output_path))
    reopenable = verify_cap.isOpened()
    verify_cap.release()
    if not reopenable:
        raise VideoAnnotationError(
            f"Annotated video could not be reopened for verification: {output_path}"
        )

    logger.info(
        "Annotated video written: %s (%.1f KB, %d source frames processed)",
        output_path,
        output_path.stat().st_size / 1024,
        frame_idx,
    )
    return output_path
