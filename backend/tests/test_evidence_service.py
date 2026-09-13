from app.models import Evidence, EvidenceType
from app.services.evidence_service import _has_backend_model_link


def test_backend_model_link_requires_direct_file_or_shared_symbol() -> None:
    route = Evidence(
        file="backend/api/chat.py",
        line=5,
        snippet='@router.post("/api/chat")',
        type=EvidenceType.API_ROUTE,
    )
    route_handler = Evidence(
        file="backend/api/chat.py",
        line=7,
        snippet="return generate_reply(message)",
        type=EvidenceType.BACKEND_HANDLER,
    )
    model_call = Evidence(
        file="backend/jobs/report.py",
        line=9,
        snippet="client.responses.create(input=report)",
        type=EvidenceType.MODEL_CALL,
    )
    unrelated_handler = Evidence(
        file="backend/jobs/report.py",
        line=6,
        snippet="def generate_nightly_report():",
        type=EvidenceType.BACKEND_HANDLER,
    )
    linked_handler = unrelated_handler.model_copy(
        update={"snippet": "def generate_reply(message):"}
    )

    assert _has_backend_model_link([route, route_handler, model_call, unrelated_handler]) is False
    assert _has_backend_model_link([route, route_handler, model_call, linked_handler]) is True
