import json
import logging
from typing import Any, Optional, Type, TypeVar

import boto3
from botocore.config import Config
from langchain_aws import ChatBedrock
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

T = TypeVar("T", bound=BaseModel)


class BedrockService:
    """Service for interacting with AWS Bedrock (Claude models)."""

    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._llm_cache: dict[str, ChatBedrock] = {}

    @property
    def client(self) -> Any:
        if self._client is None:
            config = Config(
                region_name=settings.aws_region,
                retries={"max_attempts": 3, "mode": "adaptive"},
            )
            kwargs: dict[str, Any] = {
                "config": config,
                "region_name": settings.aws_region,
            }
            if settings.aws_access_key_id:
                kwargs["aws_access_key_id"] = settings.aws_access_key_id
                kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
            self._client = boto3.client("bedrock-runtime", **kwargs)
        return self._client

    def get_llm(
        self,
        model_id: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 64000,  # Increased for Claude 4
        streaming: bool = True,
    ) -> ChatBedrock:
        """Return a cached ChatBedrock instance for the specified configuration."""
        resolved_model_id = model_id or settings.bedrock_model_id
        cache_key = f"{resolved_model_id}:{temperature}:{max_tokens}"

        if cache_key not in self._llm_cache:
            # Configure boto3 client with retries and timeouts
            from botocore.config import Config
            
            boto_config = Config(
                region_name=settings.aws_region,
                retries={
                    'max_attempts': 5,  # Increased from 3 to 5 for better resilience
                    'mode': 'adaptive'
                },
                read_timeout=300,  # 5 minutes for reading response
                connect_timeout=60,  # 1 minute for initial connection
                # Force signature v4 and ensure credentials are refreshed
                signature_version='v4',
                parameter_validation=False,  # Skip parameter validation for better performance
            )
            
            self._llm_cache[cache_key] = ChatBedrock(
                model_id=resolved_model_id,
                region_name=settings.aws_region,
                model_kwargs={
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                streaming=streaming,
                config=boto_config,  # Add the config for better timeout handling
            )
        return self._llm_cache[cache_key]
    
    def clear_cache(self) -> None:
        """Clear the LLM cache to force recreation of clients with fresh credentials."""
        self._llm_cache.clear()

    def get_fast_llm(self) -> ChatBedrock:
        """Return the faster / cheaper model instance (Haiku) for simple tasks."""
        return self.get_llm(
            model_id=settings.bedrock_fast_model_id,
            temperature=0.1,
            max_tokens=64000,
        )

    async def invoke(
        self,
        system_prompt: str,
        user_message: str,
        model_id: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 64000,  # Increased for Claude 4
        use_fast_model: bool = False,
    ) -> str:
        """Invoke the LLM and return the raw string response."""
        llm = (
            self.get_fast_llm()
            if use_fast_model
            else self.get_llm(
                model_id=model_id,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]
        response = await llm.ainvoke(messages)
        return response.content  # type: ignore[return-value]

    async def invoke_with_json_output(
        self,
        system_prompt: str,
        user_message: str,
        model_id: Optional[str] = None,
        use_fast_model: bool = False,
    ) -> dict[str, Any]:
        """
        Invoke the LLM and parse its response as JSON.

        Strips markdown code fences if the model wraps the response in them,
        which happens despite explicit instructions in some cases.
        """
        json_instruction = (
            "\n\nCRITICAL: Respond with ONLY a valid JSON object. "
            "No markdown fences, no explanation, no text before or after the JSON."
        )
        raw = await self.invoke(
            system_prompt=system_prompt + json_instruction,
            user_message=user_message,
            model_id=model_id,
            use_fast_model=use_fast_model,
        )
        return self._parse_json_response(raw)

    async def invoke_structured(
        self,
        system_prompt: str,
        user_message: str,
        response_model: Type[T],
        max_retries: int = 3,
        use_fast_model: bool = False,
    ) -> T:
        """
        Invoke the LLM and validate the JSON response against a Pydantic model.

        Retries up to max_retries times, feeding validation errors back to the
        model so it can self-correct.
        """
        from pydantic import ValidationError

        last_error: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                raw = await self.invoke_with_json_output(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    use_fast_model=use_fast_model,
                )
                return response_model.model_validate(raw)
            except (ValidationError, Exception) as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    user_message = (
                        f"{user_message}\n\n"
                        f"Previous attempt failed with: {exc}\n"
                        "Fix the JSON to match the required schema exactly."
                    )
                    logger.warning(
                        f"Structured output attempt {attempt + 1} failed: {exc}"
                    )

        raise last_error or RuntimeError("invoke_structured failed after all retries")

    @staticmethod
    def _parse_json_response(raw: str) -> dict[str, Any]:
        """Strip optional markdown fences and parse JSON."""
        clean = raw.strip()
        # Remove ```json ... ``` or ``` ... ``` wrappers
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
        
        try:
            return json.loads(clean)  # type: ignore[return-value]
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed. Error: {e}")
            logger.error(f"Raw response length: {len(raw)}")
            logger.error(f"Cleaned response length: {len(clean)}")
            logger.error(f"Last 200 chars of cleaned response: {clean[-200:]}")
            raise


# Module-level singleton consumed by all agents
bedrock_service = BedrockService()
