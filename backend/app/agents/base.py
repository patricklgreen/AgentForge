import logging
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.services.bedrock import BedrockService, bedrock_service


class BaseAgent(ABC):
    """Abstract base class for all agents in the AgentForge pipeline."""

    def __init__(
        self,
        name: str,
        description: str,
        bedrock: BedrockService | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.bedrock = bedrock or bedrock_service
        self.logger = logging.getLogger(f"agents.{name}")

    @abstractmethod
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's task and return the updated state."""
        ...

    async def _invoke_llm(
        self,
        system_prompt: str,
        user_message: str,
        use_fast_model: bool = False,
    ) -> str:
        """Invoke the LLM and return the raw string response."""
        max_retries = 2  # Retry once for credential refresh
        
        for attempt in range(max_retries + 1):
            try:
                llm = (
                    self.bedrock.get_fast_llm()
                    if use_fast_model
                    else self.bedrock.get_llm()
                )
                messages: list[BaseMessage] = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_message),
                ]
                
                # Add timeout to prevent individual LLM calls from hanging indefinitely
                import asyncio
                timeout_minutes = 10  # 10 minutes per LLM call should be more than enough
                
                try:
                    async with asyncio.timeout(timeout_minutes * 60):
                        response = await llm.ainvoke(messages)
                except asyncio.TimeoutError:
                    error_msg = f"LLM call timed out after {timeout_minutes} minutes"
                    self.logger.error(error_msg)
                    raise Exception(error_msg)
                    
                return response.content  # type: ignore[return-value]
                
            except Exception as exc:
                error_str = str(exc)
                
                # Check for AWS signature expiration errors
                if "InvalidSignatureException" in error_str or "Signature expired" in error_str:
                    self.logger.warning(f"AWS signature expired on attempt {attempt + 1}: {exc}")
                    
                    if attempt < max_retries:
                        # Clear the LLM cache to force credential refresh
                        self.logger.info("Clearing Bedrock cache to refresh credentials...")
                        self.bedrock.clear_cache()
                        
                        # Wait a bit before retry to allow credential refresh
                        import asyncio
                        await asyncio.sleep(2)
                        continue
                
                self.logger.error(f"LLM invocation failed: {exc}")
                raise

    async def _invoke_llm_json(
        self,
        system_prompt: str,
        user_message: str,
        use_fast_model: bool = False,
    ) -> dict[str, Any]:
        """Invoke LLM and parse the response as JSON."""
        return await self.bedrock.invoke_with_json_output(
            system_prompt=system_prompt,
            user_message=user_message,
            use_fast_model=use_fast_model,
        )

    def _log_step(self, message: str, data: Any = None) -> None:
        self.logger.info(
            f"[{self.name}] {message}",
            extra={"data": data} if data else {},
        )
