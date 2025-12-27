"""
Client for working with LLM (Ollama by default).
"""

import httpx
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """LLM configuration."""

    provider: str = "ollama"
    model: str = "qwen3:14b"
    base_url: str = "http://localhost:11434"
    timeout: int = 120
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class Message:
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


class LLMClient:
    """Client for working with LLM."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = httpx.Client(timeout=config.timeout)

    def chat(
        self, messages: List[Message], tools: Optional[List[dict]] = None
    ) -> Message:
        """Sends request to LLM."""

        if self.config.provider == "ollama":
            return self._chat_ollama(messages, tools)
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")

    def _chat_ollama(
        self, messages: List[Message], tools: Optional[List[dict]] = None
    ) -> Message:
        """Request to Ollama API."""

        url = f"{self.config.base_url}/api/chat"

        payload = {
            "model": self.config.model,
            "messages": [self._message_to_dict(m) for m in messages],
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }

        if tools:
            payload["tools"] = tools

        try:
            response = self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            message = data.get("message", {})

            # Parse tool calls if present
            tool_calls = None
            if "tool_calls" in message:
                tool_calls = [
                    {
                        "id": tc.get("id", f"call_{i}"),
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    }
                    for i, tc in enumerate(message["tool_calls"])
                ]

            return Message(
                role="assistant",
                content=message.get("content", ""),
                tool_calls=tool_calls,
            )

        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama request error: {e}")

    def _message_to_dict(self, message: Message) -> dict:
        """Converts Message to dictionary for API."""
        result = {"role": message.role, "content": message.content}
        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc["id"],
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in message.tool_calls
            ]
        if message.tool_call_id:
            result["tool_call_id"] = message.tool_call_id
        return result

    def close(self):
        """Closes client."""
        self.client.close()


def build_tools_schema(tool_descriptions: dict) -> List[dict]:
    """Builds JSON Schema for tools from prompt descriptions."""
    tools = []

    for name, desc in tool_descriptions.items():
        properties = {}
        required = []

        for param_name, param_info in desc.get("parameters", {}).items():
            properties[param_name] = {
                "type": param_info.get("type", "string"),
                "description": param_info.get("description", ""),
            }
            if param_info.get("required", False):
                required.append(param_name)

        tool = {
            "type": "function",
            "function": {
                "name": name,
                "description": desc.get("description", ""),
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
        tools.append(tool)

    return tools
