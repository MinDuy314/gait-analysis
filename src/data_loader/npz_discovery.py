"""NPZ dataset discovery module."""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field

from src.core.exceptions import DatasetDiscoveryError
from src.core.logging import get_logger

logger = get_logger(__name__)

EXPECTED_PARTICIPANTS: Set[str] = {f"Ref{i:02d}" for i in range(1, 14)}
KNOWN_CONDITIONS: Set[str] = {
    "level_down",
    "level_up",
    "ramp_10_down",
    "ramp_10_up",
    "ramp_75_down",
    "ramp_75_up",
    "ramp75_down",
    "ramp75_up",
}


class DiscoveredNPZFile(BaseModel):
    """Represents a single discovered NPZ trial file."""

    trial_id: str
    participant_id: str
    condition_dir: str
    filename: str
    relative_path: str
    absolute_path: str
    file_size_bytes: int
    sha256_hash: str


class DiscoveryReport(BaseModel):
    """Summary report of NPZ dataset discovery."""

    root_dir: str
    total_files_discovered: int
    participants_found: List[str] = Field(default_factory=list)
    missing_expected_participants: List[str] = Field(default_factory=list)
    conditions_found: List[str] = Field(default_factory=list)
    duplicate_filenames: Dict[str, List[str]] = Field(default_factory=dict)
    duplicate_content_hashes: Dict[str, List[str]] = Field(default_factory=dict)
    unexpected_paths: List[str] = Field(default_factory=list)
    files: List[DiscoveredNPZFile] = Field(default_factory=list)


def _compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def discover_npz_dataset(npz_root: Path, project_root: Optional[Path] = None) -> DiscoveryReport:
    """
    Discover all NPZ files in `npz_root`, extract directory metadata,
    and detect duplicates, missing participants, or unexpected structures.
    """
    if not npz_root.exists() or not npz_root.is_dir():
        raise DatasetDiscoveryError(f"NPZ root directory does not exist: {npz_root}")

    base_for_rel = project_root if project_root else npz_root
    npz_paths = sorted(npz_root.rglob("*.npz"))

    discovered_files: List[DiscoveredNPZFile] = []
    participants_set: Set[str] = set()
    conditions_set: Set[str] = set()
    unexpected_paths: List[str] = []
    by_filename: Dict[str, List[str]] = {}
    by_hash: Dict[str, List[str]] = {}

    for path in npz_paths:
        rel_to_npz = path.relative_to(npz_root)
        parts = rel_to_npz.parts
        rel_path_str = str(path.relative_to(base_for_rel)).replace("\\", "/")

        if len(parts) != 3:
            unexpected_paths.append(rel_path_str)
            participant_id = parts[0] if len(parts) >= 1 else "unknown"
            condition_dir = parts[1] if len(parts) >= 2 else "unknown"
        else:
            participant_id, condition_dir, _ = parts
            if condition_dir not in KNOWN_CONDITIONS:
                unexpected_paths.append(rel_path_str)

        participants_set.add(participant_id)
        conditions_set.add(condition_dir)

        trial_id = f"{condition_dir}__{path.stem}"
        file_hash = _compute_sha256(path)
        file_size = path.stat().st_size

        by_filename.setdefault(path.name, []).append(rel_path_str)
        by_hash.setdefault(file_hash, []).append(rel_path_str)

        discovered_files.append(
            DiscoveredNPZFile(
                trial_id=trial_id,
                participant_id=participant_id,
                condition_dir=condition_dir,
                filename=path.name,
                relative_path=rel_path_str,
                absolute_path=str(path),
                file_size_bytes=file_size,
                sha256_hash=file_hash,
            )
        )

    dup_filenames = {k: v for k, v in by_filename.items() if len(v) > 1}
    dup_hashes = {k: v for k, v in by_hash.items() if len(v) > 1}
    missing_participants = sorted(EXPECTED_PARTICIPANTS - participants_set)

    logger.info(
        "Discovered %d NPZ files across %d participants and %d conditions.",
        len(discovered_files),
        len(participants_set),
        len(conditions_set),
    )
    if missing_participants:
        logger.warning(
            "Expected participants missing from NPZ directory (check incomplete data): %s",
            missing_participants,
        )

    return DiscoveryReport(
        root_dir=str(npz_root),
        total_files_discovered=len(discovered_files),
        participants_found=sorted(participants_set),
        missing_expected_participants=missing_participants,
        conditions_found=sorted(conditions_set),
        duplicate_filenames=dup_filenames,
        duplicate_content_hashes=dup_hashes,
        unexpected_paths=unexpected_paths,
        files=discovered_files,
    )
