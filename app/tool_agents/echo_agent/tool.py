"""Echo Agent Tool 구현."""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact, build_artifact

AGENT_TYPE = "echo_agent"


class EchoToolInput(BaseModel):
    """Echo Tool 입력 스키마."""

    text: str = Field(..., description="그대로 되돌려줄 텍스트")


class EchoTool(BaseAgentTool):
    """입력 텍스트를 그대로 반환하는 최소 Tool."""

    name: str = "echo"
    description: str = "입력한 텍스트를 그대로 되돌려줍니다. 테스트/검증용 도구입니다."
    args_schema: type[BaseModel] = EchoToolInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(self, text: str, config: RunnableConfig | None = None):
        return self._echo(text)

    async def _arun(self, text: str, config: RunnableConfig | None = None):
        return self._echo(text)

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="에코 처리 중 오류가 발생했습니다")
    def _echo(self, text: str) -> tuple[str, dict]:
        artifact = build_artifact(AGENT_TYPE, echoed=text)
        return text, artifact

    def format_content(self, message: ToolMessage) -> ToolMessage:
        if isinstance(message.artifact, dict):
            echoed = message.artifact.get("echoed", "")
            return message.model_copy(update={"content": f"echo: {echoed}"})
        return message
