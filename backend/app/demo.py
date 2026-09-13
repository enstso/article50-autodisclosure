import shutil
from difflib import unified_diff
from pathlib import Path

from app.core.article50_rules import ARTICLE_50_1_AI_INTERACTION_DISCLOSURE
from app.models import (
    AIInteractionFlow,
    AIInvestigationResult,
    AIUsage,
    Article50AnalysisResult,
    Evidence,
    EvidenceType,
    ReadinessStatus,
    RemediationContext,
    RemediationPlan,
    RepositorySummary,
    TransparencyAssessment,
)
from app.services.workspace_service import WorkspaceService

DEMO_REPOSITORY_URL = "demo://article50-ai-chatbot"
DEMO_REPOSITORY_ROOT = Path(__file__).resolve().parent / "demo_repository"
DEMO_DISCLOSURE = "You are chatting with an AI assistant."
DEMO_FRONTEND_FILE = "frontend/src/components/Chat.tsx"


def materialize_demo_repository(destination: Path) -> None:
    """Copy the controlled fixture into an isolated scan workspace."""

    shutil.copytree(DEMO_REPOSITORY_ROOT, destination)


class DemoRepositoryAnalyzer:
    def analyze(self, scan_id: str) -> RepositorySummary:
        return RepositorySummary(
            languages=["TypeScript", "Python"],
            frameworks=["React", "FastAPI"],
            architecture_summary=(
                "A React chat interface calls a FastAPI route backed by Amazon Bedrock."
            ),
            important_files=[
                DEMO_FRONTEND_FILE,
                "backend/app/api/chat.py",
                "backend/app/services/ai.py",
            ],
            potential_ai_integrations=["Amazon Bedrock"],
        )


class DemoAIInteractionAnalyzer:
    def analyze(self, scan_id: str) -> AIInvestigationResult:
        model_call = Evidence(
            file="backend/app/services/ai.py",
            line=6,
            snippet="    response = bedrock.converse(",
            type=EvidenceType.MODEL_CALL,
        )
        evidence = [
            Evidence(
                file=DEMO_FRONTEND_FILE,
                line=7,
                snippet='    const response = await fetch("/api/chat", {',
                type=EvidenceType.USER_INTERACTION,
            ),
            Evidence(
                file="backend/app/api/chat.py",
                line=6,
                snippet='@router.post("/api/chat")',
                type=EvidenceType.API_ROUTE,
            ),
            Evidence(
                file="backend/app/api/chat.py",
                line=8,
                snippet='    return {"reply": generate_reply(payload["message"])}',
                type=EvidenceType.BACKEND_HANDLER,
            ),
            model_call,
            Evidence(
                file="backend/app/services/ai.py",
                line=7,
                snippet='        modelId="global.anthropic.claude-sonnet-4-6",',
                type=EvidenceType.MODEL_CONFIGURATION,
            ),
        ]
        usage = AIUsage(
            provider="Amazon Bedrock",
            sdk="boto3",
            model="Claude Sonnet 4.6",
            file="backend/app/services/ai.py",
            line=6,
            purpose="Generate replies for the support chat",
            evidence=[model_call],
            confidence=0.98,
        )
        interaction = AIInteractionFlow(
            id="demo-chat-flow",
            name="Customer support chat",
            user_facing=True,
            frontend_entrypoint=DEMO_FRONTEND_FILE,
            api_endpoint="POST /api/chat",
            backend_handler="backend/app/api/chat.py",
            ai_provider="Amazon Bedrock",
            ai_model="Claude Sonnet 4.6",
            flow_summary="React Chat UI → POST /api/chat → FastAPI → Amazon Bedrock",
            evidence=evidence,
            confidence=0.96,
        )
        return AIInvestigationResult(ai_usages=[usage], ai_interactions=[interaction])


class DemoArticle50Analyzer:
    def __init__(self, workspace_service: WorkspaceService) -> None:
        self.workspace_service = workspace_service

    def analyze(
        self, scan_id: str, interactions: list[AIInteractionFlow]
    ) -> Article50AnalysisResult:
        if not interactions:
            return Article50AnalysisResult()
        source = (
            self.workspace_service.get_repository_path(scan_id) / DEMO_FRONTEND_FILE
        ).read_text(encoding="utf-8")
        disclosed = DEMO_DISCLOSURE in source
        interaction = interactions[0]
        evidence = list(interaction.evidence)
        disclosure_line = None
        if disclosed:
            disclosure_line = next(
                index
                for index, line in enumerate(source.splitlines(), start=1)
                if DEMO_DISCLOSURE in line
            )
            evidence.append(
                Evidence(
                    file=DEMO_FRONTEND_FILE,
                    line=disclosure_line,
                    snippet=(
                        '      <p className="ai-notice">'
                        f"{DEMO_DISCLOSURE}</p>"
                    ),
                    type=EvidenceType.DISCLOSURE,
                )
            )
        return Article50AnalysisResult(
            assessments=[
                TransparencyAssessment(
                    interaction_id=interaction.id,
                    rule_id=ARTICLE_50_1_AI_INTERACTION_DISCLOSURE,
                    status=(ReadinessStatus.PASS if disclosed else ReadinessStatus.ACTION_REQUIRED),
                    disclosure_detected=disclosed,
                    disclosure_text=DEMO_DISCLOSURE if disclosed else None,
                    disclosure_file=DEMO_FRONTEND_FILE if disclosed else None,
                    disclosure_line=disclosure_line,
                    explanation=(
                        "A clear AI transparency disclosure is visible in the chat interface."
                        if disclosed
                        else "A direct user-facing AI interaction was detected, but no clear "
                        "AI transparency disclosure was found in the relevant interface."
                    ),
                    evidence=evidence,
                    inspected_files=[DEMO_FRONTEND_FILE],
                    confidence=0.96,
                )
            ]
        )


class DemoRemediationGenerator:
    def propose(self, context: RemediationContext) -> RemediationPlan:
        source = context.source_files[0]
        form_line = '      <form className="chat-form" onSubmit={sendMessage}>'
        replacement = (
            f'      <p className="ai-notice">{DEMO_DISCLOSURE}</p>\n'
            f"{form_line}"
        )
        if form_line not in source.content:
            raise ValueError("The controlled demo fixture no longer matches its remediation.")
        updated = source.content.replace(form_line, replacement, 1)
        diff = "".join(
            unified_diff(
                source.content.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=f"a/{source.file}",
                tofile=f"b/{source.file}",
            )
        )
        return RemediationPlan(
            title="Add AI disclosure to the chat interface",
            rationale=(
                "Adds an explicit AI transparency notice directly above the user-facing "
                "conversation form."
            ),
            disclosure_text=DEMO_DISCLOSURE,
            affected_files=[source.file],
            unified_diff=diff,
            confidence=0.98,
        )
