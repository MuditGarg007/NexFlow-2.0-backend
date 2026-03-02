from openai import AsyncOpenAI
from app.config import get_settings
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class LLMClient:
    """
    Unified LLM client using OpenAI SDK.
    Supports both OpenAI and OpenRouter by swapping base_url.
    """

    def __init__(self, provider: str | None = None):
        self.provider = provider or settings.LLM_PROVIDER

        if self.provider == "openrouter":
            self.client = AsyncOpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
            )
            self.default_model = settings.OPENROUTER_DEFAULT_MODEL
        else:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            self.default_model = settings.DEFAULT_MODEL

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        model: str | None = None,
        temperature: float = 0.7,
    ):
        kwargs = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": stream,
        }

        resolved_model = kwargs["model"]
        no_temperature_models = ("o1", "o3", "o4", "gpt-5")
        if not any(resolved_model.startswith(m) for m in no_temperature_models):
            kwargs["temperature"] = temperature

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        logger.debug("llm_call", provider=self.provider, model=kwargs["model"], stream=stream)
        return await self.client.chat.completions.create(**kwargs)

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
    ):
        response = await self.chat(messages=messages, tools=tools, model=model)
        choice = response.choices[0]
        return {
            "content": choice.message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in (choice.message.tool_calls or [])
            ],
            "finish_reason": choice.finish_reason,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            },
        }


def get_llm_client(provider: str | None = None) -> LLMClient:
    return LLMClient(provider=provider)
