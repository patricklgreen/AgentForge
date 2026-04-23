import asyncio
import errno
import inspect
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


def _retryable_exception_types() -> tuple[type[BaseException], ...]:
    """Types raised by boto3/urllib3 on flaky network, DNS, or idle connections."""
    types: list[type[BaseException]] = []
    try:
        from botocore.exceptions import (
            ConnectTimeoutError,
            EndpointConnectionError,
            ReadTimeoutError,
        )

        types.extend((EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError))
    except ImportError:
        pass
    try:
        from urllib3.exceptions import MaxRetryError, NewConnectionError
        from urllib3.exceptions import ReadTimeoutError as Urllib3ReadTimeoutError

        types.extend((NewConnectionError, MaxRetryError, Urllib3ReadTimeoutError))
    except ImportError:
        pass
    return tuple(types)


_RETRYABLE_EXC_TYPES = _retryable_exception_types()

# Transient AWS / HTTP / transport errors worth retrying with a fresh client
_RETRYABLE_SUBSTRINGS = (
    "InvalidSignatureException",
    "Signature expired",
    "SignatureDoesNotMatch",
    "RequestExpired",
    "ExpiredToken",
    "ExpiredTokenException",
    "CredentialsExpired",
    "Response ended prematurely",
    "IncompleteRead",
    # Offline / network / DNS (botocore EndpointConnectionError message, etc.)
    "Could not connect to the endpoint URL",
    "Connection reset by peer",
    "Connection refused",
    "Name or service not known",
    "Network is unreachable",
    "Temporary failure in name resolution",
    "Failed to establish a new connection",
)

def _network_errnos() -> frozenset[int]:
    codes: list[int] = [
        errno.ECONNREFUSED,
        errno.ECONNRESET,
        errno.ETIMEDOUT,
        errno.EPIPE,
        errno.ENETUNREACH,
        errno.EHOSTUNREACH,
    ]
    for name in ("EAI_AGAIN", "ENETDOWN"):
        if hasattr(errno, name):
            codes.append(getattr(errno, name))
    return frozenset(codes)


_NETWORK_ERRNOS = _network_errnos()


def _is_retryable_aws_error(exc: BaseException) -> bool:
    if isinstance(exc, _RETRYABLE_EXC_TYPES):
        return True
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in _NETWORK_ERRNOS:
        return True
    s = str(exc)
    if any(x in s for x in _RETRYABLE_SUBSTRINGS):
        return True
    t = type(exc).__name__
    if t in ("ProtocolError", "IncompleteRead", "ClientConnectorError", "ClientOSError"):
        return True
    return False


def _bedrock_config() -> Config:
    """Botocore config: keep connections alive and allow long model responses."""
    params: dict[str, Any] = {
        "region_name": settings.aws_region,
        "retries": {"max_attempts": 5, "mode": "adaptive"},
        "read_timeout": 300,
        "connect_timeout": 60,
        "signature_version": "v4",
        "parameter_validation": False,
    }
    # tcp_keepalive reduces idle disconnects on long runs (botocore 1.29.0+)
    sig = inspect.signature(Config.__init__)
    if "tcp_keepalive" in sig.parameters:
        params["tcp_keepalive"] = True
    return Config(**params)


