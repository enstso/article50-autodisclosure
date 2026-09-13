import boto3

bedrock = boto3.client("bedrock-runtime")


def generate_reply(message: str) -> str:
    response = bedrock.converse(
        modelId="global.anthropic.claude-sonnet-4-6",
        messages=[{"role": "user", "content": [{"text": message}]}],
    )
    return response["output"]["message"]["content"][0]["text"]
