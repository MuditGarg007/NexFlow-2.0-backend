import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.agent_session import AgentSession
from app.models.tool_execution import ToolExecution
from app.services.llm_client import get_llm_client
from app.services.integration_service import IntegrationService
from app.mcp.registry import get_tool, get_tools_as_openai_format
from app.utils.logger import get_logger
from app.config import get_settings

settings = get_settings()
logger = get_logger(__name__)

SYSTEM_PROMPT = """You are NexFlow, an AI assistant that helps users interact with their connected applications.
You have access to tools that can interact with the user's connected services (GitHub, Gmail, Google Calendar, Google Drive, Google Photos, LinkedIn).
When a user asks you to do something, determine which tool to call and with what parameters.
If the user asks about something you can't do with available tools, respond helpfully without calling a tool.
Always be concise and clear in your responses."""


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_conversations(self, user_id) -> list[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(result.scalars().all())

    async def create_conversation(self, user_id, title: str | None = None) -> Conversation:
        conv = Conversation(user_id=user_id, title=title or "New Conversation")
        self.db.add(conv)
        await self.db.flush()
        return conv

    async def get_conversation(self, conversation_id, user_id) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_conversation(self, conversation_id, user_id) -> bool:
        conv = await self.get_conversation(conversation_id, user_id)
        if conv:
            await self.db.delete(conv)
            return True
        return False

    async def get_messages(self, conversation_id) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return list(result.scalars().all())

    async def process_message(self, user_id, conversation_id, content: str):
        """
        Process a user message through the agent loop.
        Yields SSE events as the agent works.
        """
        integration_service = IntegrationService(self.db)
        connected_ids = await integration_service.get_connected_integration_ids(user_id)
        available_tools = get_tools_as_openai_format(connected_ids) if connected_ids else []

        # save user message
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=content,
        )
        self.db.add(user_msg)
        await self.db.flush()

        # create agent session
        session = AgentSession(
            user_id=user_id,
            conversation_id=conversation_id,
            status="running",
        )
        self.db.add(session)
        await self.db.flush()

        # build message history
        history = await self.get_messages(conversation_id)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content or ""})

        llm = get_llm_client()
        iteration = 0

        try:
            while iteration < settings.MAX_TOOL_CALLS_PER_TURN:
                iteration += 1

                if available_tools:
                    result = await llm.chat_with_tools(messages=messages, tools=available_tools)
                else:
                    response = await llm.chat(messages=messages)
                    result = {
                        "content": response.choices[0].message.content,
                        "tool_calls": [],
                        "finish_reason": response.choices[0].finish_reason,
                    }

                if not result["tool_calls"]:
                    # no tool calls — we have the final response
                    yield {"event": "token", "data": json.dumps({"content": result["content"]})}
                    assistant_msg = Message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=result["content"],
                    )
                    self.db.add(assistant_msg)
                    break

                # process tool calls
                for tc in result["tool_calls"]:
                    func_name = tc["function"]["name"]
                    func_args = json.loads(tc["function"]["arguments"])

                    yield {"event": "tool_call", "data": json.dumps({"tool": func_name, "params": func_args, "status": "executing"})}

                    tool = get_tool(func_name)
                    if not tool:
                        tool_result = {"error": f"Unknown tool: {func_name}"}
                    else:
                        try:
                            token = await integration_service.get_access_token(user_id, tool.integration_id)
                            import time
                            start = time.time()
                            tool_result = await tool.execute(func_args, token)
                            duration_ms = int((time.time() - start) * 1000)

                            tool_exec = ToolExecution(
                                agent_session_id=session.id,
                                integration_id=tool.integration_id,
                                tool_name=func_name,
                                method_name=func_name.split(".")[-1],
                                input_params=func_args,
                                output_result=tool_result,
                                duration_ms=duration_ms,
                                status="success",
                            )
                            self.db.add(tool_exec)
                        except Exception as e:
                            logger.error("tool_execution_failed", tool=func_name, error=str(e))
                            tool_result = {"error": str(e)}

                    yield {"event": "tool_result", "data": json.dumps({"tool": func_name, "result": tool_result})}

                    # add assistant + tool messages to history for next iteration
                    messages.append({"role": "assistant", "content": None, "tool_calls": [
                        {"id": tc["id"], "type": "function", "function": {"name": func_name, "arguments": tc["function"]["arguments"]}}
                    ]})
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(tool_result)})

            session.status = "completed"
            session.ended_at = datetime.now(timezone.utc)
            yield {"event": "done", "data": json.dumps({"session_id": str(session.id)})}

        except Exception as e:
            session.status = "failed"
            session.ended_at = datetime.now(timezone.utc)
            logger.error("agent_session_failed", error=str(e))
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
