from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import UnsafePathError
from app.services.workspace_service import WorkspaceService


def test_workspace_is_isolated_by_backend_generated_scan_id(tmp_path) -> None:
    service = WorkspaceService(Settings(workspace_path=tmp_path))
    first_id = str(uuid4())
    second_id = str(uuid4())

    first = service.create_workspace(first_id)
    second = service.create_workspace(second_id)

    assert first != second
    assert service.get_repository_path(first_id) == first / "repository"
    assert service.get_repository_path(second_id) == second / "repository"


@pytest.mark.parametrize("scan_id", ["../escape", "not-a-uuid", "", "../../etc/passwd"])
def test_workspace_rejects_user_controlled_scan_paths(tmp_path, scan_id: str) -> None:
    service = WorkspaceService(Settings(workspace_path=tmp_path))

    with pytest.raises(UnsafePathError):
        service.get_workspace(scan_id)
