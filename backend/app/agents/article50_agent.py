import json
import logging
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError
from strands import Agent
from strands.models import BedrockModel

from app.core.bedrock import get_bedrock_model
from app.core.config import Settings, get_settings
from app.core.exceptions import RepositoryAgentError
from app.models import AIInteractionFlow, Article50AnalysisResult
from app.services.article50_service import TransparencyAssessmentValidator
from app.tools import (
    find_disclosure_candidates,
    list_directory,
    read_source_file,
    search_repository,
    search_ui_text,
)
from app.tools.disclosure_tools import (
    DisclosureInspector,
    clear_scan_interactions,
    register_scan_interactions,
)
from app.tools.repository_tools import RepositoryInspector

ARTICLE50_SYSTEM_PROMPT = """
You are an AI transparency readiness analysis agent. Evaluate whether each confirmed user-facing AI
interaction clearly informs the user that AI is involved. You are not providing legal advice and you
must not certify legal compliance.

Use only repository evidence. A disclosure must be user-facing, clearly related to the interaction,
reasonably visible in the experience, and explicit enough to communicate that AI is involved. Do
not count README documentation, developer comments, variable names, backend logs, internal
documentation, dependency names, or unrelated generic AI mentions.

Use deterministic disclosure candidates first, then inspect only targeted interaction files when
context is needed. PASS requires a clear relevant disclosure. ACTION_REQUIRED means a clearly
user-facing interaction has no relevant disclosure. NEEDS_REVIEW means evidence, visibility, or
context is ambiguous. Do not assume a disclosure exists without source evidence. Do not modify or
execute code. Return structured transparency assessments and do not expose chain-of-thought.
""".strip()

logger = logging.getLogger(__name__)


class Article50AnalysisAgent:
    def __init__(
        self,
        settings: Settings | None = None,
        model_factory: Callable[[], BedrockModel] = get_bedrock_model,
        agent_factory: Callable[..., Any] = Agent,
        result_validator: TransparencyAssessmentValidator | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model_factory = model_factory
        self.agent_factory = agent_factory
        repository = RepositoryInspector(self.settings)
        disclosure = DisclosureInspector(self.settings, repository)
        self.disclosure = disclosure
        self.result_validator = result_validator or TransparencyAssessmentValidator(disclosure)

    def analyze(
        self, scan_id: str, interactions: list[AIInteractionFlow]
    ) -> Article50AnalysisResult:
        confirmed = [item for item in interactions if item.user_facing]
        if not confirmed:
            return Article50AnalysisResult()

        register_scan_interactions(scan_id, confirmed)
        try:
            deterministic_context = [
                {
                    "interaction": interaction.model_dump(mode="json"),
                    "relevant_ui_files": self.disclosure.relevant_ui_files(
                        scan_id, interaction
                    ),
                    "disclosure_candidates": self.disclosure.find_disclosure_candidates(
                        scan_id, interaction.id
                    ),
                }
                for interaction in confirmed
            ]
            agent = self.agent_factory(
                model=self.model_factory(),
                tools=[
                    find_disclosure_candidates,
                    search_ui_text,
                    read_source_file,
                    list_directory,
                    search_repository,
                ],
                system_prompt=ARTICLE50_SYSTEM_PROMPT,
                structured_output_model=Article50AnalysisResult,
                callback_handler=None,
            )
            prompt = (
                f"Evaluate Article 50 transparency readiness for scan {scan_id}. "
                "Pass that exact scan_id and the supplied interaction IDs to tools. "
                "The deterministic "
                "interaction context is:\n"
                f"{json.dumps(deterministic_context, ensure_ascii=True)}"
            )
            result = agent(prompt, structured_output_model=Article50AnalysisResult)
            structured_output = getattr(result, "structured_output", None)
            if structured_output is None:
                logger.warning(
                    "Article 50 agent returned no structured output for scan %s", scan_id
                )
                raise RepositoryAgentError(
                    "The Article 50 analysis agent returned no structured result."
                )
            proposed = _parse_article50_result(structured_output)
            return self.result_validator.validate(scan_id, confirmed, proposed)
        except RepositoryAgentError:
            raise
        except ValidationError as error:
            # Do not log model output or repository content. The scan identifier is enough to
            # correlate this controlled parsing failure with operational telemetry.
            logger.warning(
                "Article 50 structured output validation failed for scan %s", scan_id
            )
            raise RepositoryAgentError(
                "The Article 50 analysis agent returned an invalid structured result."
            ) from error
        finally:
            clear_scan_interactions(scan_id)


def _parse_article50_result(structured_output: Any) -> Article50AnalysisResult:
    """Accept the structured model object, a mapping, or a JSON serialization of either."""

    if isinstance(structured_output, str):
        payload = structured_output.strip()
        if payload.startswith("```") and payload.endswith("```"):
            lines = payload.splitlines()
            if len(lines) >= 3:
                payload = "\n".join(lines[1:-1]).strip()
        return Article50AnalysisResult.model_validate_json(payload)
    return Article50AnalysisResult.model_validate(structured_output)
