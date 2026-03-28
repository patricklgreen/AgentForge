"""
Optional file-based prompt template loader.

Agents call load_prompt() to get their system prompt.  If a
language-specific template file exists under backend/app/prompts/,
it is used.  Otherwise the caller's inline default is returned unchanged.

Directory structure (all files are optional — missing == use inline default):
    app/prompts/
    ├── base/
    │   ├── requirements_analyst.md
    │   ├── architect.md
    │   └── code_reviewer.md
    ├── python-fastapi/
    │   ├── code_generator.md
    │   └── test_writer.md
    └── typescript-nestjs/
        ├── code_generator.md
        └── test_writer.md
"""
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@lru_cache(maxsize=256)
def load_prompt(
    template_name: str,
    language: str = "",
    framework: str = "",
    default: str = "",
) -> str:
    """
    Load a prompt template, falling back to *default* if no file is found.

    Args:
        template_name: Base name without extension, e.g. "code_generator".
        language:       Target language (e.g. "python").
        framework:      Target framework (e.g. "fastapi").
        default:        Inline fallback prompt.

    Returns:
        The template content string.
    """
    candidates: list[Path] = []

    # Language-specific override first
    if language and framework:
        key = f"{language.lower()}-{framework.lower().replace(' ', '')}"
        candidates.append(_PROMPTS_DIR / key / f"{template_name}.md")

    if language:
        candidates.append(_PROMPTS_DIR / language.lower() / f"{template_name}.md")

    # Base fallback
    candidates.append(_PROMPTS_DIR / "base" / f"{template_name}.md")

    for path in candidates:
        if path.exists():
            content = path.read_text(encoding="utf-8").strip()
            logger.debug(f"Loaded prompt template: {path}")
            return content

    if default:
        return default

    logger.warning(
        f"No prompt template found for '{template_name}' "
        f"(language={language}, framework={framework}) — using empty string"
    )
    return ""


def load_few_shot_examples(
    language: str,
    framework: str,
    example_type: str,
) -> str:
    """
    Load few-shot code examples for a language/framework combination.

    Returns an empty string if no examples directory is found.
    """
    key = f"{language.lower()}-{framework.lower().replace(' ', '')}"
    examples_dir = _PROMPTS_DIR / key / "examples"

    if not examples_dir.exists():
        return ""

    parts: list[str] = []
    for path in sorted(examples_dir.glob(f"*{example_type}*")):
        if path.is_file():
            parts.append(f"# Example: {path.stem}\n{path.read_text(encoding='utf-8')}")

    return "\n\n---\n\n".join(parts)
