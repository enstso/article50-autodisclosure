from botocore.exceptions import ClientError, NoCredentialsError

from app.services.scan_service import _safe_error_message


def test_bedrock_errors_are_mapped_to_safe_messages() -> None:
    access_denied = ClientError(
        {
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "sensitive provider details",
            }
        },
        "Converse",
    )
    model_missing = ClientError(
        {
            "Error": {
                "Code": "ResourceNotFoundException",
                "Message": "sensitive provider details",
            }
        },
        "Converse",
    )

    assert "access was denied" in _safe_error_message(access_denied)
    assert (
        _safe_error_message(model_missing) == "The configured Amazon Bedrock model is unavailable."
    )
    assert _safe_error_message(NoCredentialsError()) == (
        "Amazon Bedrock authentication is not configured."
    )


def test_unknown_agent_error_does_not_leak_internal_details() -> None:
    error = RuntimeError("failure at D:\\private\\workspace with secret data")

    assert _safe_error_message(error) == "Repository analysis failed."
