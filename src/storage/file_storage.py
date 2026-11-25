import hashlib
import shutil
import uuid
from pathlib import Path
from typing import Optional, Tuple
from src.core.logging import get_logger

logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB default


class FileStorage:
    def __init__(self, storage_root: Path, max_size_bytes: int = MAX_FILE_SIZE_BYTES):
        self.storage_root = Path(storage_root)
        self.max_size_bytes = max_size_bytes
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def _safe_server_filename(self, original: str) -> str:
        suffix = Path(original).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            suffix = ".bin"
        return f"{uuid.uuid4()}{suffix}"

    def save_upload(
        self,
        source_path: Path,
        original_filename: str,
        subject_id: str,
        session_id: str,
    ) -> Tuple[str, Path, int]:
        suffix = Path(original_filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension: {suffix}")

        size = source_path.stat().st_size
        if size > self.max_size_bytes:
            raise ValueError(f"File size {size} bytes exceeds limit {self.max_size_bytes} bytes")

        server_name = self._safe_server_filename(original_filename)
        dest_dir = self.storage_root / subject_id / session_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / server_name

        shutil.move(str(source_path), str(dest_path))
        logger.info("Stored upload %s -> %s (%d bytes)", original_filename, dest_path, size)
        return server_name, dest_path, size

    def delete_file(self, file_path: Path) -> bool:
        try:
            if file_path.exists():
                file_path.unlink()
                return True
        except Exception as e:
            logger.error("Failed to delete %s: %s", file_path, e)
        return False

    def compute_sha256(self, file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
