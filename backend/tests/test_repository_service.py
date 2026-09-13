from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.exceptions import InvalidRepositoryUrlError, RepositoryTooLargeError
from app.services.repository_service import RepositoryService, validate_repository_url


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://github.com/openai/openai-python", "https://github.com/openai/openai-python"),
        ("https://github.com/openai/openai-python.git", "https://github.com/openai/openai-python"),
        (" https://github.com/openai/openai-python/ ", "https://github.com/openai/openai-python"),
    ],
)
def test_validate_repository_url_accepts_github_https(value: str, expected: str) -> None:
    assert validate_repository_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://gitlab.com/owner/repository",
        "https://localhost/owner/repository",
        "https://127.0.0.1/owner/repository",
        "https://0.0.0.0/owner/repository",
        "https://10.0.0.1/owner/repository",
        "https://172.16.0.1/owner/repository",
        "https://192.168.1.1/owner/repository",
        "file:///tmp/repository",
        "ssh://git@github.com/owner/repository",
        "git@github.com:owner/repository.git",
        "C:\\projects\\repository",
        "/home/user/repository",
        "https://github.com/owner/repository/issues",
        "https://github.com:443/owner/repository",
    ],
)
def test_validate_repository_url_rejects_unsafe_sources(value: str) -> None:
    with pytest.raises(InvalidRepositoryUrlError):
        validate_repository_url(value)


def test_clone_is_shallow_non_interactive_and_skips_submodules(tmp_path) -> None:
    destination = tmp_path / "repository"

    def fake_clone(_url, target, **_kwargs) -> None:
        target.mkdir()
        (target / "README.md").write_text("fixture", encoding="utf-8")

    service = RepositoryService(Settings(workspace_path=tmp_path))
    with patch("app.services.repository_service.Repo.clone_from", side_effect=fake_clone) as clone:
        result = service.clone_repository("https://github.com/example/repository", destination)

    assert result == destination
    call = clone.call_args
    assert call.args[:2] == ("https://github.com/example/repository", destination)
    assert call.kwargs["depth"] == 1
    assert "--no-recurse-submodules" in call.kwargs["multi_options"]
    assert call.kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert call.kwargs["env"]["GIT_LFS_SKIP_SMUDGE"] == "1"
    assert call.kwargs["env"]["GIT_CONFIG_KEY_0"] == "credential.helper"
    assert call.kwargs["env"]["GIT_CONFIG_VALUE_0"] == ""


def test_clone_rejects_repository_over_configured_size(tmp_path) -> None:
    destination = tmp_path / "repository"

    def fake_large_clone(_url, target, **_kwargs) -> None:
        target.mkdir()
        (target / "large.bin").write_bytes(b"x" * (1024 * 1024 + 1))

    service = RepositoryService(Settings(workspace_path=tmp_path, max_repository_size_mb=1))
    with (
        patch(
            "app.services.repository_service.Repo.clone_from",
            side_effect=fake_large_clone,
        ),
        pytest.raises(RepositoryTooLargeError, match="1 MB"),
    ):
        service.clone_repository("https://github.com/example/repository", destination)
