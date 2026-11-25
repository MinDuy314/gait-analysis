"""End-to-end Milestone 1 NPZ discovery, validation, and metadata pipeline."""

from pathlib import Path
from typing import Optional

from src.core.config import AppConfig
from src.core.logging import get_logger
from src.data_loader.metadata_generator import (
    generate_subject_index,
    generate_trial_index,
    generate_variable_dictionary,
)
from src.data_loader.npz_discovery import DiscoveryReport, discover_npz_dataset
from src.data_loader.npz_validator import ValidationReport, validate_all_npz, write_qc_reports

logger = get_logger(__name__)


def run_milestone1_pipeline(project_root: Optional[Path] = None) -> tuple[DiscoveryReport, ValidationReport]:
    """Execute NPZ discovery, schema validation, QC reporting, and metadata generation."""
    cfg = AppConfig(project_root=project_root)

    discovery_report = discover_npz_dataset(cfg.raw_npz_dir, project_root=cfg.project_root)
    validation_report = validate_all_npz(
        discovery_report.files,
        gait_cycle_points=cfg.gait_cycle_points,
    )

    write_qc_reports(validation_report, cfg.qc_dir)
    generate_trial_index(validation_report, cfg.metadata_dir / "trial_index.csv")
    generate_subject_index(validation_report, cfg.metadata_dir / "subject_index.csv")
    generate_variable_dictionary(cfg.metadata_dir / "variable_dictionary.csv")

    return discovery_report, validation_report


if __name__ == "__main__":
    run_milestone1_pipeline()
