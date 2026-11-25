"""Configuration loader and path resolution for the Gait Analysis Backend MVP."""

from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from src.core.exceptions import ConfigurationError


def get_project_root() -> Path:
    """Resolve the project root directory (parent of src/)."""
    return Path(__file__).resolve().parent.parent.parent


class AppConfig:
    """Central configuration container loaded from YAML files."""

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = Path(project_root) if project_root else get_project_root()
        self.dataset_cfg = self._load_yaml(self.project_root / "config" / "dataset_config.yaml")
        self.feature_cfg = self._load_yaml(self.project_root / "config" / "feature_config.yaml")

    @staticmethod
    def _load_yaml(path: Path) -> Dict[str, Any]:
        if not path.exists():
            raise ConfigurationError(f"Configuration file not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return data
        except yaml.YAMLError as exc:
            raise ConfigurationError(f"Failed to parse YAML file {path}: {exc}") from exc

    @property
    def raw_npz_dir(self) -> Path:
        raw_dir = self.dataset_cfg.get("dataset", {}).get("raw_dir", "data/raw")
        return self.project_root / raw_dir / "npz"

    @property
    def raw_c3d_dir(self) -> Path:
        raw_dir = self.dataset_cfg.get("dataset", {}).get("raw_dir", "data/raw")
        return self.project_root / raw_dir / "c3d"

    @property
    def raw_txt_dir(self) -> Path:
        raw_dir = self.dataset_cfg.get("dataset", {}).get("raw_dir", "data/raw")
        return self.project_root / raw_dir / "txt"

    @property
    def processed_dir(self) -> Path:
        proc_dir = self.dataset_cfg.get("dataset", {}).get("processed_dir", "data/processed")
        return self.project_root / proc_dir

    @property
    def qc_dir(self) -> Path:
        return self.processed_dir / "quality_control"

    @property
    def metadata_dir(self) -> Path:
        return self.project_root / "metadata"

    @property
    def gait_cycle_points(self) -> int:
        return int(self.dataset_cfg.get("dataset", {}).get("gait_cycle_points", 101))

    @property
    def trial_features_dir(self) -> Path:
        return self.processed_dir / "trial_features"

    @property
    def gait_curves_dir(self) -> Path:
        return self.processed_dir / "gait_curves"

    @property
    def reference_dir(self) -> Path:
        return self.processed_dir / "reference"

    @property
    def figures_dir(self) -> Path:
        return self.project_root / "outputs" / "figures"
