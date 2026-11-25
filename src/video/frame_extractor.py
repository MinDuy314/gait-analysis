"""Frame extraction with configurable sampling and timestamp preservation."""

from pathlib import Path
from typing import Generator, List, Optional, Tuple
import cv2
import numpy as np

from src.core.logging import get_logger

logger = get_logger(__name__)


class ExtractedFrame:
    """Container for an extracted video frame with temporal metadata."""

    def __init__(
        self,
        frame_index: int,
        timestamp_s: float,
        image_bgr: np.ndarray,
        orig_width: int,
        orig_height: int,
    ) -> None:
        self.frame_index = frame_index
        self.timestamp_s = timestamp_s
        self.image_bgr = image_bgr
        self.orig_width = orig_width
        self.orig_height = orig_height


def extract_frames(
    video_path: Path,
    frame_stride: int = 1,
    max_frames: Optional[int] = None,
    resize_dim: Optional[Tuple[int, int]] = None,
) -> Generator[ExtractedFrame, None, None]:
    """
    Generator yielding ExtractedFrame objects from a video file.
    Does not hold entire video in memory.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise IOError(f"Cannot open video for frame extraction: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if fps > 0 else 30.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    idx = 0
    yielded = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            if idx % frame_stride == 0:
                t_pos_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                t_s = (t_pos_msec / 1000.0) if t_pos_msec > 0 else (idx / fps)

                img_out = frame
                if resize_dim is not None:
                    img_out = cv2.resize(frame, resize_dim, interpolation=cv2.INTER_LINEAR)

                yield ExtractedFrame(
                    frame_index=idx,
                    timestamp_s=round(t_s, 4),
                    image_bgr=img_out,
                    orig_width=orig_w,
                    orig_height=orig_h,
                )
                yielded += 1
                if max_frames is not None and yielded >= max_frames:
                    break
            idx += 1
    finally:
        cap.release()
