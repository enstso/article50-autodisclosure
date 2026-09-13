import re
from pathlib import Path
from typing import Any

from strands import tool

from app.core.ai_detection_rules import (
    AI_DEPENDENCIES,
    AI_USAGE_PATTERNS,
    DEPENDENCY_MANIFEST_NAMES,
)
from app.core.config import Settings, get_settings
from app.tools.repository_tools import (
    MAX_SEARCH_QUERY_LENGTH,
    MAX_SEARCH_RESULTS,
    MAX_SNIPPET_LENGTH,
    RepositoryInspector,
)

SOURCE_SUFFIXES = frozenset(
    {
        ".cs",
        ".go",
        ".java",
        ".js",
        ".jsx",
        ".kt",
        ".php",
        ".py",
        ".rb",
        ".rs",
        ".swift",
        ".ts",
        ".tsx",
        ".vue",
    }
)

ROUTE_PATTERNS = (
    re.compile(
        r"@\s*(?:app|router|blueprint)\s*\.\s*"
        r"(?P<method>get|post|put|patch|delete|options|head|route)\s*"
        r"\(\s*[\"'](?P<path>/[^\"']*)[\"']",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:app|router)\s*\.\s*(?P<method>get|post|put|patch|delete|options|head)"
        r"\s*\(\s*[\"'](?P<path>/[^\"']*)[\"']",
        re.IGNORECASE,
    ),
    re.compile(
        r"@(?P<method>Get|Post|Put|Patch|Delete)\s*\(\s*[\"'](?P<path>/?[^\"']*)[\"']",
    ),
)

ENDPOINT_CALL_PATTERN = re.compile(
    r"\b(?:fetch|axios\s*\.\s*(?:get|post|put|patch|delete)|"
    r"api\s*\.\s*(?:get|post|put|patch|delete)|apiUrl)\s*\(",
    re.IGNORECASE,
)

SYMBOL_PATTERN = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$.-]{0,127}$")


