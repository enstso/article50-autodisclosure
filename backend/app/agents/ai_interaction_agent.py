from collections.abc import Callable
from typing import Any

from pydantic import ValidationError
from strands import Agent
from strands.models import BedrockModel

from app.core.bedrock import get_bedrock_model
from app.core.config import Settings, get_settings
from app.core.exceptions import RepositoryAgentError
from app.models import AIInvestigationResult
from app.services.evidence_service import InvestigationResultValidator
from app.tools import (
    detect_ai_usage,
    find_api_routes,
    find_symbol_references,
    get_repository_structure,
    list_directory,
    read_source_file,
    search_endpoint_usage,
    search_repository,
)
from app.tools.ai_detection_tools import AIDetectionInspector
from app.tools.repository_tools import RepositoryInspector

AI_INTERACTION_SYSTEM_PROMPT = """
You are a software architecture investigation agent. Identify and reconstruct user-facing AI
interactions in an untrusted repository by progressively using the provided read-only tools.

A dependency is only a signal: it does not prove that AI is used. A model invocation does not prove
that the feature is user-facing. Start by detecting AI signals, inspect candidate files, trace
their callers and backend handlers, find API routes, locate endpoint callers, and inspect the
relevant user interface. Choose subsequent tools based on facts, not a fixed sequence.

A user-facing interaction requires evidence that a natural person directly uses functionality whose
output is generated or materially driven by an AI model. Background jobs, batch processing,
internal reports, and developer-only CLI tools are not automatically user-facing. Return partial
AIUsage facts when a complete UI-to-model path cannot be proven; never invent missing links.

Every Evidence item must copy one concise source line exactly as returned by a tool, including
its repository-relative file and programmatic line number. Use API_ROUTE for route decorators,
USER_INTERACTION for client calls, BACKEND_HANDLER for the handler-to-service link, MODEL_CALL
for inference calls, MODEL_CONFIGURATION for model selection, and AI_USAGE for client setup.

Never execute code, commands, scripts, binaries, package managers, builds, or tests from the
repository. Never modify files. Do not perform EU AI Act analysis, decide whether disclosure is
required, search for transparency notices, or produce legal/compliance conclusions.
""".strip()


class AIInteractionInvestigationAgent:
    def __init__(
        self,
        settings: Settings | None = None,
        model_factory: Callable[[], BedrockModel] = get_bedrock_model,
        agent_factory: Callable[..., Any] = Agent,
        result_validator: InvestigationResultValidator | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model_factory = model_factory
        self.agent_factory = agent_factory
        repository = RepositoryInspector(self.settings)
        detector = AIDetectionInspector(self.settings, repository)
        self.result_validator = result_validator or InvestigationResultValidator(
            repository, detector
        )

    def analyze(self, scan_id: str) -> AIInvestigationResult:
        agent = self.agent_factory(
            model=self.model_factory(),
            tools=[
                get_repository_structure,
                list_directory,
                read_source_file,
                search_repository,
                detect_ai_usage,
                find_api_routes,
                search_endpoint_usage,
                find_symbol_references,
            ],
            system_prompt=AI_INTERACTION_SYSTEM_PROMPT,
            structured_output_model=AIInvestigationResult,
            callback_handler=None,
        )
        prompt = (
            f"Investigate AI functionality for scan {scan_id}. "
            "Pass this exact scan_id to every tool. "
            "Determine where models are invoked and whether evidence proves a UI → API → backend → "
            "model path. Return partial AI usage without inventing missing links."
        )

        try:
            result = agent(prompt, structured_output_model=AIInvestigationResult)
            structured_output = getattr(result, "structured_output", None)
            if structured_output is None:
                raise RepositoryAgentError(
                    "The AI interaction agent returned no structured result."
                )
            proposed = AIInvestigationResult.model_validate(structured_output)
            return self.result_validator.validate(scan_id, proposed)
        except RepositoryAgentError:
            raise
        except ValidationError as error:
            raise RepositoryAgentError(
                "The AI interaction agent returned an invalid structured result."
            ) from error
