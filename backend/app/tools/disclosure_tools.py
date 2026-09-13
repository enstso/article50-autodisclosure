import re
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import Any

from strands import tool

from app.core.config import Settings, get_settings
from app.core.disclosure_detection_rules import (
    has_dynamic_disclosure_signal,
    is_ambiguous_ai_context,
    is_explicit_ai_disclosure,
)
from app.models import AIInteractionFlow
from app.tools.repository_tools import MAX_SEARCH_RESULTS, MAX_SNIPPET_LENGTH, RepositoryInspector

UI_SUFFIXES = frozenset({".html", ".htm", ".js", ".jsx", ".json", ".svelte", ".ts", ".tsx", ".vue"})
COMPONENT_SUFFIXES = (".tsx", ".jsx", ".vue", ".svelte", ".ts", ".js", ".json")
MAX_RELATED_FILES = 24

IMPORT_PATTERN = re.compile(
    r"(?:\bfrom\s+|\bimport\s*\(|\brequire\s*\()\s*[\"'](?P<path>\.{1,2}/[^\"']+)[\"']"
)
VISIBLE_ATTRIBUTE_PATTERN = re.compile(
    r"\b(?:aria-label|title|placeholder|alt|data-tooltip)\s*=\s*[\"'](?P<text>[^\"']+)[\"']",
    re.IGNORECASE,
)
JSX_TEXT_PATTERN = re.compile(r">(?P<text>[^<>{}]+)<", re.MULTILINE)
JSX_STRING_EXPRESSION_PATTERN = re.compile(
    r"\{\s*[\"'`](?P<text>[^\"'`]+)[\"'`]\s*\}", re.MULTILINE
)
CONSTANT_STRING_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*[\"'`](?P<text>[^\"'`]+)[\"'`]"
)
JSON_VALUE_PATTERN = re.compile(r":\s*[\"'](?P<text>[^\"']+)[\"']\s*[,}]?")

_interaction_registry: dict[str, dict[str, AIInteractionFlow]] = {}
_registry_lock = Lock()


def register_scan_interactions(scan_id: str, interactions: list[AIInteractionFlow]) -> None:
    with _registry_lock:
        _interaction_registry[scan_id] = {
            item.id: item.model_copy(deep=True) for item in interactions
        }


def clear_scan_interactions(scan_id: str) -> None:
    with _registry_lock:
        _interaction_registry.pop(scan_id, None)


def _registered_interaction(scan_id: str, interaction_id: str) -> AIInteractionFlow:
    with _registry_lock:
        interaction = _interaction_registry.get(scan_id, {}).get(interaction_id)
        if interaction is None:
            raise ValueError("The requested interaction is not registered for this scan.")
        return interaction.model_copy(deep=True)


