from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class CreateConversationRequest(BaseModel):
    title: str | None = Field(None, max_length=255)


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str | None
    tool_calls: dict | None = None
    token_count: int
    created_at: str

    model_config = {"from_attributes": True}


class ConversationDetailResponse(BaseModel):
    id: str
    title: str
    messages: list[MessageResponse]
    created_at: str
    updated_at: str
