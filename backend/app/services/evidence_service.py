import re
from collections import defaultdict
from typing import Any
from uuid import UUID, uuid5

from app.core.exceptions import AutoDisclosureError
from app.models import (
    AIInteractionFlow,
    AIInvestigationResult,
    AIUsage,
    Evidence,
    EvidenceType,
)
from app.tools.ai_detection_tools import AIDetectionInspector
from app.tools.repository_tools import MAX_SNIPPET_LENGTH, RepositoryInspector


class EvidenceService:
    """Canonicalize model-proposed evidence against real repository source lines."""

    def __init__(self, repository: RepositoryInspector) -> None:
        self.repository = repository

    def canonicalize(self, scan_id: str, evidence: Evidence) -> Evidence | None:
        if not evidence.snippet.strip():
            return None
        try:
            source = self.repository.read_source_file(scan_id, evidence.file)
        except (AutoDisclosureError, ValueError):
            return None

        lines = source["content"].splitlines()
        line_number = evidence.line
        proposed = evidence.snippet.strip()
        if line_number is None:
            line_number = next(
                (
                    index
                    for index, line in enumerate(lines, start=1)
                    if proposed in line or line.strip() in proposed
                ),
                None,
            )
        if line_number is None or line_number < 1 or line_number > len(lines):
            return None

        actual_line = lines[line_number - 1].strip()
        if not actual_line:
            return None
        if (
            proposed.casefold() not in actual_line.casefold()
            and actual_line.casefold() not in proposed.casefold()
        ):
            return None
        return Evidence(
            file=source["path"],
            line=line_number,
            snippet=_bounded_snippet(actual_line),
            type=evidence.type,
        )


