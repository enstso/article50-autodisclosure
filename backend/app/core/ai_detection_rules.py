from dataclasses import dataclass
from re import IGNORECASE, Pattern
from re import compile as compile_pattern


@dataclass(frozen=True)
class AIDependency:
    package: str
    provider: str


@dataclass(frozen=True)
class AIUsagePattern:
    name: str
    provider: str
    kind: str
    pattern: Pattern[str]


AI_DEPENDENCIES = (
    AIDependency("@anthropic-ai/sdk", "Anthropic"),
    AIDependency("@aws-sdk/client-bedrock-runtime", "Amazon Bedrock"),
    AIDependency("@google/generative-ai", "Google Gemini"),
    AIDependency("@google/genai", "Google Gemini"),
    AIDependency("anthropic", "Anthropic"),
    AIDependency("autogen", "Microsoft AutoGen"),
    AIDependency("boto3", "Amazon Bedrock"),
    AIDependency("cohere", "Cohere"),
    AIDependency("cohere-ai", "Cohere"),
    AIDependency("crewai", "CrewAI"),
    AIDependency("google-generativeai", "Google Gemini"),
    AIDependency("google-genai", "Google Gemini"),
    AIDependency("langchain", "LangChain"),
    AIDependency("langgraph", "LangGraph"),
    AIDependency("mistralai", "Mistral AI"),
    AIDependency("ollama", "Ollama"),
    AIDependency("openai", "OpenAI"),
    AIDependency("semantic-kernel", "Microsoft Semantic Kernel"),
    AIDependency("strands-agents", "Amazon Bedrock / Strands"),
    AIDependency("transformers", "Hugging Face"),
)

DEPENDENCY_MANIFEST_NAMES = frozenset(
    {
        "package.json",
        "package-lock.json",
        "requirements.txt",
        "pyproject.toml",
        "poetry.lock",
        "pipfile",
        "go.mod",
    }
)

AI_USAGE_PATTERNS = (
    AIUsagePattern(
        "bedrock-runtime client",
        "Amazon Bedrock",
        "client",
        compile_pattern(
            r"boto3\s*\.\s*client\s*\(\s*[\"']bedrock-runtime[\"']",
            IGNORECASE,
        ),
    ),
    AIUsagePattern(
        "BedrockRuntimeClient",
        "Amazon Bedrock",
        "client",
        compile_pattern(r"\bBedrockRuntimeClient\s*\(", IGNORECASE),
    ),
    AIUsagePattern(
        "Bedrock model invocation",
        "Amazon Bedrock",
        "invocation",
        compile_pattern(
            r"\b(?:invoke_model|converse|converse_stream)\s*\(",
            IGNORECASE,
        ),
    ),
    AIUsagePattern(
        "Bedrock SDK command",
        "Amazon Bedrock",
        "invocation",
        compile_pattern(
            r"\b(?:InvokeModel|Converse|ConverseStream)Command\s*\(",
            IGNORECASE,
        ),
    ),
    AIUsagePattern(
        "Anthropic import",
        "Anthropic",
        "import",
        compile_pattern(
            r"(?:from\s+anthropic\s+import|from\s+[\"']@anthropic-ai/sdk[\"'])",
            IGNORECASE,
        ),
    ),
    AIUsagePattern(
        "Anthropic client",
        "Anthropic",
        "client",
        compile_pattern(r"\b(?:new\s+)?Anthropic\s*\(", IGNORECASE),
    ),
    AIUsagePattern(
        "Anthropic messages invocation",
        "Anthropic",
        "invocation",
        compile_pattern(r"\.messages\s*\.\s*create\s*\(", IGNORECASE),
    ),
    AIUsagePattern(
        "OpenAI import",
        "OpenAI",
        "import",
        compile_pattern(
            r"(?:from\s+openai\s+import|from\s+[\"']openai[\"'])",
            IGNORECASE,
        ),
    ),
    AIUsagePattern(
        "OpenAI client",
        "OpenAI",
        "client",
        compile_pattern(r"\b(?:new\s+)?OpenAI\s*\(", IGNORECASE),
    ),
    AIUsagePattern(
        "OpenAI chat completion",
        "OpenAI",
        "invocation",
        compile_pattern(
            r"\.chat\s*\.\s*completions\s*\.\s*create\s*\(",
            IGNORECASE,
        ),
    ),
    AIUsagePattern(
        "OpenAI Responses API",
        "OpenAI",
        "invocation",
        compile_pattern(r"\.responses\s*\.\s*create\s*\(", IGNORECASE),
    ),
    AIUsagePattern(
        "Gemini generation",
        "Google Gemini",
        "invocation",
        compile_pattern(
            r"(?:\.generate_content|\.models\s*\.\s*generate_content)\s*\(",
            IGNORECASE,
        ),
    ),
    AIUsagePattern(
        "Ollama invocation",
        "Ollama",
        "invocation",
        compile_pattern(r"\bollama\s*\.\s*(?:chat|generate)\s*\(", IGNORECASE),
    ),
    AIUsagePattern(
        "Claude model configuration",
        "Anthropic",
        "configuration",
        compile_pattern(
            r"[\"'][^\"']*(?<!anthropic\.)claude[^\"']*[\"']",
            IGNORECASE,
        ),
    ),
    AIUsagePattern(
        "OpenAI model configuration",
        "OpenAI",
        "configuration",
        compile_pattern(r"[\"'](?:gpt-|o[134]-)[^\"']*[\"']", IGNORECASE),
    ),
    AIUsagePattern(
        "Bedrock model configuration",
        "Amazon Bedrock",
        "configuration",
        compile_pattern(r"[\"'](?:global\.|us\.|eu\.)?anthropic\.claude[^\"']*[\"']", IGNORECASE),
    ),
)
