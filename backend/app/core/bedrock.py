import boto3
from strands.models import BedrockModel

from app.core.config import Settings, get_settings


def get_bedrock_model(settings: Settings | None = None) -> BedrockModel:
    """Create the single configured Bedrock model used by repository agents.

    ``boto3.Session`` deliberately receives no credentials. Boto3 therefore uses
    its standard credential provider chain (environment, profiles, IAM roles, and
    other runtime providers).
    """

    active_settings = settings or get_settings()
    session = boto3.Session(region_name=active_settings.aws_region)
    return BedrockModel(
        model_id=active_settings.bedrock_model_id,
        boto_session=session,
        temperature=0.1,
    )
