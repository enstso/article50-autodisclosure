import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from strands import tool

from app.core.config import Settings, get_settings
from app.core.exceptions import BinaryFileError, UnsafePathError
from app.core.repository_rules import IMPORTANT_FILE_NAMES, LANGUAGE_BY_SUFFIX, is_ignored
from app.services.workspace_service import WorkspaceService

MAX_SEARCH_RESULTS = 50
MAX_SEARCH_QUERY_LENGTH = 200
MAX_SNIPPET_LENGTH = 240


class RepositoryInspector:
    """Deterministic, read-only inspection of an isolated repository checkout."""

    def __init__(
        self,
        settings: Settings | None = None,
        workspace_service: WorkspaceService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.workspace_service = workspace_service or WorkspaceService(self.settings)

    def _root(self, scan_id: str) -> Path:
        root = self.workspace_service.get_repository_path(scan_id).resolve()
        if not root.is_dir():
            raise UnsafePathError("Repository workspace does not exist.")
        return root

    def _safe_path(self, scan_id: str, relative_path: str, *, allow_root: bool = False) -> Path:
        if not isinstance(relative_path, str) or "\x00" in relative_path:
            raise UnsafePathError("Repository path is unsafe.")

        normalized = relative_path.strip().replace("\\", "/")
        posix_path = PurePosixPath(normalized)
        windows_path = PureWindowsPath(relative_path)
        if (
            posix_path.is_absolute()
            or windows_path.is_absolute()
            or windows_path.drive
            or ".." in posix_path.parts
        ):
            raise UnsafePathError("Repository path is unsafe.")
        if not allow_root and normalized in {"", "."}:
            raise UnsafePathError("A repository-relative file path is required.")
        if is_ignored(Path(*posix_path.parts)):
            raise UnsafePathError("Ignored repository paths cannot be inspected.")

        root = self._root(scan_id)
        candidate = (root / Path(*posix_path.parts)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise UnsafePathError("Repository path is unsafe.") from error
        return candidate

    def _iter_files(self, scan_id: str) -> list[Path]:
        root = self._root(scan_id)
        files: list[Path] = []
        for current, directory_names, file_names in os.walk(root, followlinks=False):
            current_path = Path(current)
            relative_current = current_path.relative_to(root)
            directory_names[:] = sorted(
                name
                for name in directory_names
                if not is_ignored(relative_current / name)
                and not (current_path / name).is_symlink()
            )
            for name in sorted(file_names):
                path = current_path / name
                if path.is_symlink() or is_ignored(path.relative_to(root)):
                    continue
                files.append(path)
        return files

    def get_repository_structure(self, scan_id: str) -> dict[str, Any]:
        root = self._root(scan_id)
        files = self._iter_files(scan_id)
        relative_files = [path.relative_to(root).as_posix() for path in files]

        top_level_directories = sorted(
            path.name
            for path in root.iterdir()
            if path.is_dir() and not path.is_symlink() and not is_ignored(Path(path.name))
        )
        important_files = sorted(
            relative for relative in relative_files if Path(relative).name in IMPORTANT_FILE_NAMES
        )
        languages = sorted(
            {
                language
                for path in files
                if (language := LANGUAGE_BY_SUFFIX.get(path.suffix.lower())) is not None
            }
        )
        frameworks = self._detect_frameworks(files, root)

        return {
            "total_files": len(files),
            "top_level_directories": top_level_directories,
            "important_files": important_files,
            "languages": languages,
            "frameworks": frameworks,
        }

    def _detect_frameworks(self, files: list[Path], root: Path) -> list[str]:
        frameworks: set[str] = set()
        max_bytes = self.settings.max_file_size_kb * 1024

        for path in files:
            relative = path.relative_to(root).as_posix()
            name = path.name.lower()
            if path.stat().st_size > max_bytes:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            if name == "package.json":
                try:
                    package = json.loads(content)
                except json.JSONDecodeError:
                    package = {}
                dependencies = {
                    str(key).lower()
                    for section in ("dependencies", "devDependencies", "peerDependencies")
                    for key in package.get(section, {})
                }
                package_frameworks = {
                    "react": "React",
                    "next": "Next.js",
                    "vue": "Vue",
                    "@angular/core": "Angular",
                    "express": "Express",
                    "@nestjs/core": "NestJS",
                }
                frameworks.update(
                    display
                    for dependency, display in package_frameworks.items()
                    if dependency in dependencies
                )

            if name in {"requirements.txt", "pyproject.toml", "pipfile"}:
                lowered = content.lower()
                python_frameworks = {
                    "fastapi": "FastAPI",
                    "flask": "Flask",
                    "django": "Django",
                }
                frameworks.update(
                    display
                    for dependency, display in python_frameworks.items()
                    if dependency in lowered
                )

            if relative.endswith(("vite.config.js", "vite.config.ts")):
                # Vite is build tooling rather than an application framework, so it is not returned.
                continue

        return sorted(frameworks)

    def list_directory(self, scan_id: str, relative_path: str) -> dict[str, list[str]]:
        directory = self._safe_path(scan_id, relative_path, allow_root=True)
        if not directory.is_dir():
            raise UnsafePathError("Repository directory does not exist.")

        files: list[str] = []
        directories: list[str] = []
        root = self._root(scan_id)
        for entry in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
            relative = entry.relative_to(root)
            if entry.is_symlink() or is_ignored(relative):
                continue
            if entry.is_dir():
                directories.append(entry.name)
            elif entry.is_file():
                files.append(entry.name)
        return {"files": files, "directories": directories}

    def read_source_file(self, scan_id: str, relative_path: str) -> dict[str, Any]:
        path = self._safe_path(scan_id, relative_path)
        if not path.is_file() or path.is_symlink():
            raise UnsafePathError("Repository file does not exist.")

        max_bytes = self.settings.max_file_size_kb * 1024
        try:
            with path.open("rb") as file_handle:
                payload = file_handle.read(max_bytes + 1)
        except OSError as error:
            raise UnsafePathError("Repository file could not be read.") from error

        truncated = len(payload) > max_bytes
        payload = payload[:max_bytes]
        if b"\x00" in payload:
            raise BinaryFileError("Binary files cannot be read.")
        try:
            content = payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise BinaryFileError("Binary files cannot be read.") from error

        root = self._root(scan_id)
        return {
            "path": path.relative_to(root).as_posix(),
            "content": content,
            "truncated": truncated,
        }

    def search_repository(self, scan_id: str, query: str) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("A non-empty search query is required.")
        if len(query) > MAX_SEARCH_QUERY_LENGTH:
            raise ValueError(f"Search queries are limited to {MAX_SEARCH_QUERY_LENGTH} characters.")

        root = self._root(scan_id)
        lowered_query = query.casefold()
        max_bytes = self.settings.max_file_size_kb * 1024
        results: list[dict[str, Any]] = []

        for path in self._iter_files(scan_id):
            if path.stat().st_size > max_bytes:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if "\x00" in content:
                continue

            for line_number, line in enumerate(content.splitlines(), start=1):
                if lowered_query not in line.casefold():
                    continue
                snippet = line.strip()
                if len(snippet) > MAX_SNIPPET_LENGTH:
                    snippet = f"{snippet[: MAX_SNIPPET_LENGTH - 1]}…"
                results.append(
                    {
                        "file": path.relative_to(root).as_posix(),
                        "line": line_number,
                        "snippet": snippet,
                    }
                )
                if len(results) >= MAX_SEARCH_RESULTS:
                    return results
        return results


def _inspector() -> RepositoryInspector:
    return RepositoryInspector()


@tool
def get_repository_structure(scan_id: str) -> dict[str, Any]:
    """Inspect the repository tree and detect basic languages and frameworks.

    Args:
        scan_id: Backend-generated scan identifier for the isolated repository.
    """

    return _inspector().get_repository_structure(scan_id)


@tool
def list_directory(scan_id: str, relative_path: str) -> dict[str, list[str]]:
    """List immediate files and directories under a safe repository-relative path.

    Args:
        scan_id: Backend-generated scan identifier for the isolated repository.
        relative_path: Path relative to the repository root; use an empty string for the root.
    """

    return _inspector().list_directory(scan_id, relative_path)


@tool
def read_source_file(scan_id: str, relative_path: str) -> dict[str, Any]:
    """Read a UTF-8 source file within the configured size limit without executing it.

    Args:
        scan_id: Backend-generated scan identifier for the isolated repository.
        relative_path: Source-code or text path relative to the repository root.
    """

    return _inspector().read_source_file(scan_id, relative_path)


@tool
def search_repository(scan_id: str, query: str) -> list[dict[str, Any]]:
    """Search repository text deterministically and return bounded line matches.

    Args:
        scan_id: Backend-generated scan identifier for the isolated repository.
        query: Case-insensitive literal text to find.
    """

    return _inspector().search_repository(scan_id, query)
