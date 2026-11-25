"""Storage manifest tracking."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


class StorageManifest:
    def __init__(self, manifest_path: Path):
        self.manifest_path = Path(manifest_path)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text())
            except Exception:
                return {}
        return {}

    def _save(self):
        self.manifest_path.write_text(json.dumps(self.entries, indent=2))

    def record_artifact(self, artifact_id: str, path: str, artifact_type: str, metadata: Optional[Dict[str, Any]] = None):
        self.entries[artifact_id] = {
            "path": path,
            "type": artifact_type,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        self._save()

    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        return self.entries.get(artifact_id)
