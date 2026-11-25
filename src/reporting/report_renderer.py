import json
from pathlib import Path
from typing import Optional
from src.reporting.report_schema import GaitReport
from src.core.config import AppConfig
from src.core.logging import get_logger

logger = get_logger(__name__)


class ReportRenderer:
    """Renders and persists individual and professional reports."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self._individual_dir = self.config.project_root / "outputs" / "reports" / "individual"
        self._professional_dir = self.config.project_root / "outputs" / "reports" / "professional"
        self._individual_dir.mkdir(parents=True, exist_ok=True)
        self._professional_dir.mkdir(parents=True, exist_ok=True)

    def save(self, report: GaitReport) -> Path:
        out_dir = self._individual_dir if report.report_type.value == "individual" else self._professional_dir
        out_path = out_dir / f"{report.report_id}.md"
        out_path.write_text(report.content_md, encoding="utf-8")

        meta_path = out_dir / f"{report.report_id}_meta.json"
        meta_path.write_text(report.model_dump_json(exclude={"content_md", "content_html"}, indent=2))

        logger.info("Saved %s report %s", report.report_type.value, report.report_id)
        return out_path
