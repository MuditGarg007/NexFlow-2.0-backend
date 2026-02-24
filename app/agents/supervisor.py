from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage

from app.services.llm_client import get_llm_client
from app.mcp.registry import get_tool, get_tools_as_openai_format
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    conversation_id: str
    connected_integration_ids: list[str]
    iteration_count: int
    max_iterations: int
    final_response: str | None
    events: list[dict]


async def supervisor_node(state: AgentState) -> dict:
    """Main supervisor — decides whether to call a tool or respond directly."""
    llm = get_llm_client()
    tools = get_tools_as_openai_format(state["connected_integration_ids"])

    messages = [{"role": m.type if hasattr(m, 'type') else "user", "content": m.content} for m in state["messages"]]

    system_msg = {
        "role": "system",
        "content": (
            "You are NexFlow, an AI assistant. You help users interact with their connected apps. "
            "Use the available tools when the user asks to perform actions on their connected services. "
            "Be concise and helpful."
        ),
    }
    messages = [system_msg] + messages

    if tools:
        result = await llm.chat_with_tools(messages=messages, tools=tools)
    else:
        response = await llm.chat(messages=messages)
        result = {"content": response.choices[0].message.content, "tool_calls": []}

    events = list(state.get("events", []))

    if result["tool_calls"]:
        return {
            "messages": [AIMessage(content=result["content"] or "", additional_kwargs={"tool_calls": result["tool_calls"]})],
            "events": events + [{"event": "thinking", "data": f"Planning to call {len(result['tool_calls'])} tool(s)"}],
            "iteration_count": state["iteration_count"] + 1,
        }
    else:
        return {
            "messages": [AIMessage(content=result["content"])],
            "final_response": result["content"],
            "events": events + [{"event": "response", "data": result["content"]}],
            "iteration_count": state["iteration_count"] + 1,
        }


async def tool_executor_node(state: AgentState) -> dict:
    """Executes tool calls from the supervisor's decision."""
    last_message = state["messages"][-1]
    tool_calls = last_message.additional_kwargs.get("tool_calls", [])
    events = list(state.get("events", []))
    new_messages = []

    for tc in tool_calls:
        func_name = tc["function"]["name"]
        import json
        func_args = json.loads(tc["function"]["arguments"])

        events.append({"event": "tool_call", "data": {"tool": func_name, "status": "executing"}})

        tool = get_tool(func_name)
        if tool:
            try:
                # NOTE: in production, the OAuth token would be fetched here
                result = {"info": f"Tool {func_name} requires OAuth token — execute via ChatService for real calls"}
                events.append({"event": "tool_result", "data": {"tool": func_name, "result": result}})
            except Exception as e:
                result = {"error": str(e)}
                events.append({"event": "tool_error", "data": {"tool": func_name, "error": str(e)}})
        else:
            result = {"error": f"Unknown tool: {func_name}"}

        new_messages.append(ToolMessage(content=json.dumps(result), tool_call_id=tc["id"]))

    return {"messages": new_messages, "events": events}


def should_continue(state: AgentState) -> str:
    if state.get("final_response"):
        return END
    if state["iteration_count"] >= state["max_iterations"]:
        return END
    last = state["messages"][-1] if state["messages"] else None
    if last and hasattr(last, "additional_kwargs") and last.additional_kwargs.get("tool_calls"):
        return "tool_executor"
    return END


def build_agent_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("tool_executor", tool_executor_node)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges("supervisor", should_continue, {"tool_executor": "tool_executor", END: END})
    graph.add_edge("tool_executor", "supervisor")

    return graph.compile()
