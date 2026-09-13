from pathlib import Path

IGNORED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "dist",
        "build",
        "coverage",
        ".venv",
        "venv",
        "__pycache__",
        ".next",
        ".cache",
        ".idea",
        ".vscode",
    }
)

LANGUAGE_BY_SUFFIX = {
    ".css": "CSS",
    ".go": "Go",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".php": "PHP",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".swift": "Swift",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".vue": "Vue",
}

IMPORTANT_FILE_NAMES = frozenset(
    {
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "Pipfile",
        "poetry.lock",
        "vite.config.js",
        "vite.config.ts",
        "next.config.js",
        "next.config.mjs",
        "README.md",
        "Dockerfile",
    }
)


def is_ignored(relative_path: Path) -> bool:
    return any(part.casefold() in IGNORED_DIRECTORY_NAMES for part in relative_path.parts)
