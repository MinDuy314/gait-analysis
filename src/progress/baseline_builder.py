from typing import Any, Dict, List, Optional
import numpy as np
from src.progress.progress_schema import Baseline
from src.core.logging import get_logger

logger = get_logger(__name__)

MIN_SESSIONS_FOR_BASELINE = 2
MIN_TRIALS_PER_FEATURE = 2


def build_baseline(
    subject_id: str,
    session_features: List[Dict[str, Any]],  # list of feature dicts per session
    session_ids: List[str],
    conditions: Optional[List[str]] = None,
    previous_version: int = 0,
) -> Optional[Baseline]:
    if len(session_features) < MIN_SESSIONS_FOR_BASELINE:
        logger.warning(
            "Insufficient sessions for baseline: %d (need %d)",
            len(session_features), MIN_SESSIONS_FOR_BASELINE,
        )
        return None

    all_keys: set = set()
    for sf in session_features:
        all_keys.update(sf.keys())

    feature_means: Dict[str, Optional[float]] = {}
    feature_medians: Dict[str, Optional[float]] = {}
    feature_sds: Dict[str, Optional[float]] = {}
    feature_n: Dict[str, int] = {}

    for key in all_keys:
        values = []
        for sf in session_features:
            v = sf.get(key)
            if v is not None and isinstance(v, (int, float)) and np.isfinite(v):
                values.append(float(v))
        n = len(values)
        feature_n[key] = n
        if n >= MIN_TRIALS_PER_FEATURE:
            arr = np.array(values)
            feature_means[key] = float(np.mean(arr))
            feature_medians[key] = float(np.median(arr))
            feature_sds[key] = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        else:
            feature_means[key] = None
            feature_medians[key] = None
            feature_sds[key] = None

    return Baseline(
        subject_id=subject_id,
        version=previous_version + 1,
        n_sessions=len(session_features),
        n_trials=sum(feature_n.values()),
        feature_means=feature_means,
        feature_medians=feature_medians,
        feature_sds=feature_sds,
        feature_n=feature_n,
        contributing_session_ids=list(session_ids),
        conditions=conditions or [],
    )
