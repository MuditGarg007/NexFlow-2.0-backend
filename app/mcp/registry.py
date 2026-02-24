from app.mcp.base import BaseMCPTool
from app.utils.logger import get_logger

logger = get_logger(__name__)

_registry: dict[str, BaseMCPTool] = {}


def register_tool(tool: BaseMCPTool):
    _registry[tool.name] = tool
    logger.info("tool_registered", tool=tool.name, integration=tool.integration_id)


def get_tool(name: str) -> BaseMCPTool | None:
    return _registry.get(name)


def get_tools_for_integration(integration_id: str) -> list[BaseMCPTool]:
    return [t for t in _registry.values() if t.integration_id == integration_id]


def get_all_tools() -> list[BaseMCPTool]:
    return list(_registry.values())


def get_tools_as_openai_format(integration_ids: list[str] | None = None) -> list[dict]:
    tools = _registry.values()
    if integration_ids:
        tools = [t for t in tools if t.integration_id in integration_ids]
    return [t.to_openai_tool() for t in tools]


def init_registry():
    """Register all built-in tool adapters."""
    from app.mcp.adapters import github, gmail, google_calendar, google_drive, google_photos, linkedin
    for module in [github, gmail, google_calendar, google_drive, google_photos, linkedin]:
        module.register_tools()
    logger.info("mcp_registry_initialized", tool_count=len(_registry))
