"""File retention policies and cleanup."""
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta
from src.core.logging import get_logger

logger = get_logger(__name__)


class RetentionManager:
    def __init__(self, default_retention_days: int = 90):
        self.default_retention_days = default_retention_days

    def purge_expired_files(self, base_dir: Path, max_age_days: Optional[int] = None) -> List[Path]:
        days = max_age_days or self.default_retention_days
        threshold = datetime.utcnow() - timedelta(days=days)
        deleted: List[Path] = []
        if not base_dir.exists():
            return deleted

        for file_path in base_dir.glob("**/*"):
            if file_path.is_file():
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < threshold:
                    try:
                        file_path.unlink()
                        deleted.append(file_path)
                        logger.info("Purged expired file: %s", file_path)
                    except Exception as e:
                        logger.error("Failed to delete expired file %s: %s", file_path, e)
        return deleted
