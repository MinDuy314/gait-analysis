"""End-to-end Milestone 2 pipeline: features, reference distributions, splits, and plots."""

from pathlib import Path
from typing import Dict, Optional

from src.core.config import AppConfig
from src.feature_extraction.npz_feature_extractor import run_feature_extraction
from src.reference.data_splits import generate_participant_splits
from src.reference.reference_builder import build_reference_distributions
from src.visualization.npz_plots import generate_milestone2_figures


def run_milestone2_pipeline(project_root: Optional[Path] = None) -> Dict[str, object]:
    """Run all Milestone 2 stages sequentially."""
    cfg = AppConfig(project_root=project_root)
    feat_outputs = run_feature_extraction(cfg)
    ref_outputs = build_reference_distributions(cfg)
    splits_path = generate_participant_splits(cfg)
    figures = generate_milestone2_figures(cfg)
    return {
        "features": feat_outputs,
        "reference": ref_outputs,
        "splits": splits_path,
        "figures": figures,
    }


if __name__ == "__main__":
    run_milestone2_pipeline()