class DisclosureInspector:
    """Find user-visible disclosure text near a confirmed AI interaction."""

    def __init__(
        self,
        settings: Settings | None = None,
        repository_inspector: RepositoryInspector | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository_inspector or RepositoryInspector(self.settings)

    def relevant_ui_files(
        self, scan_id: str, interaction: AIInteractionFlow
    ) -> list[dict[str, str]]:
        entrypoint = (interaction.frontend_entrypoint or "").replace("\\", "/")
        if not entrypoint:
            return []
        try:
            self.repository.read_source_file(scan_id, entrypoint)
        except Exception:
            return []

        relations: dict[str, str] = {entrypoint: "frontend_entrypoint"}
        frontier = [entrypoint]
        for _ in range(2):
            next_frontier: list[str] = []
            for current in frontier:
                source = self.repository.read_source_file(scan_id, current)["content"]
                for import_path in self._relative_imports(scan_id, current, source):
                    if import_path not in relations and len(relations) < MAX_RELATED_FILES:
                        relations[import_path] = "related_component"
                        next_frontier.append(import_path)
            frontier = next_frontier

        # A parent component or layout that directly imports the interaction entrypoint is part of
        # the rendered context. This search is deterministic; no source is sent to the model here.
        for candidate in self._ui_files(scan_id):
            if candidate in relations or len(relations) >= MAX_RELATED_FILES:
                continue
            try:
                source = self.repository.read_source_file(scan_id, candidate)["content"]
            except Exception:
                continue
            if entrypoint in self._relative_imports(scan_id, candidate, source):
                relations[candidate] = "parent_component"

        return [
            {"file": file, "relation": relation}
            for file, relation in sorted(
                relations.items(), key=lambda item: (item[1] != "frontend_entrypoint", item[0])
            )
        ]

    def find_disclosure_candidates(
        self, scan_id: str, interaction_id: str
    ) -> list[dict[str, Any]]:
        interaction = _registered_interaction(scan_id, interaction_id)
        return self._matching_candidates(scan_id, interaction, is_explicit_ai_disclosure)

    def find_ambiguous_context(
        self, scan_id: str, interaction: AIInteractionFlow
    ) -> list[dict[str, Any]]:
        return self._matching_candidates(scan_id, interaction, is_ambiguous_ai_context)

    def has_dynamic_disclosure_context(
        self, scan_id: str, interaction: AIInteractionFlow
    ) -> bool:
        for relevant in self.relevant_ui_files(scan_id, interaction):
            source = self.repository.read_source_file(scan_id, relevant["file"])["content"]
            if has_dynamic_disclosure_signal(_without_comments(source)):
                return True
        return False

    def search_ui_text(self, scan_id: str, query: str) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("A non-empty UI text query is required.")
        if len(query) > 100:
            raise ValueError("UI text queries are limited to 100 characters.")

        lowered_query = query.casefold()
        matches: list[dict[str, Any]] = []
        for file in self._ui_files(scan_id):
            source = self.repository.read_source_file(scan_id, file)["content"]
            for visible in self._visible_strings(file, source):
                if lowered_query not in visible["text"].casefold():
                    continue
                matches.append({"file": file, **visible})
                if len(matches) >= MAX_SEARCH_RESULTS:
                    return matches
        return matches

    def _matching_candidates(
        self,
        scan_id: str,
        interaction: AIInteractionFlow,
        predicate: Any,
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for relevant in self.relevant_ui_files(scan_id, interaction):
            source = self.repository.read_source_file(scan_id, relevant["file"])["content"]
            for visible in self._visible_strings(relevant["file"], source):
                if predicate(visible["text"]):
                    candidates.append({**relevant, **visible})
        return candidates[:MAX_SEARCH_RESULTS]

    def _ui_files(self, scan_id: str) -> list[str]:
        root = self.repository._root(scan_id)
        output: list[str] = []
        for path in self.repository._iter_files(scan_id):
            relative = path.relative_to(root).as_posix()
            lowered_parts = {part.casefold() for part in PurePosixPath(relative).parts}
            if path.suffix.lower() not in UI_SUFFIXES:
                continue
            if "backend" in lowered_parts or path.name.casefold().startswith("readme"):
                continue
            output.append(relative)
        return output

    def _relative_imports(self, scan_id: str, source_file: str, source: str) -> list[str]:
        source_path = PurePosixPath(source_file)
        found: list[str] = []
        for match in IMPORT_PATTERN.finditer(_without_comments(source)):
            imported = source_path.parent.joinpath(match.group("path"))
            normalized = _normalize_relative(imported)
            for candidate in _import_candidates(normalized):
                try:
                    self.repository.read_source_file(scan_id, candidate)
                except Exception:
                    continue
                if Path(candidate).suffix.lower() in UI_SUFFIXES:
                    found.append(candidate)
                    break
        return found

    def _visible_strings(self, file: str, source: str) -> list[dict[str, Any]]:
        cleaned = _without_comments(source)
        items: list[dict[str, Any]] = []

        patterns = [VISIBLE_ATTRIBUTE_PATTERN, JSX_TEXT_PATTERN, JSX_STRING_EXPRESSION_PATTERN]
        for pattern in patterns:
            for match in pattern.finditer(cleaned):
                text = " ".join(match.group("text").split())
                if not _looks_like_user_text(text):
                    continue
                line = cleaned.count("\n", 0, match.start("text")) + 1
                items.append(_visible_item(source, line, text))

        rendered_names = {
            name
            for name in re.findall(r"\{\s*([A-Za-z_$][\w$]*)\s*\}", cleaned)
        }
        for match in CONSTANT_STRING_PATTERN.finditer(cleaned):
            if match.group("name") not in rendered_names:
                continue
            text = " ".join(match.group("text").split())
            if _looks_like_user_text(text):
                line = cleaned.count("\n", 0, match.start("text")) + 1
                items.append(_visible_item(source, line, text))

        path = PurePosixPath(file)
        translation_file = path.suffix.lower() == ".json" and any(
            part.casefold() in {"i18n", "locale", "locales", "translations"}
            for part in path.parts
        )
        if translation_file:
            for match in JSON_VALUE_PATTERN.finditer(cleaned):
                text = " ".join(match.group("text").split())
                if _looks_like_user_text(text):
                    line = cleaned.count("\n", 0, match.start("text")) + 1
                    items.append(_visible_item(source, line, text))

        unique: list[dict[str, Any]] = []
        seen: set[tuple[int, str]] = set()
        for item in items:
            key = (item["line"], item["text"].casefold())
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique


def _normalize_relative(path: PurePosixPath) -> str:
    parts: list[str] = []
    for part in path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def _import_candidates(path: str) -> list[str]:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix:
        return [path]
    return [
        *(f"{path}{extension}" for extension in COMPONENT_SUFFIXES),
        *(f"{path}/index{extension}" for extension in COMPONENT_SUFFIXES),
    ]


def _without_comments(source: str) -> str:
    def preserve_lines(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    without_blocks = re.sub(r"/\*[\s\S]*?\*/", preserve_lines, source)
    return re.sub(r"(?m)^\s*//.*$", "", without_blocks)


def _looks_like_user_text(text: str) -> bool:
    return bool(text and re.search(r"[A-Za-z]", text) and not text.startswith(("http://", "https://")))


def _visible_item(source: str, line: int, text: str) -> dict[str, Any]:
    lines = source.splitlines()
    snippet = lines[line - 1].strip() if 0 < line <= len(lines) else text
    if len(snippet) > MAX_SNIPPET_LENGTH:
        snippet = f"{snippet[: MAX_SNIPPET_LENGTH - 1]}…"
    return {"line": line, "text": text, "snippet": snippet}


def _inspector() -> DisclosureInspector:
    return DisclosureInspector()


@tool
def find_disclosure_candidates(scan_id: str, interaction_id: str) -> list[dict[str, Any]]:
    """Find explicit, user-visible AI disclosure text near a registered interaction.

    Args:
        scan_id: Backend-generated scan identifier for the isolated repository.
        interaction_id: Identifier of a confirmed AI interaction registered for this scan.
    """

    return _inspector().find_disclosure_candidates(scan_id, interaction_id)


@tool
def search_ui_text(scan_id: str, query: str) -> list[dict[str, Any]]:
    """Search rendered frontend text while excluding comments, imports, and backend files.

    Args:
        scan_id: Backend-generated scan identifier for the isolated repository.
        query: Case-insensitive literal text to find in likely user-visible strings.
    """

    return _inspector().search_ui_text(scan_id, query)
