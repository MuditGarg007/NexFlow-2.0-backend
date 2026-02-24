from abc import ABC, abstractmethod


class BaseMCPTool(ABC):
    name: str
    description: str
    integration_id: str
    input_schema: dict
    requires_oauth: bool = True

    @abstractmethod
    async def execute(self, params: dict, oauth_token: str) -> dict:
        """Execute the tool with given parameters and OAuth token."""
        ...

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }
