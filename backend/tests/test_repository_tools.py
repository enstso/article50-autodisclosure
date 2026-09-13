import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import BinaryFileError, UnsafePathError
from app.services.workspace_service import WorkspaceService
from app.tools.repository_tools import RepositoryInspector

FIXTURE_REPOSITORY = Path(__file__).parent / "fixtures" / "sample_repository"


@pytest.fixture
def repository_inspector(tmp_path) -> tuple[RepositoryInspector, str, Path]:
    settings = Settings(workspace_path=tmp_path, max_file_size_kb=1)
    workspace_service = WorkspaceService(settings)
    scan_id = str(uuid4())
    workspace_service.create_workspace(scan_id)
    repository = workspace_service.get_repository_path(scan_id)
    shutil.copytree(FIXTURE_REPOSITORY, repository)
    return RepositoryInspector(settings, workspace_service), scan_id, repository


def test_repository_structure_detects_fixture_stack(repository_inspector) -> None:
    inspector, scan_id, _ = repository_inspector

    structure = inspector.get_repository_structure(scan_id)

    assert structure["total_files"] == 4
    assert structure["top_level_directories"] == ["backend", "frontend"]
    assert structure["languages"] == ["Python", "TypeScript"]
    assert structure["frameworks"] == ["FastAPI", "React"]
    assert "frontend/package.json" in structure["important_files"]
    assert "backend/requirements.txt" in structure["important_files"]


def test_list_read_and_search_are_deterministic(repository_inspector) -> None:
    inspector, scan_id, _ = repository_inspector

    listing = inspector.list_directory(scan_id, "backend")
    source = inspector.read_source_file(scan_id, "backend/app/main.py")
    matches = inspector.search_repository(scan_id, "FastAPI")

    assert listing == {"files": ["requirements.txt"], "directories": ["app"]}
    assert source["path"] == "backend/app/main.py"
    assert source["truncated"] is False
    assert {
        "file": "backend/app/main.py",
        "line": 1,
        "snippet": "from fastapi import FastAPI",
    } in matches


@pytest.mark.parametrize(
    "relative_path",
    ["..", "../", "../../etc/passwd", "/etc/passwd", "C:\\Windows\\system.ini"],
)
def test_repository_tools_reject_path_traversal(repository_inspector, relative_path: str) -> None:
    inspector, scan_id, _ = repository_inspector

    with pytest.raises(UnsafePathError):
        inspector.read_source_file(scan_id, relative_path)


def test_read_source_file_rejects_binary_and_truncates_large_text(repository_inspector) -> None:
    inspector, scan_id, repository = repository_inspector
    (repository / "binary.dat").write_bytes(b"text\x00binary")
    (repository / "large.txt").write_text("x" * 2048, encoding="utf-8")

    with pytest.raises(BinaryFileError):
        inspector.read_source_file(scan_id, "binary.dat")

    large = inspector.read_source_file(scan_id, "large.txt")
    assert large["truncated"] is True
    assert len(large["content"].encode()) == 1024


def test_repository_tools_ignore_dependency_directories(repository_inspector) -> None:
    inspector, scan_id, repository = repository_inspector
    ignored = repository / "node_modules" / "untrusted"
    ignored.mkdir(parents=True)
    (ignored / "payload.ts").write_text("FastAPI", encoding="utf-8")

    structure = inspector.get_repository_structure(scan_id)

    assert structure["total_files"] == 4
    with pytest.raises(UnsafePathError):
        inspector.list_directory(scan_id, "node_modules")