class InvestigationResultValidator:
    """Merge deterministic facts with agent output and reject unsupported conclusions."""

    def __init__(
        self,
        repository: RepositoryInspector,
        detector: AIDetectionInspector,
    ) -> None:
        self.repository = repository
        self.detector = detector
        self.evidence = EvidenceService(repository)

    def validate(
        self,
        scan_id: str,
        proposed: AIInvestigationResult,
    ) -> AIInvestigationResult:
        signals = self.detector.detect_ai_usage(scan_id)
        routes = self.detector.find_api_routes(scan_id)
        usages = self._validated_usages(scan_id, proposed.ai_usages, signals)
        flows = self._validated_flows(
            scan_id,
            proposed.ai_interactions,
            signals,
            routes,
            usages,
        )
        return AIInvestigationResult(ai_usages=usages, ai_interactions=flows)

    def _validated_usages(
        self,
        scan_id: str,
        proposed_usages: list[AIUsage],
        signals: dict[str, list[dict[str, Any]]],
    ) -> list[AIUsage]:
        candidates = signals["usage_candidates"]
        dependencies = signals["dependencies"]
        candidate_by_position = {(item["file"], item["line"]): item for item in candidates}
        dependency_positions = {(item["file"], item["line"]) for item in dependencies}
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for candidate in candidates:
            if candidate["kind"] in {"client", "invocation"}:
                groups[(candidate["file"], candidate["provider"])].append(candidate)

        output: list[AIUsage] = []
        for (file, provider), group in sorted(groups.items()):
            group.sort(key=lambda item: (item["kind"] != "invocation", item["line"]))
            anchor = group[0]
            proposed = next(
                (
                    usage
                    for usage in proposed_usages
                    if usage.file.replace("\\", "/") == file
                    and usage.provider is not None
                    and usage.provider.casefold() == provider.casefold()
                ),
                None,
            )

            evidence = [
                Evidence(
                    file=item["file"],
                    line=item["line"],
                    snippet=item["snippet"],
                    type=(
                        EvidenceType.MODEL_CALL
                        if item["kind"] == "invocation"
                        else EvidenceType.AI_USAGE
                    ),
                )
                for item in group
            ]
            if proposed is not None:
                for proposed_evidence in proposed.evidence:
                    item = self.evidence.canonicalize(scan_id, proposed_evidence)
                    if item is None or item.line is None:
                        continue
                    position = (item.file, item.line)
                    candidate = candidate_by_position.get(position)
                    if item.type == EvidenceType.MODEL_CALL and (
                        candidate is None or candidate["kind"] != "invocation"
                    ):
                        continue
                    if item.type == EvidenceType.AI_USAGE and candidate is None:
                        continue
                    if item.type == EvidenceType.MODEL_CONFIGURATION and (
                        candidate is None and position not in dependency_positions
                    ):
                        continue
                    if item.type not in {
                        EvidenceType.AI_USAGE,
                        EvidenceType.BACKEND_HANDLER,
                        EvidenceType.MODEL_CALL,
                        EvidenceType.MODEL_CONFIGURATION,
                    }:
                        continue
                    evidence.append(item)
            evidence = _unique_evidence(evidence)

            packages = sorted(
                {
                    item["package"]
                    for item in dependencies
                    if item["provider"].casefold() == provider.casefold()
                }
            )
            proposed_model = proposed.model if proposed is not None else None
            model = (
                proposed_model
                if proposed_model
                and any(proposed_model.casefold() in item.snippet.casefold() for item in evidence)
                else None
            )
            has_invocation = any(item["kind"] == "invocation" for item in group)
            maximum_confidence = 0.92 if has_invocation else 0.72
            proposed_confidence = (
                proposed.confidence if proposed is not None else maximum_confidence
            )

            output.append(
                AIUsage(
                    provider=provider,
                    sdk=packages[0] if packages else None,
                    model=model,
                    file=file,
                    line=anchor["line"],
                    purpose=proposed.purpose if proposed is not None else None,
                    evidence=evidence,
                    confidence=round(min(proposed_confidence, maximum_confidence), 2),
                )
            )
        return output

    def _validated_flows(
        self,
        scan_id: str,
        proposed_flows: list[AIInteractionFlow],
        signals: dict[str, list[dict[str, Any]]],
        routes: list[dict[str, Any]],
        usages: list[AIUsage],
    ) -> list[AIInteractionFlow]:
        candidate_by_position = {
            (item["file"], item["line"]): item for item in signals["usage_candidates"]
        }
        dependency_positions = {(item["file"], item["line"]) for item in signals["dependencies"]}
        route_by_position = {(item["file"], item["line"]): item for item in routes}
        output: list[AIInteractionFlow] = []

        for proposed in proposed_flows:
            matching_route = _match_route(proposed.api_endpoint, routes)
            endpoint = (
                f"{matching_route['method']} {matching_route['path']}" if matching_route else None
            )
            endpoint_callers = (
                self.detector.search_endpoint_usage(scan_id, matching_route["path"])
                if matching_route
                else []
            )
            caller_positions = {(item["file"], item["line"]) for item in endpoint_callers}

            verified: list[Evidence] = []
            for evidence in proposed.evidence:
                canonical = self.evidence.canonicalize(scan_id, evidence)
                if canonical is None or canonical.line is None:
                    continue
                position = (canonical.file, canonical.line)
                if canonical.type == EvidenceType.API_ROUTE and position not in route_by_position:
                    continue
                if (
                    canonical.type == EvidenceType.USER_INTERACTION
                    and position not in caller_positions
                ):
                    continue
                if canonical.type == EvidenceType.MODEL_CALL:
                    candidate = candidate_by_position.get(position)
                    if candidate is None or candidate["kind"] != "invocation":
                        continue
                if canonical.type in {EvidenceType.AI_USAGE, EvidenceType.MODEL_CONFIGURATION}:
                    if (
                        position not in candidate_by_position
                        and position not in dependency_positions
                    ):
                        continue
                if canonical.type == EvidenceType.DISCLOSURE:
                    continue
                verified.append(canonical)

            if matching_route:
                verified.append(_route_evidence(matching_route))
            frontend_entrypoint = _matching_file(proposed.frontend_entrypoint, endpoint_callers)
            if frontend_entrypoint is None and endpoint_callers:
                frontend_entrypoint = endpoint_callers[0]["file"]
            for caller in endpoint_callers:
                if caller["file"] == frontend_entrypoint:
                    verified.append(
                        Evidence(
                            file=caller["file"],
                            line=caller["line"],
                            snippet=caller["snippet"],
                            type=EvidenceType.USER_INTERACTION,
                        )
                    )

            provider = _matching_provider(proposed.ai_provider, usages)
            provider_usages = [usage for usage in usages if usage.provider == provider]
            for usage in provider_usages:
                verified.extend(usage.evidence)
            if matching_route:
                verified.extend(
                    self._deterministic_backend_link_evidence(
                        scan_id, matching_route["file"], verified
                    )
                )
            verified = _unique_evidence(verified)

            backend_handler = _verified_backend_file(proposed.backend_handler, verified)
            if backend_handler is None and matching_route:
                backend_handler = matching_route["file"]

            model = (
                proposed.ai_model
                if proposed.ai_model
                and any(
                    proposed.ai_model.casefold() in item.snippet.casefold() for item in verified
                )
                else None
            )
            evidence_types = {item.type for item in verified}
            evidence_files = {item.file for item in verified}
            backend_model_link = _has_backend_model_link(verified)
            completeness = 0.0
            completeness += 0.30 if EvidenceType.MODEL_CALL in evidence_types else 0.0
            completeness += 0.20 if EvidenceType.API_ROUTE in evidence_types else 0.0
            completeness += 0.25 if EvidenceType.USER_INTERACTION in evidence_types else 0.0
            completeness += 0.15 if backend_model_link else 0.0
            completeness += 0.10 if len(evidence_files) >= 3 else 0.0
            completeness = round(completeness, 2)
            # The model's user_facing flag is advisory. An exact frontend caller -> API route ->
            # backend handler -> model invocation path is stronger, deterministic evidence. This
            # prevents a valid direct interaction from being dropped solely because the model
            # returned a conservative boolean while keeping background/model-only usage excluded.
            confirmed = (
                frontend_entrypoint is not None
                and endpoint is not None
                and backend_handler is not None
                and provider is not None
                and backend_model_link
                and EvidenceType.USER_INTERACTION in evidence_types
                and EvidenceType.API_ROUTE in evidence_types
                and EvidenceType.MODEL_CALL in evidence_types
                and completeness >= 0.8
            )
            confidence = round(min(proposed.confidence, completeness), 2)
            if not verified or provider is None or confidence < 0.5:
                continue

            flow_id = str(
                uuid5(
                    UUID(scan_id),
                    "|".join(
                        [
                            proposed.name,
                            endpoint or "",
                            frontend_entrypoint or "",
                            provider,
                        ]
                    ),
                )
            )
            output.append(
                AIInteractionFlow(
                    id=flow_id,
                    name=proposed.name,
                    user_facing=confirmed,
                    frontend_entrypoint=frontend_entrypoint,
                    api_endpoint=endpoint,
                    backend_handler=backend_handler,
                    ai_provider=provider,
                    ai_model=model,
                    flow_summary=proposed.flow_summary,
                    evidence=verified,
                    confidence=confidence,
                )
            )
        return output

    def _deterministic_backend_link_evidence(
        self,
        scan_id: str,
        route_file: str,
        evidence: list[Evidence],
    ) -> list[Evidence]:
        """Prove a route-to-model link from exact source calls, without model inference."""

        try:
            route_source = self.repository.read_source_file(scan_id, route_file)["content"]
        except (AutoDisclosureError, ValueError):
            return []
        route_lines = route_source.splitlines()
        output: list[Evidence] = []

        for model_call in (
            item for item in evidence if item.type == EvidenceType.MODEL_CALL
        ):
            try:
                model_source = self.repository.read_source_file(
                    scan_id, model_call.file
                )["content"]
            except (AutoDisclosureError, ValueError):
                continue
            model_lines = model_source.splitlines()
            symbol_info = _enclosing_function(model_lines, model_call.line)
            if symbol_info is None:
                continue
            symbol, definition_line = symbol_info
            route_line = next(
                (
                    index
                    for index, line in enumerate(route_lines, start=1)
                    if _contains_function_call(line, symbol)
                ),
                None,
            )
            if route_line is None:
                continue
            output.extend(
                [
                    Evidence(
                        file=route_file,
                        line=route_line,
                        snippet=_bounded_snippet(route_lines[route_line - 1].strip()),
                        type=EvidenceType.BACKEND_HANDLER,
                    ),
                    Evidence(
                        file=model_call.file,
                        line=definition_line,
                        snippet=_bounded_snippet(model_lines[definition_line - 1].strip()),
                        type=EvidenceType.BACKEND_HANDLER,
                    ),
                ]
            )
        return output


