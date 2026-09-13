import shutil
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.agents.ai_interaction_agent import (
    AI_INTERACTION_SYSTEM_PROMPT,
    AIInteractionInvestigationAgent,
)
from app.core.config import Settings
from app.models import (
    AIInteractionFlow,
    AIInvestigationResult,
    AIUsage,
    Evidence,
    EvidenceType,
)
from app.services.workspace_service import WorkspaceService
from app.tools.ai_detection_tools import AIDetectionInspector
from app.tools.repository_tools import RepositoryInspector

FIXTURE_REPOSITORY = Path(__file__).parent / "fixtures" / "ai_chat_app"


def test_agent_reconstructs_validated_ui_to_bedrock_flow(tmp_path) -> None:
    settings = Settings(workspace_path=tmp_path)
    workspace = WorkspaceService(settings)
    scan_id = str(uuid4())
    workspace.create_workspace(scan_id)
    shutil.copytree(FIXTURE_REPOSITORY, workspace.get_repository_path(scan_id))
    repository = RepositoryInspector(settings, workspace)
    detector = AIDetectionInspector(settings, repository)

    signals = detector.detect_ai_usage(scan_id)
    route = detector.find_api_routes(scan_id)[0]
    caller = detector.search_endpoint_usage(scan_id, "/api/chat")[0]
    backend_reference = next(
        item
        for item in detector.find_symbol_references(scan_id, "generate_reply")
        if item["file"] == "backend/app/api/chat.py" and "return" in item["snippet"]
    )
    service_definition = next(
        item
        for item in detector.find_symbol_references(scan_id, "generate_reply")
        if item["file"] == "backend/app/services/ai.py" and item["snippet"].startswith("def ")
    )
    model_call = next(
        item
        for item in signals["usage_candidates"]
        if item["provider"] == "Amazon Bedrock" and item["kind"] == "invocation"
    )
    model_configuration = next(
        item
        for item in signals["usage_candidates"]
        if item["provider"] == "Amazon Bedrock" and item["kind"] == "configuration"
    )
    client = next(
        item
        for item in signals["usage_candidates"]
        if item["provider"] == "Amazon Bedrock" and item["kind"] == "client"
    )

    proposed = AIInvestigationResult(
        ai_usages=[
            AIUsage(
                provider="Amazon Bedrock",
                sdk="boto3",
                model="global.anthropic.claude-sonnet-4-6",
                file=model_call["file"],
                line=model_call["line"],
                purpose="Generate chat replies",
                evidence=[
                    _evidence(client, EvidenceType.AI_USAGE),
                    _evidence(model_call, EvidenceType.MODEL_CALL),
                    _evidence(model_configuration, EvidenceType.MODEL_CONFIGURATION),
                ],
                confidence=0.97,
            )
        ],
        ai_interactions=[
            AIInteractionFlow(
                id="model-proposed-id",
                name="Customer support chatbot",
                user_facing=True,
                frontend_entrypoint=caller["file"],
                api_endpoint="POST /api/chat",
                backend_handler=route["file"],
                ai_provider="Amazon Bedrock",
                ai_model="global.anthropic.claude-sonnet-4-6",
                flow_summary=(
                    "The React chat form calls the FastAPI route, which invokes Amazon Bedrock."
                ),
                evidence=[
                    _evidence(caller, EvidenceType.USER_INTERACTION),
                    _evidence(route, EvidenceType.API_ROUTE),
                    _evidence(backend_reference, EvidenceType.BACKEND_HANDLER),
                    _evidence(service_definition, EvidenceType.BACKEND_HANDLER),
                    _evidence(model_call, EvidenceType.MODEL_CALL),
                    _evidence(model_configuration, EvidenceType.MODEL_CONFIGURATION),
                    Evidence(
                        file="invented/missing.py",
                        line=999,
                        snippet="fabricated_model_call()",
                        type=EvidenceType.MODEL_CALL,
                    ),
                ],
                confidence=0.94,
            )
        ],
    )
    captured: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, **kwargs) -> None:
            captured["configuration"] = kwargs

        def __call__(self, prompt: str, **kwargs):
            captured["prompt"] = prompt
            return SimpleNamespace(structured_output=proposed)

    analyzer = AIInteractionInvestigationAgent(
        settings=settings,
        model_factory=lambda: object(),
        agent_factory=FakeAgent,
    )

    result = analyzer.analyze(scan_id)

    assert len(captured["configuration"]["tools"]) == 8
    assert captured["configuration"]["system_prompt"] == AI_INTERACTION_SYSTEM_PROMPT
    assert len(result.ai_usages) == 1
    assert len(result.ai_interactions) == 1
    flow = result.ai_interactions[0]
    assert flow.user_facing is True
    assert flow.frontend_entrypoint == "frontend/src/Chat.tsx"
    assert flow.api_endpoint == "POST /api/chat"
    assert flow.backend_handler == "backend/app/api/chat.py"
    assert flow.ai_provider == "Amazon Bedrock"
    assert flow.ai_model == "global.anthropic.claude-sonnet-4-6"
    assert flow.confidence == 0.94
    assert {item.file for item in flow.evidence} >= {
        "frontend/src/Chat.tsx",
        "backend/app/api/chat.py",
        "backend/app/services/ai.py",
    }
    assert all(item.file != "invented/missing.py" for item in flow.evidence)


def _evidence(fact: dict, evidence_type: EvidenceType) -> Evidence:
    return Evidence(
        file=fact["file"],
        line=fact["line"],
        snippet=fact["snippet"],
        type=evidence_type,
    )
