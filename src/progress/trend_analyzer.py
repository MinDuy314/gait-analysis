from typing import Any, Dict, List, Optional, Tuple
import numpy as np


def compute_trend(values: List[float]) -> Optional[Tuple[str, float]]:
    """
    Returns (direction, slope) for a sequence of measurements.
    Requires at least 3 data points.
    """
    if len(values) < 3:
        return None
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    # Simple linear regression
    slope, _ = np.polyfit(x, y, 1)
    if abs(slope) < 1e-6:
        direction = "stable"
    elif slope > 0:
        direction = "increasing"
    else:
        direction = "decreasing"
    return direction, float(slope)


def analyze_trends(
    historical_features: List[Dict[str, Any]],  # ordered oldest to newest
) -> Dict[str, Optional[Tuple[str, float]]]:
    if len(historical_features) < 3:
        return {}

    all_keys: set = set()
    for f in historical_features:
        all_keys.update(f.keys())

    trends: Dict[str, Optional[Tuple[str, float]]] = {}
    for key in all_keys:
        vals = []
        for f in historical_features:
            v = f.get(key)
            if v is not None and isinstance(v, (int, float)) and np.isfinite(v):
                vals.append(float(v))
        if len(vals) >= 3:
            trends[key] = compute_trend(vals)
        else:
            trends[key] = None
    return trends
