import shutil
from pathlib import Path
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.exceptions import UnsafePathError


class WorkspaceService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = self.settings.workspace_path.resolve()

    @staticmethod
    def _validate_scan_id(scan_id: str) -> str:
        try:
            parsed = UUID(scan_id)
        except (ValueError, AttributeError) as error:
            raise UnsafePathError("Invalid scan identifier.") from error
        if str(parsed) != scan_id.lower():
            raise UnsafePathError("Invalid scan identifier.")
        return str(parsed)

    def get_workspace(self, scan_id: str) -> Path:
        safe_id = self._validate_scan_id(scan_id)
        path = (self.root / safe_id).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as error:
            raise UnsafePathError("Workspace path is unsafe.") from error
        return path

    def create_workspace(self, scan_id: str) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        workspace = self.get_workspace(scan_id)
        workspace.mkdir(parents=False, exist_ok=False)
        return workspace

    def get_repository_path(self, scan_id: str) -> Path:
        return self.get_workspace(scan_id) / "repository"

    def get_snapshot_path(self, scan_id: str, patch_id: str) -> Path:
        safe_patch_id = self._validate_scan_id(patch_id)
        snapshot = (self.get_workspace(scan_id) / "snapshots" / safe_patch_id).resolve()
        try:
            snapshot.relative_to(self.get_workspace(scan_id))
        except ValueError as error:
            raise UnsafePathError("Snapshot path is unsafe.") from error
        return snapshot

    def cleanup_workspace(self, scan_id: str) -> None:
        workspace = self.get_workspace(scan_id)
        if workspace.exists():
            shutil.rmtree(workspace)


def create_workspace(scan_id: str) -> Path:
    return WorkspaceService().create_workspace(scan_id)


def get_workspace(scan_id: str) -> Path:
    return WorkspaceService().get_workspace(scan_id)


def get_repository_path(scan_id: str) -> Path:
    return WorkspaceService().get_repository_path(scan_id)


def cleanup_workspace(scan_id: str) -> None:
    WorkspaceService().cleanup_workspace(scan_id)