def _match_route(
    proposed_endpoint: str | None,
    routes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not proposed_endpoint:
        return None
    parts = proposed_endpoint.strip().split(maxsplit=1)
    if len(parts) == 2 and parts[0].isalpha():
        method, path = parts[0].upper(), parts[1]
        return next(
            (route for route in routes if route["method"] == method and route["path"] == path),
            None,
        )
    path = proposed_endpoint.strip()
    return next((route for route in routes if route["path"] == path), None)


def _matching_file(proposed_file: str | None, facts: list[dict[str, Any]]) -> str | None:
    if not proposed_file:
        return None
    normalized = proposed_file.replace("\\", "/")
    return normalized if any(item["file"] == normalized for item in facts) else None


def _matching_provider(proposed_provider: str | None, usages: list[AIUsage]) -> str | None:
    providers = sorted({usage.provider for usage in usages if usage.provider is not None})
    if proposed_provider:
        match = next(
            (
                provider
                for provider in providers
                if provider.casefold() == proposed_provider.casefold()
            ),
            None,
        )
        if match:
            return match
    return providers[0] if len(providers) == 1 else None


def _verified_backend_file(proposed_file: str | None, evidence: list[Evidence]) -> str | None:
    if not proposed_file:
        return None
    normalized = proposed_file.replace("\\", "/")
    allowed_types = {EvidenceType.API_ROUTE, EvidenceType.BACKEND_HANDLER}
    return (
        normalized
        if any(item.file == normalized and item.type in allowed_types for item in evidence)
        else None
    )


def _route_evidence(route: dict[str, Any]) -> Evidence:
    return Evidence(
        file=route["file"],
        line=route["line"],
        snippet=route["snippet"],
        type=EvidenceType.API_ROUTE,
    )


def _bounded_snippet(value: str) -> str:
    if len(value) <= MAX_SNIPPET_LENGTH:
        return value
    return f"{value[: MAX_SNIPPET_LENGTH - 1]}…"


def _unique_evidence(evidence: list[Evidence]) -> list[Evidence]:
    output: list[Evidence] = []
    seen: set[tuple[str, int | None, EvidenceType]] = set()
    for item in evidence:
        key = (item.file, item.line, item.type)
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def _has_backend_model_link(evidence: list[Evidence]) -> bool:
    model_files = {item.file for item in evidence if item.type == EvidenceType.MODEL_CALL}
    route_files = {item.file for item in evidence if item.type == EvidenceType.API_ROUTE}
    handlers = [item for item in evidence if item.type == EvidenceType.BACKEND_HANDLER]
    if model_files & route_files:
        return True

    model_handlers = [item for item in handlers if item.file in model_files]
    route_handlers = [item for item in handlers if item.file in route_files]
    ignored_symbols = {"dict", "list", "set", "tuple"}
    for route_handler in route_handlers:
        route_symbols = {
            symbol
            for symbol in re.findall(
                r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(",
                route_handler.snippet,
            )
            if symbol.casefold() not in ignored_symbols
        }
        for model_handler in model_handlers:
            model_symbols = {
                symbol
                for symbol in re.findall(
                    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(",
                    model_handler.snippet,
                )
                if symbol.casefold() not in ignored_symbols
            }
            if route_symbols & model_symbols:
                return True
    return False


FUNCTION_DEFINITION_PATTERNS = (
    re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?function\s+"
        r"([A-Za-z_$][A-Za-z0-9_$]*)\s*\("
    ),
    re.compile(
        r"^\s*(?:export\s+)?(?:const|let|var)\s+"
        r"([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?\("
    ),
)


def _enclosing_function(
    lines: list[str], line_number: int | None
) -> tuple[str, int] | None:
    if line_number is None or line_number < 1 or line_number > len(lines):
        return None
    for index in range(line_number - 1, -1, -1):
        line = lines[index]
        for pattern in FUNCTION_DEFINITION_PATTERNS:
            match = pattern.search(line)
            if match is not None:
                return match.group(1), index + 1
    return None


def _contains_function_call(line: str, symbol: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith(("#", "//")):
        return False
    return re.search(rf"\b{re.escape(symbol)}\s*\(", line) is not None
