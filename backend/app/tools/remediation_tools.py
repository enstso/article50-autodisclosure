from threading import Lock
from typing import Any

from strands import tool

from app.models import EvidenceType, RemediationContext

CONTEXT_WINDOW_LINES = 60

_context_registry: dict[tuple[str, str], RemediationContext] = {}
_registry_lock = Lock()


def register_remediation_context(context: RemediationContext) -> None:
    with _registry_lock:
        _context_registry[(context.scan_id, context.finding.id)] = context.model_copy(deep=True)


def clear_remediation_context(scan_id: str, finding_id: str) -> None:
    with _registry_lock:
        _context_registry.pop((scan_id, finding_id), None)


def remediation_context_payload(scan_id: str, finding_id: str) -> dict[str, Any]:
    with _registry_lock:
        context = _context_registry.get((scan_id, finding_id))
        if context is None:
            raise ValueError("The requested remediation context is not registered.")
        context = context.model_copy(deep=True)

    frontend_lines = [
        evidence.line
        for evidence in context.interaction.evidence
        if evidence.file == context.interaction.frontend_entrypoint
        and evidence.type in {EvidenceType.USER_INTERACTION, EvidenceType.UI_CONTEXT}
        and evidence.line is not None
    ]
    return {
        "scan_id": context.scan_id,
        "finding": context.finding.model_dump(mode="json"),
        "assessment": context.assessment.model_dump(mode="json"),
        "interaction": context.interaction.model_dump(mode="json"),
        "source_files": [
            {
                "file": source.file,
                "sha256": source.sha256,
                "excerpts": _source_excerpts(source.content, frontend_lines),
            }
            for source in context.source_files
        ],
    }


def _source_excerpts(content: str, anchor_lines: list[int]) -> list[dict[str, Any]]:
    lines = content.splitlines()
    if len(lines) <= CONTEXT_WINDOW_LINES * 2:
        return [{"start_line": 1, "content": content}]

    anchors = [*anchor_lines, len(lines)]
    windows: list[tuple[int, int]] = []
    for anchor in anchors:
        start = max(1, anchor - CONTEXT_WINDOW_LINES // 2)
        end = min(len(lines), start + CONTEXT_WINDOW_LINES - 1)
        start = max(1, end - CONTEXT_WINDOW_LINES + 1)
        contained = any(
            start >= existing_start and end <= existing_end
            for existing_start, existing_end in windows
        )
        if contained:
            continue
        windows.append((start, end))
    return [
        {
            "start_line": start,
            "content": "\n".join(lines[start - 1 : end]),
        }
        for start, end in windows[:2]
    ]


@tool
def get_remediation_context(scan_id: str, finding_id: str) -> dict[str, Any]:
    """Return the bounded, read-only context for one remediable finding.

    Args:
        scan_id: Backend-generated scan identifier.
        finding_id: Identifier of the ACTION_REQUIRED finding being remediated.
    """

    return remediation_context_payload(scan_id, finding_id)
