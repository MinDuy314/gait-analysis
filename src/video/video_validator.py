"""Video integrity and quality validator."""

from pathlib import Path
from typing import List, Optional, Tuple
import cv2

from src.core.logging import get_logger
from src.video.video_metadata import QualityIssue, VideoMetadata, VideoValidationResult

logger = get_logger(__name__)

# .webm is produced by in-browser (MediaRecorder) webcam capture for multi-view sessions.
SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm"}
MAX_PLAUSIBLE_FPS = 240.0


def extract_video_metadata(video_path: Path) -> Tuple[Optional[VideoMetadata], List[QualityIssue]]:
    """Extract metadata using OpenCV VideoCapture."""
    issues: List[QualityIssue] = []
    path_obj = Path(video_path)

    if not path_obj.exists():
        issues.append(QualityIssue(issue_code="file_not_found", severity="critical", message=f"File not found: {path_obj}"))
        return None, issues

    ext = path_obj.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        issues.append(QualityIssue(issue_code="unsupported_format", severity="critical", message=f"Unsupported format {ext}"))

    cap = cv2.VideoCapture(str(path_obj))
    if not cap.isOpened():
        issues.append(QualityIssue(issue_code="cannot_open_video", severity="critical", message="OpenCV cannot open video stream"))
        return None, issues

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
    codec = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)]).strip()

    ret, test_frame = cap.read()

    # Browser-recorded WebM files often lack frame-count / frame-rate headers.
    # Fall back to decoding the stream to measure them instead of reporting 0 s.
    if ret and (frame_count <= 0 or fps <= 0 or fps > MAX_PLAUSIBLE_FPS):
        counted, last_ms = 1, float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
        while True:
            ok = cap.grab()
            if not ok:
                break
            counted += 1
            last_ms = float(cap.get(cv2.CAP_PROP_POS_MSEC) or last_ms)
        frame_count = counted
        if last_ms > 0 and counted > 1:
            fps = (counted - 1) / (last_ms / 1000.0)

    duration = (frame_count / fps) if fps > 0 else 0.0
    aspect_ratio = (width / height) if height > 0 else 0.0
    cap.release()

    if not ret or test_frame is None:
        issues.append(QualityIssue(issue_code="corrupted_stream", severity="critical", message="Could not read first frame"))
        is_readable = False
    else:
        is_readable = True

    meta = VideoMetadata(
        filename=path_obj.name,
        file_path=str(path_obj).replace("\\", "/"),
        file_size_bytes=path_obj.stat().st_size,
        duration_seconds=round(duration, 3),
        frame_count=frame_count,
        fps=round(fps, 2),
        width=width,
        height=height,
        aspect_ratio=round(aspect_ratio, 3),
        codec=codec,
        is_readable=is_readable,
    )
    return meta, issues


def validate_video(
    video_path: Path,
    min_duration_s: float = 1.0,
    min_fps: float = 15.0,
    min_height: int = 240,
) -> VideoValidationResult:
    """Validate video file integrity and standard recording constraints."""
    meta, issues = extract_video_metadata(video_path)
    if meta is None or not meta.is_readable:
        return VideoValidationResult(is_valid=False, metadata=meta, issues=issues)

    if meta.duration_seconds < min_duration_s:
        issues.append(QualityIssue(
            issue_code="short_duration",
            severity="warning",
            message=f"Duration {meta.duration_seconds}s is below minimum {min_duration_s}s",
        ))

    if meta.fps < min_fps:
        issues.append(QualityIssue(
            issue_code="low_framerate",
            severity="warning",
            message=f"Framerate {meta.fps} fps is below minimum {min_fps} fps",
        ))

    if meta.height < min_height:
        issues.append(QualityIssue(
            issue_code="low_resolution",
            severity="warning",
            message=f"Height {meta.height}px is below minimum {min_height}px",
        ))

    has_critical = any(i.severity == "critical" for i in issues)
    return VideoValidationResult(is_valid=not has_critical, metadata=meta, issues=issues)