class BedrockService:
    """Service for interacting with AWS Bedrock (Claude models).

    **Credential / signature robustness**
    - Passes ``aws_session_token`` when present (STS / assumed-role sessions).
    - Builds a **new** ``ChatBedrock`` for each ``ainvoke`` so boto clients are
      never reused across long pipeline gaps (avoids stale signatures).
    - Retries transient signature, network, and connection errors with backoff
      (see ``bedrock_invoke_max_attempts``).
    """

    def __init__(self) -> None:
        # Legacy: tests and clear_cache() expect this attribute
        self._llm_cache: dict[str, ChatBedrock] = {}
        self._client: Optional[Any] = None

    @property
    def client(self) -> Any:
        """Rarely used; prefer ChatBedrock per invoke. Kept for compatibility."""
        if self._client is None:
            kwargs: dict[str, Any] = {
                "config": Config(
                    region_name=settings.aws_region,
                    retries={"max_attempts": 3, "mode": "adaptive"},
                ),
                "region_name": settings.aws_region,
            }
            if settings.aws_access_key_id and settings.aws_secret_access_key:
                kwargs["aws_access_key_id"] = settings.aws_access_key_id
                kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
                if settings.aws_session_token:
                    kwargs["aws_session_token"] = settings.aws_session_token
            self._client = boto3.client("bedrock-runtime", **kwargs)
        return self._client

    def _chat_bedrock_kwargs(
        self,
        model_id: str,
        temperature: float,
        max_tokens: int,
        streaming: bool,
    ) -> dict[str, Any]:
        kw: dict[str, Any] = {
            "model_id": model_id,
            "region_name": settings.aws_region,
            "model_kwargs": {
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            "streaming": streaming,
            "config": _bedrock_config(),
        }
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            kw["aws_access_key_id"] = settings.aws_access_key_id
            kw["aws_secret_access_key"] = settings.aws_secret_access_key
            if settings.aws_session_token:
                kw["aws_session_token"] = settings.aws_session_token
        return kw

    def _new_chat_bedrock(
        self,
        model_id: str,
        temperature: float,
        max_tokens: int,
        streaming: bool = False,
    ) -> ChatBedrock:
        """Fresh client + model — avoids stale SigV4 after long idle periods."""
        return ChatBedrock(**self._chat_bedrock_kwargs(model_id, temperature, max_tokens, streaming))

    def get_llm(
        self,
        model_id: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 64000,
        streaming: bool = False,
    ) -> ChatBedrock:
        """Return a **new** ChatBedrock (not cached) with the given configuration."""
        resolved = model_id or settings.bedrock_model_id
        return self._new_chat_bedrock(resolved, temperature, max_tokens, streaming)

    def clear_cache(self) -> None:
        """Drop cached boto clients so the next connection uses fresh credentials."""
        self._llm_cache.clear()
        self._client = None

    def get_fast_llm(self) -> ChatBedrock:
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
        max_tokens: int = 64000,
        use_fast_model: bool = False,
    ) -> tuple[str, dict]:
        """Invoke the LLM; retries signature / connection failures with fresh clients."""
        resolved_model_id = (
            settings.bedrock_fast_model_id
            if use_fast_model
            else (model_id or settings.bedrock_model_id)
        )
        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        max_rounds = settings.bedrock_invoke_max_attempts

        for attempt in range(max_rounds):
            try:
                llm = self._new_chat_bedrock(
                    resolved_model_id,
                    temperature,
                    max_tokens,
                    streaming=False,
                )
                response = await llm.ainvoke(messages)

                um = getattr(response, "usage_metadata", None) or {}
                usage_info = {
                    "input_tokens": um.get("input_tokens", 0),
                    "output_tokens": um.get("output_tokens", 0),
                    "model_id": resolved_model_id,
                }
                return response.content, usage_info  # type: ignore[return-value]

            except Exception as exc:
                if _is_retryable_aws_error(exc) and attempt < max_rounds - 1:
                    logger.warning(
                        "Bedrock invoke retry %s/%s after: %s",
                        attempt + 1,
                        max_rounds,
                        exc,
                    )
                    self.clear_cache()
                    await asyncio.sleep(min(2**attempt, 30))
                    continue
                raise

    async def invoke_with_json_output(
        self,
        system_prompt: str,
        user_message: str,
        model_id: Optional[str] = None,
        use_fast_model: bool = False,
    ) -> tuple[dict[str, Any], dict]:
        json_instruction = (
            "\n\nCRITICAL: Respond with ONLY a valid JSON object. "
            "No markdown fences, no explanation, no text before or after the JSON."
        )
        raw, usage_info = await self.invoke(
            system_prompt=system_prompt + json_instruction,
            user_message=user_message,
            model_id=model_id,
            use_fast_model=use_fast_model,
        )
        return self._parse_json_response(raw), usage_info

    async def invoke_structured(
        self,
        system_prompt: str,
        user_message: str,
        response_model: Type[T],
        max_retries: int = 3,
        use_fast_model: bool = False,
    ) -> T:
        from pydantic import ValidationError

        last_error: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                raw_dict, usage_info = await self.invoke_with_json_output(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    use_fast_model=use_fast_model,
                )
                return response_model.model_validate(raw_dict)
            except (ValidationError, Exception) as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    user_message = (
                        f"{user_message}\n\n"
                        f"Previous attempt failed with: {exc}\n"
                        "Fix the JSON to match the required schema exactly."
                    )
                    logger.warning("Structured output attempt %s failed: %s", attempt + 1, exc)

        raise last_error or RuntimeError("invoke_structured failed after all retries")

    @staticmethod
    def _parse_json_response(raw: str) -> dict[str, Any]:
        import re

        clean = raw.strip()
        json_block_pattern = r"```(?:json)?\s*(.*?)\s*```"
        match = re.search(json_block_pattern, clean, re.DOTALL)
        if match:
            clean = match.group(1).strip()
        else:
            json_pattern = r"\{.*\}"
            match = re.search(json_pattern, clean, re.DOTALL)
            if match:
                clean = match.group(0).strip()

        try:
            return json.loads(clean)  # type: ignore[return-value]
        except json.JSONDecodeError as e:
            logger.error("JSON parsing failed. Error: %s", e)
            logger.error("Raw response length: %s", len(raw))
            logger.error("Last 200 chars of cleaned response: %s", clean[-200:])
            raise


bedrock_service = BedrockService()
