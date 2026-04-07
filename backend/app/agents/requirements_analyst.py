import json
import logging
from typing import Any, Optional

from app.agents.base import BaseAgent
from app.agents.language_profiles import LanguageProfile, get_profile

logger = logging.getLogger(__name__)

# ─── Base System Prompt ───────────────────────────────────────────────────────

_BASE_SYSTEM_PROMPT = """You are a Senior Software Architect and Business Analyst with \
15+ years of experience across enterprise, SaaS, and startup environments.

Your role is to analyze business requirements and produce a detailed, unambiguous \
technical specification that a team of AI agents will use to generate production-ready code.

You must identify:
1. Core functional requirements (what the system must do)
2. Non-functional requirements (performance, security, scalability, maintainability)
3. Data models and entities with their relationships
4. API endpoints with request/response contracts
5. User roles and permission matrix
6. Integration and third-party service requirements
7. Constraints, assumptions, and open questions
8. Measurable acceptance criteria for each feature

Guidelines:
- Be thorough and specific — vague requirements produce vague code
- Flag ambiguities in "assumptions" and "open_questions"
- Choose technology recommendations that match the target language/framework profile
- Respect language idioms (e.g. do NOT recommend SQLAlchemy for a TypeScript project)
- Always respond with valid JSON in the exact structure requested"""


def _build_system_prompt(profile: Optional[LanguageProfile]) -> str:
    """Extend the base prompt with language-profile-specific guidance."""
    if profile is None:
        return _BASE_SYSTEM_PROMPT

    addendum = f"""

── Language Profile: {profile.language} / {", ".join(profile.primary_frameworks)} ──

You are producing a specification for a {profile.language} project. Apply these conventions:

**Framework conventions:**
{profile.api_conventions}

**Dependency injection pattern:**
{profile.di_pattern}

**Async / concurrency pattern:**
{profile.async_pattern}

**Recommended ORM / data access options:**
{", ".join(profile.orm_options)}

**Test frameworks:**
{", ".join(profile.test_frameworks)}

**Package management:**
{profile.package_manager} (dependency file: {profile.dependency_file})

**Code style:**
{profile.code_style_guide}

**Additional agent instructions:**
{profile.agent_prompt_addendum.strip()}

When recommending the tech stack, prefer the libraries listed above over generic \
alternatives that may not fit the {profile.language} ecosystem."""

    return _BASE_SYSTEM_PROMPT + addendum


# ─── Output Schema ────────────────────────────────────────────────────────────

_OUTPUT_SCHEMA = {
    "project_name": "string — kebab-case identifier",
    "project_summary": "string — 2-3 sentence plain-English summary",
    "target_language": "string — exactly as provided",
    "target_framework": "string — primary framework",
    "functional_requirements": [
        {
            "id": "FR-001",
            "title": "string — short imperative phrase",
            "description": "string — detailed behaviour description",
            "priority": "must | should | could",
            "user_story": "As a , I want to  so that ",
            "acceptance_criteria": ["string — independently testable criterion"],
            "affected_entities": ["string — data model names"],
        }
    ],
    "non_functional_requirements": [
        {
            "id": "NFR-001",
            "category": "performance | security | scalability | reliability | maintainability | observability",
            "description": "string",
            "metric": "string — specific measurable target",
            "implementation_hint": "string — concrete suggestion",
        }
    ],
    "user_roles": [
        {
            "name": "string",
            "description": "string",
            "permissions": ["string"],
        }
    ],
    "data_models": [
        {
            "name": "string — PascalCase",
            "description": "string",
            "fields": [
                {
                    "name": "string",
                    "type": "string — language-idiomatic type",
                    "required": True,
                    "unique": False,
                    "indexed": False,
                    "description": "string",
                    "validation_rules": ["string"],
                }
            ],
            "relationships": [
                {
                    "type": "one_to_many | many_to_many | one_to_one",
                    "target": "string — target entity name",
                    "description": "string",
                }
            ],
            "business_rules": ["string — invariants that must always hold"],
        }
    ],
    "api_endpoints": [
        {
            "method": "GET | POST | PUT | PATCH | DELETE",
            "path": "string — RESTful path with {parameters}",
            "description": "string",
            "auth_required": True,
            "required_roles": ["string"],
            "path_params": [{"name": "string", "type": "string", "description": "string"}],
            "query_params": [
                {
                    "name": "string",
                    "type": "string",
                    "required": False,
                    "description": "string",
                }
            ],
            "request_body": {"description": "string", "schema": {}},
            "response": {"status_code": 200, "description": "string", "schema": {}},
            "error_responses": [{"status_code": 400, "description": "string"}],
        }
    ],
    "integrations": [
        {
            "name": "string",
            "purpose": "string",
            "auth_method": "string",
            "data_flow": "inbound | outbound | bidirectional",
        }
    ],
    "tech_stack": {
        "language": "string",
        "framework": "string",
        "database": "string",
        "cache": "string",
        "auth": "string",
        "testing": "string",
        "orm": "string",
        "task_queue": "string or null",
        "search": "string or null",
        "file_storage": "string or null",
        "observability": "string",
        "ci_cd": "string",
        "containerisation": "string",
        "additional": ["string"],
    },
    "constraints": ["string"],
    "assumptions": ["string"],
    "open_questions": ["string"],
    "out_of_scope": ["string"],
    "glossary": [{"term": "string", "definition": "string"}],
}


