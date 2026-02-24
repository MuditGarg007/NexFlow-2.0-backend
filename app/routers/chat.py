import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.chat_service import ChatService
from app.schemas.chat import (
    SendMessageRequest, CreateConversationRequest,
    ConversationResponse, ConversationDetailResponse, MessageResponse,
)
from app.middleware.rate_limiter import rate_limit_chat

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = ChatService(db)
    convs = await service.list_conversations(user.id)
    return [
        ConversationResponse(
            id=str(c.id), title=c.title,
            created_at=c.created_at.isoformat(), updated_at=c.updated_at.isoformat(),
        )
        for c in convs
    ]


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(body: CreateConversationRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = ChatService(db)
    conv = await service.create_conversation(user.id, body.title)
    return ConversationResponse(
        id=str(conv.id), title=conv.title,
        created_at=conv.created_at.isoformat(), updated_at=conv.updated_at.isoformat(),
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = ChatService(db)
    conv = await service.get_conversation(conversation_id, user.id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    messages = await service.get_messages(conversation_id)
    return ConversationDetailResponse(
        id=str(conv.id), title=conv.title,
        messages=[
            MessageResponse(
                id=str(m.id), role=m.role, content=m.content,
                tool_calls=m.tool_calls, token_count=m.token_count,
                created_at=m.created_at.isoformat(),
            )
            for m in messages
        ],
        created_at=conv.created_at.isoformat(), updated_at=conv.updated_at.isoformat(),
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = ChatService(db)
    deleted = await service.delete_conversation(conversation_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


@router.post("/conversations/{conversation_id}/messages", dependencies=[Depends(rate_limit_chat)])
async def send_message(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ChatService(db)
    conv = await service.get_conversation(conversation_id, user.id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    async def event_stream():
        async for event in service.process_message(user.id, conversation_id, body.content):
            yield f"event: {event['event']}\ndata: {event['data']}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
