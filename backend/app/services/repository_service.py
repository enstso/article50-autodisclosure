import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from git import Repo
from git.exc import GitCommandError, GitCommandNotFound, InvalidGitRepositoryError

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    GitUnavailableError,
    InvalidRepositoryUrlError,
    RepositoryCloneError,
    RepositoryNotFoundError,
    RepositoryTooLargeError,
)

GITHUB_COMPONENT_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?$")


def validate_repository_url(repository_url: str) -> str:
    """Validate and normalize a public GitHub HTTPS repository URL."""

    if not isinstance(repository_url, str):
        raise InvalidRepositoryUrlError("A GitHub HTTPS repository URL is required.")

    value = repository_url.strip()
    if not value or "\\" in value:
        raise InvalidRepositoryUrlError("A GitHub HTTPS repository URL is required.")

    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as error:
        raise InvalidRepositoryUrlError("The GitHub repository URL is invalid.") from error
    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() != "github.com"
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise InvalidRepositoryUrlError(
            "Only public https://github.com/{owner}/{repository} URLs are supported."
        )

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise InvalidRepositoryUrlError(
            "Only public https://github.com/{owner}/{repository} URLs are supported."
        )

    owner, repository = parts
    if repository.endswith(".git"):
        repository = repository[:-4]
    if (
        not owner
        or not repository
        or not all(GITHUB_COMPONENT_PATTERN.fullmatch(part) for part in (owner, repository))
    ):
        raise InvalidRepositoryUrlError("The GitHub repository URL is invalid.")

    return f"https://github.com/{owner}/{repository}"


class RepositoryService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def clone_repository(self, repository_url: str, destination: Path) -> Path:
        normalized_url = validate_repository_url(repository_url)
        if destination.exists():
            raise RepositoryCloneError("The repository workspace is not empty.")

        try:
            Repo.clone_from(
                normalized_url,
                destination,
                depth=1,
                multi_options=["--single-branch", "--no-tags", "--no-recurse-submodules"],
                env={
                    "GIT_ASKPASS": "",
                    "SSH_ASKPASS": "",
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "credential.helper",
                    "GIT_CONFIG_VALUE_0": "",
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_LFS_SKIP_SMUDGE": "1",
                    "GIT_TERMINAL_PROMPT": "0",
                },
            )
        except GitCommandNotFound as error:
            raise GitUnavailableError("Git is unavailable on the server.") from error
        except GitCommandError as error:
            message = f"{error.stderr or ''} {error.stdout or ''}".lower()
            if "repository not found" in message or "not found" in message:
                raise RepositoryNotFoundError("Public GitHub repository not found.") from error
            raise RepositoryCloneError(
                "The public GitHub repository could not be cloned."
            ) from error
        except OSError as error:
            raise RepositoryCloneError(
                "The public GitHub repository could not be cloned."
            ) from error

        size_bytes = self._repository_size(destination)
        max_bytes = self.settings.max_repository_size_mb * 1024 * 1024
        if size_bytes > max_bytes:
            raise RepositoryTooLargeError(
                f"Repository exceeds the {self.settings.max_repository_size_mb} MB size limit."
            )
        return destination

    @staticmethod
    def _repository_size(repository_path: Path) -> int:
        total = 0
        for path in repository_path.rglob("*"):
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        return total

    def get_repository_metadata(self, repository_path: Path) -> dict[str, str | int]:
        try:
            repository = Repo(repository_path)
            commit = repository.head.commit.hexsha
            branch = repository.active_branch.name
        except (GitCommandError, InvalidGitRepositoryError, TypeError, ValueError) as error:
            raise RepositoryCloneError("Repository metadata could not be read.") from error

        return {
            "commit": commit,
            "branch": branch,
            "size_bytes": self._repository_size(repository_path),
        }


def clone_repository(repository_url: str, destination: Path) -> Path:
    return RepositoryService().clone_repository(repository_url, destination)


def get_repository_metadata(repository_path: Path) -> dict[str, str | int]:
    return RepositoryService().get_repository_metadata(repository_path)
