"""Camera view detection based on body geometry and landmark visibility."""

from typing import Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field

from src.pose_estimation.landmark_schema import FramePose


class ViewClassificationResult(BaseModel):
    """Result of camera view orientation classification."""

    predicted_view: str  # "front", "side", "rear", "unknown"
    confidence: float
    evidence: Dict[str, float] = Field(default_factory=dict)
    is_ambiguous: bool = False
    message: str = ""


class CameraViewClassifier:
    """Classifies camera view (front, side, rear, unknown) from pose landmark trajectories."""

    def __init__(self, confidence_threshold: float = 0.5) -> None:
        self.confidence_threshold = confidence_threshold

    def classify_sequence(self, poses: List[FramePose]) -> ViewClassificationResult:
        """Classify viewing perspective across a sequence of frame poses."""
        if not poses:
            return ViewClassificationResult(
                predicted_view="unknown",
                confidence=0.0,
                evidence={},
                is_ambiguous=True,
                message="No pose frames provided",
            )

        shoulder_widths = []
        hip_widths = []
        torso_heights = []
        head_features_present = 0
        total_eval_frames = 0

        for p in poses:
            lm = p.landmarks
            if "left_shoulder" in lm and "right_shoulder" in lm and "left_hip" in lm and "right_hip" in lm:
                ls, rs = lm["left_shoulder"], lm["right_shoulder"]
                lh, rh = lm["left_hip"], lm["right_hip"]

                if ls.is_visible and rs.is_visible and lh.is_visible and rh.is_visible:
                    sw = abs(ls.x_px - rs.x_px)
                    hw = abs(lh.x_px - rh.x_px)
                    th = abs(((ls.y_px + rs.y_px) / 2.0) - ((lh.y_px + rh.y_px) / 2.0))

                    if th > 10.0:
                        shoulder_widths.append(sw)
                        hip_widths.append(hw)
                        torso_heights.append(th)

                        # Check nose/eyes visibility to distinguish front from rear
                        if "nose" in lm and lm["nose"].is_visible and lm["nose"].confidence > 0.4:
                            head_features_present += 1
                        total_eval_frames += 1

        if total_eval_frames < 3:
            return ViewClassificationResult(
                predicted_view="unknown",
                confidence=0.2,
                evidence={"eval_frames": float(total_eval_frames)},
                is_ambiguous=True,
                message="Insufficient visible trunk landmarks across sequence",
            )

        mean_sw = float(np.mean(shoulder_widths))
        mean_th = float(np.mean(torso_heights))
        aspect = mean_sw / mean_th if mean_th > 0 else 0.0
        face_ratio = (head_features_present / total_eval_frames) if total_eval_frames > 0 else 0.0

        evidence = {
            "mean_shoulder_width_px": round(mean_sw, 1),
            "mean_torso_height_px": round(mean_th, 1),
            "shoulder_to_torso_ratio": round(aspect, 3),
            "face_visibility_ratio": round(face_ratio, 3),
        }

        # Side view: narrow apparent shoulder width relative to torso height (< 0.45)
        if aspect < 0.45:
            conf = min(0.95, max(0.5, 1.0 - (aspect / 0.45)))
            return ViewClassificationResult(
                predicted_view="side",
                confidence=round(conf, 2),
                evidence=evidence,
                is_ambiguous=False,
                message="Sagittal/side perspective indicated by narrow projected shoulder width",
            )
        else:
            # Coronal view: distinguish front from rear using facial landmarks
            if face_ratio > 0.4:
                conf = min(0.95, max(0.5, face_ratio))
                return ViewClassificationResult(
                    predicted_view="front",
                    confidence=round(conf, 2),
                    evidence=evidence,
                    is_ambiguous=False,
                    message="Frontal perspective indicated by wide shoulders and visible facial markers",
                )
            else:
                conf = min(0.90, max(0.5, 1.0 - face_ratio))
                return ViewClassificationResult(
                    predicted_view="rear",
                    confidence=round(conf, 2),
                    evidence=evidence,
                    is_ambiguous=False,
                    message="Rear perspective indicated by wide shoulders and absent facial markers",
                )
