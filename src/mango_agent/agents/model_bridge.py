"""LangChain-message bridge backed by the provider-independent model port.

LangGraph owns state transitions and tool dispatch.  This bridge only adapts
LangChain's message representation to Mango's :class:`ModelPort`, so the
agent remains independent from a provider SDK and does not need to implement
LangChain's full ``BaseChatModel`` surface.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, final

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from mango_agent.shared.domain.errors import ValidationError
from mango_agent.shared.ports.model import Message, ModelPort, Tool, ToolResult

__all__ = ["ModelPortChatBridge"]


@final
class ModelPortChatBridge:
    """Adapt LangChain messages and JSON tool schemas to ``ModelPort``."""

    def __init__(self, model: ModelPort) -> None:
        self._model = model

    async def ainvoke(
        self,
        messages: Sequence[BaseMessage],
        tools: Sequence[Tool | Mapping[str, object]] = (),
        *,
        temperature: float | None = None,
    ) -> AIMessage:
        """Return one LangChain ``AIMessage`` from the configured model port."""
        response = await self._model.invoke(
            messages=tuple(self._to_model_message(message) for message in messages),
            tools=tuple(self._to_model_tool(tool) for tool in tools),
            temperature=temperature,
        )
        return AIMessage(
            content=response.content or "",
            tool_calls=[
                {
                    "name": call.name,
                    "args": call.arguments,
                    "id": call.id,
                    "type": "tool_call",
                }
                for call in response.tool_calls
            ],
            usage_metadata={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
        )

    def _to_model_message(self, message: BaseMessage) -> Message | ToolResult:
        content = self._content_to_text(message.content)
        if isinstance(message, ToolMessage):
            return ToolResult(id=message.tool_call_id, content=content)
        if isinstance(message, HumanMessage):
            return Message(role="user", content=content)
        if isinstance(message, AIMessage):
            return Message(role="assistant", content=content)
        if isinstance(message, SystemMessage):
            return Message(role="system", content=content)
        raise ValidationError(f"unsupported LangChain message type: {type(message).__name__}")

    def _to_model_tool(self, tool: Tool | Mapping[str, object]) -> Tool:
        if isinstance(tool, Tool):
            return tool

        name = tool.get("name")
        description = tool.get("description", "")
        parameters = tool.get("parameters", tool.get("parameters_schema"))
        if not isinstance(name, str) or not isinstance(description, str):
            raise ValidationError("tool schema must include string name and description")
        if not isinstance(parameters, dict):
            raise ValidationError("tool schema must include an object parameters schema")
        return Tool(name=name, description=description, parameters_schema=dict(parameters))

    def _content_to_text(self, content: str | list[str | dict[str, Any]]) -> str:
        if isinstance(content, str):
            return content
        return json.dumps(content, ensure_ascii=False, sort_keys=True, default=str)
