from abc import ABC, abstractmethod


class BaseMCPTool(ABC):
    name: str
    description: str
    integration_id: str
    input_schema: dict
    requires_oauth: bool = True
    status: str = "stable"  # "stable" | "coming_soon" | "deprecated"

    def _check_status(self):
        if self.status == "coming_soon":
            raise NotImplementedError(
                f"Tool '{self.name}' is under development and not yet available. "
                "Check the repository for progress or open an issue to request prioritization."
            )

    @abstractmethod
    async def execute(self, params: dict, oauth_token: str) -> dict:
        """Execute the tool with given parameters and OAuth token."""
        ...

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": f"[COMING SOON] {self.description}" if self.status == "coming_soon" else self.description,
                "parameters": self.input_schema,
            },
        }
