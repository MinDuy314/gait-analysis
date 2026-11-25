import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
from src.assessment.assessment_schema import ReferenceComparison, ComparabilityStatus
from src.core.config import AppConfig


class ReferenceComparisonEngine:
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self._ref_df: Optional[pd.DataFrame] = None

    def _load_reference(self) -> pd.DataFrame:
        if self._ref_df is not None:
            return self._ref_df
        path = self.config.reference_dir / "trial_reference_distributions.csv"
        if not path.exists():
            return pd.DataFrame()
        self._ref_df = pd.read_csv(path)
        return self._ref_df

    def compare(
        self,
        feature_name: str,
        value: float,
        condition: Optional[str] = None,
        walking_speed: Optional[float] = None,
        camera_view: Optional[str] = None,
    ) -> ReferenceComparison:
        df = self._load_reference()
        if df.empty:
            return ReferenceComparison(
                feature_name=feature_name,
                value=value,
                comparability=ComparabilityStatus.insufficient_data,
                note="Reference data not available.",
            )

        # Filter by feature and condition if present
        subset = df[df["variable"] == feature_name] if "variable" in df.columns else pd.DataFrame()
        if subset.empty:
            return ReferenceComparison(
                feature_name=feature_name,
                value=value,
                comparability=ComparabilityStatus.insufficient_data,
                note=f"Feature '{feature_name}' not found in reference distributions.",
            )

        if condition and "condition" in subset.columns:
            cond_subset = subset[subset["condition"] == condition]
            if not cond_subset.empty:
                subset = cond_subset

        # Get summary stats
        mean_val = subset["mean"].mean() if "mean" in subset.columns else None
        std_val = subset["std"].mean() if "std" in subset.columns else None
        median_val = subset["median"].mean() if "median" in subset.columns else None
        n_ref = int(subset.shape[0])

        percentile = z_score = None
        if mean_val is not None and std_val is not None and std_val > 0:
            z_score = float((value - mean_val) / std_val)
            # Approximate percentile from z-score
            try:
                from scipy.stats import norm
                percentile = float(norm.cdf(z_score) * 100)
            except ImportError:
                # Approximate percentile without scipy
                import math
                percentile = float(50 * (1 + math.erf(z_score / math.sqrt(2))))

        # Comparability: flag speed dependency
        comparability = ComparabilityStatus.comparable
        notes = ["Research dataset distribution. Not a validated clinical norm."]
        if walking_speed is not None:
            notes.append(
                "Walking speed may influence this metric. Speed-matched comparison is recommended."
            )
            comparability = ComparabilityStatus.conditionally_comparable

        return ReferenceComparison(
            feature_name=feature_name,
            value=value,
            reference_median=median_val,
            reference_sd=std_val,
            percentile_position=percentile,
            z_score=z_score,
            n_reference=n_ref,
            condition=condition or "",
            comparability=comparability,
            note=" ".join(notes),
        )
