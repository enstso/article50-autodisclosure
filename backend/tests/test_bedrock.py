from unittest.mock import Mock, patch

from app.core.bedrock import get_bedrock_model
from app.core.config import Settings


def test_bedrock_model_uses_config_and_standard_credential_chain() -> None:
    settings = Settings(
        aws_region="eu-west-1",
        bedrock_model_id="global.anthropic.claude-sonnet-4-6",
    )
    session = Mock()
    model = Mock()

    with (
        patch("app.core.bedrock.boto3.Session", return_value=session) as session_factory,
        patch("app.core.bedrock.BedrockModel", return_value=model) as model_factory,
    ):
        result = get_bedrock_model(settings)

    assert result is model
    session_factory.assert_called_once_with(region_name="eu-west-1")
    model_factory.assert_called_once_with(
        model_id="global.anthropic.claude-sonnet-4-6",
        boto_session=session,
        temperature=0.1,
    )
