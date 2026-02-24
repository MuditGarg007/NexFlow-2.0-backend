"""Tests for app/mcp/base.py and app/mcp/registry.py"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── BaseMCPTool ───────────────────────────────────────────────────────────────

class ConcreteTool:
    name = "test.do_something"
    description = "A test tool"
    integration_id = "testservice"
    input_schema = {
        "type": "object",
        "properties": {
            "param1": {"type": "string"},
        },
        "required": ["param1"],
    }
    requires_oauth = True

    async def execute(self, params: dict, oauth_token: str) -> dict:
        return {"result": params["param1"]}

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


def test_to_openai_tool_format():
    tool = ConcreteTool()
    result = tool.to_openai_tool()
    assert result["type"] == "function"
    assert result["function"]["name"] == "test.do_something"
    assert result["function"]["description"] == "A test tool"
    assert result["function"]["parameters"] == tool.input_schema


@pytest.mark.asyncio
async def test_tool_execute():
    tool = ConcreteTool()
    result = await tool.execute({"param1": "hello"}, "token123")
    assert result == {"result": "hello"}


# ── Registry ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_registry():
    """Reset the registry before and after each test."""
    import app.mcp.registry as reg
    original = dict(reg._registry)
    reg._registry.clear()
    yield
    reg._registry.clear()
    reg._registry.update(original)


def test_register_and_get_tool():
    from app.mcp.registry import register_tool, get_tool
    tool = ConcreteTool()
    register_tool(tool)
    assert get_tool("test.do_something") is tool


def test_get_tool_not_found():
    from app.mcp.registry import get_tool
    assert get_tool("nonexistent.tool") is None


def test_get_tools_for_integration():
    from app.mcp.registry import register_tool, get_tools_for_integration

    tool1 = ConcreteTool()
    tool1.name = "svc.tool_a"
    tool1.integration_id = "myservice"

    tool2 = ConcreteTool()
    tool2.name = "other.tool_b"
    tool2.integration_id = "otherservice"

    register_tool(tool1)
    register_tool(tool2)

    result = get_tools_for_integration("myservice")
    assert len(result) == 1
    assert result[0].name == "svc.tool_a"


def test_get_all_tools():
    from app.mcp.registry import register_tool, get_all_tools

    tool1 = ConcreteTool()
    tool1.name = "svc.a"
    tool2 = ConcreteTool()
    tool2.name = "svc.b"
    register_tool(tool1)
    register_tool(tool2)

    all_tools = get_all_tools()
    assert len(all_tools) == 2


def test_get_tools_as_openai_format_all():
    from app.mcp.registry import register_tool, get_tools_as_openai_format

    tool = ConcreteTool()
    tool.name = "svc.t"
    register_tool(tool)

    result = get_tools_as_openai_format()
    assert len(result) == 1
    assert result[0]["type"] == "function"


def test_get_tools_as_openai_format_filtered():
    from app.mcp.registry import register_tool, get_tools_as_openai_format

    tool1 = ConcreteTool()
    tool1.name = "gh.list_repos"
    tool1.integration_id = "github"

    tool2 = ConcreteTool()
    tool2.name = "gc.list_events"
    tool2.integration_id = "google"

    register_tool(tool1)
    register_tool(tool2)

    result = get_tools_as_openai_format(integration_ids=["github"])
    assert len(result) == 1
    assert result[0]["function"]["name"] == "gh.list_repos"


def test_get_tools_as_openai_format_empty_integration_list_returns_all():
    """An empty list is falsy, so the source code's `if integration_ids:` skips
    filtering and returns all registered tools — same behaviour as None."""
    from app.mcp.registry import register_tool, get_tools_as_openai_format

    tool = ConcreteTool()
    tool.name = "svc.x"
    register_tool(tool)

    result = get_tools_as_openai_format(integration_ids=[])
    assert len(result) == 1


def test_register_tool_overwrites_same_name():
    from app.mcp.registry import register_tool, get_tool

    tool1 = ConcreteTool()
    tool1.name = "svc.same"

    tool2 = ConcreteTool()
    tool2.name = "svc.same"
    tool2.description = "Overwritten"

    register_tool(tool1)
    register_tool(tool2)
    assert get_tool("svc.same").description == "Overwritten"
