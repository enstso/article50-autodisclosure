import re

# These patterns deliberately require an explicit AI/artificial-intelligence signal. Generic labels
# such as "Assistant" and "Smart assistant" are contextual clues, not automatic disclosures.
DISCLOSURE_INDICATORS = (
    re.compile(r"\bAI[\s-]+assistant\b", re.IGNORECASE),
    re.compile(r"\bAI[\s-]+powered\b", re.IGNORECASE),
    re.compile(r"\bpowered\s+by\s+(?:an?\s+)?AI\b", re.IGNORECASE),
    re.compile(
        r"\b(?:content|response|responses|answer|answers)?\s*"
        r"(?:is|are)?\s*generated\s+by\s+AI\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bAI[\s-]+generated(?:\s+(?:content|response|responses|answer|answers))?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:you(?:'re|\s+are)\s+)?chat(?:ting)?\s+with\s+(?:an?\s+)?AI\b", re.IGNORECASE),
    re.compile(
        r"\b(?:you(?:'re|\s+are)\s+)?interact(?:ing)?\s+with\s+(?:an?\s+)?AI\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:this\s+)?assistant\s+uses\s+artificial\s+intelligence\b", re.IGNORECASE),
    re.compile(r"\bautomated\s+AI\s+assistant\b", re.IGNORECASE),
    re.compile(
        r"\bartificial[\s-]+intelligence[\s-]+(?:assistant|chatbot|system)\b",
        re.IGNORECASE,
    ),
)

AMBIGUOUS_UI_INDICATORS = (
    re.compile(r"\b(?:smart\s+)?assistant\b", re.IGNORECASE),
    re.compile(r"\bchatbot\b", re.IGNORECASE),
    re.compile(r"\bautomated\s+(?:assistant|chat)\b", re.IGNORECASE),
)

DYNAMIC_DISCLOSURE_INDICATORS = (
    re.compile(r"\bdangerouslySetInnerHTML\b"),
    re.compile(r"\b(?:innerHTML|v-html)\b"),
    re.compile(r"\b(?:t|translate|formatMessage)\s*\("),
    re.compile(
        r"\{\s*[A-Za-z_$][\w$]*(?:\.[\w$]+)*"
        r"(?:disclosure|notice|banner|assistantLabel)[\w$]*\s*\}",
        re.IGNORECASE,
    ),
)


def is_explicit_ai_disclosure(text: str) -> bool:
    normalized = " ".join(text.split())
    return any(pattern.search(normalized) for pattern in DISCLOSURE_INDICATORS)


def is_ambiguous_ai_context(text: str) -> bool:
    normalized = " ".join(text.split())
    return not is_explicit_ai_disclosure(normalized) and any(
        pattern.search(normalized) for pattern in AMBIGUOUS_UI_INDICATORS
    )


def has_dynamic_disclosure_signal(source: str) -> bool:
    return any(pattern.search(source) for pattern in DYNAMIC_DISCLOSURE_INDICATORS)