# ─── Agent ────────────────────────────────────────────────────────────────────


class RequirementsAnalystAgent(BaseAgent):
    """
    Analyzes raw business requirements and produces a structured technical
    specification consumed by all downstream agents.

    Language-profile awareness
    ──────────────────────────
    Resolves a LanguageProfile for the target language + framework, then:
    - Injects profile conventions into the system prompt
    - Auto-selects the framework if the user left it blank
    - Validates and enriches the generated tech_stack
    - Injects profile-mandated NFRs (linting, type safety, coverage, async I/O)

    Human feedback loop
    ───────────────────
    When the orchestrator routes back to this node with action="modify", the
    most recent feedback for the requirements_analysis step is appended to the
    prompt so the analyst can revise accordingly.
    """

    def __init__(self) -> None:
        super().__init__(
            name="RequirementsAnalyst",
            description=(
                "Analyzes business requirements and produces a comprehensive "
                "technical specification tailored to the target language/framework."
            ),
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        self._log_step("Starting requirements analysis...")

        language = state["target_language"]
        framework = state.get("target_framework") or ""
        requirements = state["requirements"]

        # Resolve language profile
        profile = get_profile(language, framework)
        if profile:
            self._log_step(
                f"Profile resolved: {profile.language} / "
                f"{', '.join(profile.primary_frameworks[:2])}"
            )
            if not framework:
                framework = profile.primary_frameworks[0]
                self._log_step(f"Framework auto-selected: {framework}")
        else:
            self._log_step(
                f"No profile for {language}/{framework} — using generic analysis"
            )

        feedback_context = self._build_feedback_context(state)
        system_prompt = _build_system_prompt(profile)
        user_message = self._build_user_message(
            requirements=requirements,
            language=language,
            framework=framework,
            profile=profile,
            feedback_context=feedback_context,
        )

        self._log_step("Invoking LLM...")
        specification = await self._invoke_llm_json(
            system_prompt=system_prompt,
            user_message=user_message,
            use_fast_model=True,  # Use Haiku for more reliable JSON output
        )

        specification = self._post_process(
            specification=specification,
            language=language,
            framework=framework,
            profile=profile,
        )

        fr_count = len(specification.get("functional_requirements", []))
        nfr_count = len(specification.get("non_functional_requirements", []))
        self._log_step(
            f"Analysis complete — {fr_count} FRs, {nfr_count} NFRs, "
            f"{len(specification.get('data_models', []))} models, "
            f"{len(specification.get('api_endpoints', []))} endpoints"
        )

        return {
            **state,
            "specification":    specification,
            "target_framework": framework,
            "current_step":     "requirements_analysis",
        }

    # ─── Prompt builders ──────────────────────────────────────────────────────

    def _build_feedback_context(self, state: dict[str, Any]) -> str:
        all_feedback: list[dict] = state.get("human_feedback", [])
        step_feedback = [
            fb for fb in all_feedback
            if fb.get("step") == "requirements_analysis"
            and fb.get("action") in ("modify", "reject")
        ]
        if not step_feedback:
            return ""

        latest = step_feedback[-1]
        feedback_text = (latest.get("feedback") or "").strip()
        modifications = latest.get("modifications") or {}

        if not feedback_text and not modifications:
            return ""

        lines = [
            "",
            "── Human Reviewer Feedback (MUST be fully incorporated) ──",
            f"Action: {latest.get('action', 'modify')}",
        ]
        if feedback_text:
            lines += ["", "Feedback:", feedback_text]
        if modifications:
            lines += ["", "Modifications:", json.dumps(modifications, indent=2)]
        lines += [
            "",
            "Revise your specification to fully address the feedback above.",
            "── End of feedback ──",
            "",
        ]
        return "\n".join(lines)

    def _build_user_message(
        self,
        requirements:     str,
        language:         str,
        framework:        str,
        profile:          Optional[LanguageProfile],
        feedback_context: str,
    ) -> str:
        sections: list[str] = []

        sections.append(
            f"**Target Language:** {language}\n"
            f"**Target Framework:** {framework or 'Select best fit for ' + language}"
        )

        if profile:
            sections.append(
                f"**Available language profile:**\n"
                f"- Primary frameworks: {', '.join(profile.primary_frameworks)}\n"
                f"- Test frameworks:    {', '.join(profile.test_frameworks)}\n"
                f"- ORM options:        {', '.join(profile.orm_options)}\n"
                f"- Package manager:    {profile.package_manager}\n"
                f"- Type system:        {profile.type_system}"
            )

        sections.append(
            f"**Business Requirements:**\n{'─' * 60}\n"
            f"{requirements.strip()}\n{'─' * 60}"
        )

        if feedback_context:
            sections.append(feedback_context)

        schema_json = json.dumps(_OUTPUT_SCHEMA, indent=2)
        sections.append(
            "**Output Instructions:**\n\n"
            "Return a single JSON object that EXACTLY matches the schema below. "
            "Every key shown is required. Use null for inapplicable optional fields. "
            "Use [] for empty lists. "
            "Output ONLY the JSON object — no markdown fences, no text outside JSON.\n\n"
            f"Required schema:\n{schema_json}"
        )

        return "\n\n".join(sections)

    # ─── Post-processing ──────────────────────────────────────────────────────

    def _post_process(
        self,
        specification: dict[str, Any],
        language:      str,
        framework:     str,
        profile:       Optional[LanguageProfile],
    ) -> dict[str, Any]:
        spec = dict(specification)

        # 1. Mandatory field defaults
        defaults = {
            "project_name": "application",
            "project_summary": "",
            "functional_requirements": [],
            "non_functional_requirements": [],
            "user_roles": [],
            "data_models": [],
            "api_endpoints": [],
            "integrations": [],
            "tech_stack": {},
            "constraints": [],
            "assumptions": [],
            "open_questions": [],
            "out_of_scope": [],
            "glossary": [],
        }
        for k, v in defaults.items():
            spec.setdefault(k, v)

        spec["target_language"] = language
        spec["target_framework"] = framework

        # 2. Tech stack enrichment from profile
        if profile:
            stack: dict = spec["tech_stack"]
            stack.setdefault("language",        language)
            stack.setdefault("framework",        framework or profile.primary_frameworks[0])
            stack.setdefault("testing",          profile.test_frameworks[0])
            stack.setdefault("ci_cd",            "GitHub Actions")
            stack.setdefault("containerisation", "Docker")
            stack.setdefault("observability",    "structured logging + OpenTelemetry")

            # Replace incompatible ORM selections
            if stack.get("orm") and profile.orm_options:
                current_orm = stack["orm"].lower()
                profile_orms_lower = [o.lower() for o in profile.orm_options]
                is_incompatible = not any(
                    p in current_orm or current_orm in p
                    for p in profile_orms_lower
                )
                if is_incompatible:
                    logger.info(
                        f"Replacing incompatible ORM '{stack['orm']}' with "
                        f"'{profile.orm_options[0]}'"
                    )
                    stack["orm"] = profile.orm_options[0]

            spec["tech_stack"] = stack

            # 3. Inject profile NFRs
            spec["non_functional_requirements"] = self._inject_profile_nfrs(
                existing=spec["non_functional_requirements"],
                profile=profile,
            )

        # 4. Normalise list fields
        for list_field in (
            "functional_requirements", "non_functional_requirements",
            "user_roles", "data_models", "api_endpoints", "integrations",
            "constraints", "assumptions", "open_questions", "out_of_scope", "glossary",
        ):
            if not isinstance(spec[list_field], list):
                spec[list_field] = []

        # 5. Ensure each FR has acceptance criteria
        for fr in spec.get("functional_requirements", []):
            if not isinstance(fr, dict):
                continue
            if not fr.get("acceptance_criteria"):
                fr["acceptance_criteria"] = [
                    f"The system fulfils: {fr.get('title', 'this requirement')}"
                ]
            fr.setdefault("user_story", "")
            fr.setdefault("affected_entities", [])

        # 6. Normalise data model relationships (list[str] → list[dict])
        for model in spec.get("data_models", []):
            if not isinstance(model, dict):
                continue
            rels = model.get("relationships", [])
            if rels and isinstance(rels[0], str):
                model["relationships"] = [
                    {"type": "unknown", "target": r, "description": r}
                    for r in rels
                ]
            model.setdefault("business_rules", [])
            for fld in model.get("fields", []):
                if not isinstance(fld, dict):
                    continue
                fld.setdefault("unique",           False)
                fld.setdefault("indexed",          False)
                fld.setdefault("validation_rules", [])

        return spec

    def _inject_profile_nfrs(
        self,
        existing: list[dict],
        profile: LanguageProfile,
    ) -> list[dict]:
        """Add profile-mandated NFRs that the LLM frequently omits."""
        existing_categories = {
            nfr.get("category", "").lower()
            for nfr in existing
            if isinstance(nfr, dict)
        }
        has_coverage_nfr = any(
            "coverage" in (nfr.get("description") or "").lower()
            or "test" in (nfr.get("description") or "").lower()
            for nfr in existing
            if isinstance(nfr, dict)
        )

        additions: list[dict] = []
        next_id = len(existing) + 1

        if "maintainability" not in existing_categories:
            additions.append({
                "id":                 f"NFR-{next_id:03d}",
                "category":           "maintainability",
                "description":        (
                    f"All code must pass linting with "
                    f"{', '.join(profile.linters)} with zero warnings."
                ),
                "metric":             "0 linter errors, 0 warnings in CI",
                "implementation_hint": (
                    f"Enforce {', '.join(profile.linters)} in CI pipeline. "
                    f"Follow {profile.code_style_guide}."
                ),
            })
            next_id += 1

        if profile.type_system == "static" and "reliability" not in existing_categories:
            additions.append({
                "id":                 f"NFR-{next_id:03d}",
                "category":           "reliability",
                "description":        (
                    f"All {profile.language} code must compile without type errors. "
                    "No use of 'any' / dynamic types except where unavoidable."
                ),
                "metric":             "0 type errors in strict mode",
                "implementation_hint": "Enable strict type checking in compiler config.",
            })
            next_id += 1

        if not has_coverage_nfr:
            additions.append({
                "id":                 f"NFR-{next_id:03d}",
                "category":           "maintainability",
                "description":        (
                    f"Test suite must achieve ≥90% line and branch coverage "
                    f"using {', '.join(profile.test_frameworks[:2])}."
                ),
                "metric":             "≥90% line coverage, ≥85% branch coverage",
                "implementation_hint": (
                    f"Configure {profile.test_frameworks[0]} with coverage reporting. "
                    "Fail build if thresholds are not met."
                ),
            })
            next_id += 1

        if profile.async_pattern and "scalability" not in existing_categories:
            additions.append({
                "id":                 f"NFR-{next_id:03d}",
                "category":           "scalability",
                "description":        (
                    f"All I/O-bound operations must use the {profile.language} "
                    f"async pattern ({profile.async_pattern}) to avoid blocking."
                ),
                "metric":             "No synchronous I/O on the main thread/event loop",
                "implementation_hint": (
                    "Use async-aware database and HTTP client libraries throughout."
                ),
            })

        return existing + additions
