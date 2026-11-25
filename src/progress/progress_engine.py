import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from src.progress.baseline_builder import build_baseline
from src.progress.session_comparator import compare_to_baseline
from src.progress.trend_analyzer import analyze_trends
from src.progress.progress_schema import Baseline, ProgressReport
from src.core.config import AppConfig
from src.core.logging import get_logger

logger = get_logger(__name__)


class ProgressEngine:
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self._baselines_dir = self.config.processed_dir / "baselines"
        self._progress_dir = self.config.processed_dir / "progress"
        self._baselines_dir.mkdir(parents=True, exist_ok=True)
        self._progress_dir.mkdir(parents=True, exist_ok=True)

    def build_and_save_baseline(
        self,
        subject_id: str,
        session_features: List[Dict[str, Any]],
        session_ids: List[str],
        conditions: Optional[List[str]] = None,
    ) -> Optional[Baseline]:
        # Find previous version
        existing = list(self._baselines_dir.glob(f"{subject_id}_baseline_v*.json"))
        prev_version = max(
            (int(f.stem.split("_v")[-1]) for f in existing), default=0
        )

        baseline = build_baseline(
            subject_id=subject_id,
            session_features=session_features,
            session_ids=session_ids,
            conditions=conditions,
            previous_version=prev_version,
        )
        if baseline is None:
            return None

        # Mark old baselines as not current
        for old_file in existing:
            try:
                data = json.loads(old_file.read_text())
                data["is_current"] = False
                old_file.write_text(json.dumps(data, indent=2))
            except Exception:
                pass

        out_path = self._baselines_dir / f"{subject_id}_baseline_v{baseline.version}.json"
        out_path.write_text(baseline.model_dump_json(indent=2))
        logger.info("Saved baseline v%d for subject %s", baseline.version, subject_id)
        return baseline

    def load_current_baseline(self, subject_id: str) -> Optional[Baseline]:
        files = sorted(self._baselines_dir.glob(f"{subject_id}_baseline_v*.json"))
        for f in reversed(files):
            try:
                data = json.loads(f.read_text())
                if data.get("is_current", True):
                    return Baseline.model_validate(data)
            except Exception:
                pass
        return None

    def compute_progress(
        self,
        subject_id: str,
        current_session_id: str,
        current_features: Dict[str, Any],
        current_ctx: Optional[Dict[str, Any]] = None,
    ) -> Optional[ProgressReport]:
        baseline = self.load_current_baseline(subject_id)
        if baseline is None:
            logger.warning("No baseline found for subject %s", subject_id)
            return None

        report = compare_to_baseline(
            subject_id=subject_id,
            current_session_id=current_session_id,
            current_features=current_features,
            baseline=baseline,
            current_ctx=current_ctx,
            baseline_ctx=baseline.context_summary or None,
        )

        out_path = self._progress_dir / f"{subject_id}_{current_session_id}_progress.json"
        out_path.write_text(report.model_dump_json(indent=2))
        return report