class AIDetectionInspector:
    """Bounded static detectors exposed to the AI interaction agent as tools."""

    def __init__(
        self,
        settings: Settings | None = None,
        repository_inspector: RepositoryInspector | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository_inspector or RepositoryInspector(self.settings)

    def _text_lines(self, path: Path) -> list[str] | None:
        if path.stat().st_size > self.settings.max_file_size_kb * 1024:
            return None
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        if "\x00" in content:
            return None
        return content.splitlines()

    def detect_ai_usage(self, scan_id: str) -> dict[str, list[dict[str, Any]]]:
        root = self.repository._root(scan_id)
        dependencies: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        dependency_keys: set[tuple[str, str, str]] = set()
        candidate_keys: set[tuple[str, int, str, str]] = set()

        for path in self.repository._iter_files(scan_id):
            lines = self._text_lines(path)
            if lines is None:
                continue
            relative = path.relative_to(root).as_posix()

            if path.name.casefold() in DEPENDENCY_MANIFEST_NAMES:
                for line_number, line in enumerate(lines, start=1):
                    for dependency in AI_DEPENDENCIES:
                        if not _contains_package(line, dependency.package):
                            continue
                        key = (dependency.provider, dependency.package, relative)
                        if key in dependency_keys:
                            continue
                        dependency_keys.add(key)
                        dependencies.append(
                            {
                                "provider": dependency.provider,
                                "package": dependency.package,
                                "file": relative,
                                "line": line_number,
                                "snippet": _snippet(line),
                            }
                        )

            if path.suffix.casefold() not in SOURCE_SUFFIXES:
                continue
            for line_number, line in enumerate(lines, start=1):
                for usage_pattern in AI_USAGE_PATTERNS:
                    if usage_pattern.pattern.search(line) is None:
                        continue
                    key = (relative, line_number, usage_pattern.provider, usage_pattern.name)
                    if key in candidate_keys:
                        continue
                    candidate_keys.add(key)
                    candidates.append(
                        {
                            "provider": usage_pattern.provider,
                            "pattern": usage_pattern.name,
                            "kind": usage_pattern.kind,
                            "file": relative,
                            "line": line_number,
                            "snippet": _snippet(line),
                        }
                    )

        dependencies.sort(key=lambda item: (item["file"], item["line"], item["package"]))
        candidates.sort(key=lambda item: (item["file"], item["line"], item["pattern"]))
        return {"dependencies": dependencies, "usage_candidates": candidates}

    def find_api_routes(self, scan_id: str) -> list[dict[str, Any]]:
        root = self.repository._root(scan_id)
        routes: list[dict[str, Any]] = []
        seen: set[tuple[str, int, str, str]] = set()

        for path in self.repository._iter_files(scan_id):
            if path.suffix.casefold() not in SOURCE_SUFFIXES:
                continue
            lines = self._text_lines(path)
            if lines is None:
                continue
            relative = path.relative_to(root).as_posix()

            for line_number, line in enumerate(lines, start=1):
                for route_pattern in ROUTE_PATTERNS:
                    match = route_pattern.search(line)
                    if match is None:
                        continue
                    method = match.group("method").upper()
                    if method == "ROUTE":
                        method = "ANY"
                    route_path = match.group("path") or "/"
                    if not route_path.startswith("/"):
                        route_path = f"/{route_path}"
                    key = (relative, line_number, method, route_path)
                    if key not in seen:
                        seen.add(key)
                        routes.append(
                            {
                                "method": method,
                                "path": route_path,
                                "file": relative,
                                "line": line_number,
                                "snippet": _snippet(line),
                            }
                        )

            next_route = _next_route_path(relative)
            if next_route is not None:
                for line_number, line in enumerate(lines, start=1):
                    match = re.search(
                        r"\bexport\s+(?:async\s+)?function\s+"
                        r"(?P<method>GET|POST|PUT|PATCH|DELETE)\b",
                        line,
                    )
                    if match is None:
                        continue
                    method = match.group("method")
                    key = (relative, line_number, method, next_route)
                    if key not in seen:
                        seen.add(key)
                        routes.append(
                            {
                                "method": method,
                                "path": next_route,
                                "file": relative,
                                "line": line_number,
                                "snippet": _snippet(line),
                            }
                        )

        return sorted(routes, key=lambda item: (item["file"], item["line"], item["method"]))

    def search_endpoint_usage(self, scan_id: str, endpoint: str) -> list[dict[str, Any]]:
        if not isinstance(endpoint, str) or not endpoint.startswith("/"):
            raise ValueError("A root-relative API endpoint is required.")
        if len(endpoint) > MAX_SEARCH_QUERY_LENGTH:
            raise ValueError(f"Endpoints are limited to {MAX_SEARCH_QUERY_LENGTH} characters.")

        root = self.repository._root(scan_id)
        route_positions = {
            (route["file"], route["line"]) for route in self.find_api_routes(scan_id)
        }
        results: list[dict[str, Any]] = []

        for path in self.repository._iter_files(scan_id):
            if path.suffix.casefold() not in SOURCE_SUFFIXES:
                continue
            lines = self._text_lines(path)
            if lines is None:
                continue
            relative = path.relative_to(root).as_posix()
            for line_number, line in enumerate(lines, start=1):
                if endpoint not in line or (relative, line_number) in route_positions:
                    continue
                context = "\n".join(lines[max(0, line_number - 3) : line_number + 2])
                if ENDPOINT_CALL_PATTERN.search(context) is None:
                    continue
                results.append(
                    {
                        "file": relative,
                        "line": line_number,
                        "snippet": _snippet(line),
                    }
                )
                if len(results) >= MAX_SEARCH_RESULTS:
                    return results
        return results

    def find_symbol_references(self, scan_id: str, symbol: str) -> list[dict[str, Any]]:
        if not isinstance(symbol, str) or SYMBOL_PATTERN.fullmatch(symbol) is None:
            raise ValueError("A simple function, class, service, or imported symbol is required.")
        return self.repository.search_repository(scan_id, symbol)


def _contains_package(line: str, package: str) -> bool:
    boundary = r"A-Za-z0-9_@./-"
    return (
        re.search(
            rf"(?<![{boundary}]){re.escape(package)}(?![{boundary}])",
            line,
            re.IGNORECASE,
        )
        is not None
    )


def _snippet(line: str) -> str:
    value = line.strip()
    if len(value) <= MAX_SNIPPET_LENGTH:
        return value
    return f"{value[: MAX_SNIPPET_LENGTH - 1]}…"


def _next_route_path(relative_path: str) -> str | None:
    path = Path(relative_path)
    parts = path.parts
    if len(parts) >= 3 and parts[-1].casefold() in {"route.ts", "route.tsx", "route.js"}:
        try:
            api_index = tuple(part.casefold() for part in parts).index("api")
        except ValueError:
            return None
        segments = parts[api_index + 1 : -1]
        return "/api" + (f"/{'/'.join(segments)}" if segments else "")
    if "pages" in tuple(part.casefold() for part in parts):
        try:
            api_index = tuple(part.casefold() for part in parts).index("api")
        except ValueError:
            return None
        segments = list(parts[api_index + 1 :])
        if not segments:
            return None
        segments[-1] = Path(segments[-1]).stem
        return f"/api/{'/'.join(segments)}"
    return None


def _ai_inspector() -> AIDetectionInspector:
    return AIDetectionInspector()


@tool
def detect_ai_usage(scan_id: str) -> dict[str, list[dict[str, Any]]]:
    """Find deterministic AI dependency signals and source-level usage candidates.

    Args:
        scan_id: Backend-generated scan identifier for the isolated repository.
    """

    return _ai_inspector().detect_ai_usage(scan_id)


@tool
def find_api_routes(scan_id: str) -> list[dict[str, Any]]:
    """Find lightweight FastAPI, Flask, Express, NestJS, and Next.js API route evidence.

    Args:
        scan_id: Backend-generated scan identifier for the isolated repository.
    """

    return _ai_inspector().find_api_routes(scan_id)


@tool
def search_endpoint_usage(scan_id: str, endpoint: str) -> list[dict[str, Any]]:
    """Find bounded source locations that call a root-relative API endpoint.

    Args:
        scan_id: Backend-generated scan identifier for the isolated repository.
        endpoint: API path such as /api/chat.
    """

    return _ai_inspector().search_endpoint_usage(scan_id, endpoint)


@tool
def find_symbol_references(scan_id: str, symbol: str) -> list[dict[str, Any]]:
    """Find bounded literal references to a simple function, class, service, or import symbol.

    Args:
        scan_id: Backend-generated scan identifier for the isolated repository.
        symbol: Symbol name to search for without regular expressions.
    """

    return _ai_inspector().find_symbol_references(scan_id, symbol)
