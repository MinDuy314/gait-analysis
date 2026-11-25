"""Gait event validation metrics and timing error analysis against reference events."""

from typing import List, Optional, Tuple
import numpy as np

from src.validation.validation_schema import EventValidationMetrics


def evaluate_gait_events(
    detected_events_s: List[float],
    reference_events_s: List[float],
    event_type: str = "foot_strike",
    side: Optional[str] = None,
    tolerance_ms: float = 100.0,
) -> EventValidationMetrics:
    """
    Evaluate detected event timestamps against reference event timestamps using a greedy matching window.
    Calculates precision, recall, F1, and timing error in milliseconds.
    """
    tol_s = tolerance_ms / 1000.0

    det_sorted = sorted(detected_events_s)
    ref_sorted = sorted(reference_events_s)

    n_ref = len(ref_sorted)
    n_det = len(det_sorted)

    if n_ref == 0 or n_det == 0:
        prec = 0.0 if n_det > 0 else None
        rec = 0.0 if n_ref > 0 else None
        return EventValidationMetrics(
            event_type=event_type,
            side=side,
            tolerance_ms=tolerance_ms,
            total_reference_events=n_ref,
            total_detected_events=n_det,
            true_positives=0,
            false_positives=n_det,
            false_negatives=n_ref,
            precision=prec,
            recall=rec,
            f1_score=0.0 if (prec or rec) else None,
            status="no_events_to_match",
        )

    matched_ref = set()
    matched_det = set()
    timing_errors_ms = []

    # Greedy match: pair each detected event with the closest reference event within tolerance
    for d_idx, t_det in enumerate(det_sorted):
        best_ref_idx = None
        min_err = float("inf")
        for r_idx, t_ref in enumerate(ref_sorted):
            if r_idx in matched_ref:
                continue
            err = abs(t_det - t_ref)
            if err <= tol_s and err < min_err:
                min_err = err
                best_ref_idx = r_idx

        if best_ref_idx is not None:
            matched_det.add(d_idx)
            matched_ref.add(best_ref_idx)
            # signed error (detected - reference) in ms
            timing_errors_ms.append((t_det - ref_sorted[best_ref_idx]) * 1000.0)

    tp = len(matched_det)
    fp = n_det - tp
    fn = n_ref - len(matched_ref)

    precision = (tp / n_det) if n_det > 0 else 0.0
    recall = (tp / n_ref) if n_ref > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    if timing_errors_ms:
        errs = np.array(timing_errors_ms)
        mae = float(np.mean(np.abs(errs)))
        med = float(np.median(errs))
        rmse = float(np.sqrt(np.mean(errs ** 2)))
        sd = float(np.std(errs, ddof=1)) if errs.size > 1 else 0.0
    else:
        mae, med, rmse, sd = None, None, None, None

    return EventValidationMetrics(
        event_type=event_type,
        side=side,
        tolerance_ms=tolerance_ms,
        total_reference_events=n_ref,
        total_detected_events=n_det,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=round(precision, 3),
        recall=round(recall, 3),
        f1_score=round(f1, 3),
        timing_mae_ms=round(mae, 2) if mae is not None else None,
        timing_median_error_ms=round(med, 2) if med is not None else None,
        timing_rmse_ms=round(rmse, 2) if rmse is not None else None,
        timing_error_sd_ms=round(sd, 2) if sd is not None else None,
        status="evaluated",
    )
