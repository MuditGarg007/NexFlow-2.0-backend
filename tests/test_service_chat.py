"""Tests for app/services/chat_service.py"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from tests.conftest import make_execute_result


def _make_message(role, content):
    msg = MagicMock()
    msg.role = role
    msg.content = content
    msg.created_at = datetime.now(timezone.utc)
    return msg


@pytest.mark.asyncio
async def test_list_conversations(mock_db, sample_user_id):
    conv = MagicMock()
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=[conv]))

    from app.services.chat_service import ChatService
    service = ChatService(mock_db)
    result = await service.list_conversations(sample_user_id)
    assert result == [conv]


@pytest.mark.asyncio
async def test_create_conversation_with_default_title(mock_db, sample_user_id):
    from app.services.chat_service import ChatService
    service = ChatService(mock_db)
    conv = await service.create_conversation(sample_user_id)
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()
    added_conv = mock_db.add.call_args[0][0]
    assert added_conv.title == "New Conversation"


@pytest.mark.asyncio
async def test_create_conversation_with_title(mock_db, sample_user_id):
    from app.services.chat_service import ChatService
    service = ChatService(mock_db)
    await service.create_conversation(sample_user_id, title="My Flow")
    added_conv = mock_db.add.call_args[0][0]
    assert added_conv.title == "My Flow"


@pytest.mark.asyncio
async def test_get_conversation_found(mock_db, sample_user_id):
    conv = MagicMock()
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalar=conv))

    from app.services.chat_service import ChatService
    service = ChatService(mock_db)
    result = await service.get_conversation(uuid.uuid4(), sample_user_id)
    assert result == conv


@pytest.mark.asyncio
async def test_get_conversation_not_found(mock_db, sample_user_id):
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalar=None))

    from app.services.chat_service import ChatService
    service = ChatService(mock_db)
    result = await service.get_conversation(uuid.uuid4(), sample_user_id)
    assert result is None


@pytest.mark.asyncio
async def test_delete_conversation_existing(mock_db, sample_user_id):
    conv = MagicMock()
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalar=conv))

    from app.services.chat_service import ChatService
    service = ChatService(mock_db)
    deleted = await service.delete_conversation(uuid.uuid4(), sample_user_id)
    assert deleted is True
    mock_db.delete.assert_called_once_with(conv)


@pytest.mark.asyncio
async def test_delete_conversation_not_found(mock_db, sample_user_id):
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalar=None))

    from app.services.chat_service import ChatService
    service = ChatService(mock_db)
    deleted = await service.delete_conversation(uuid.uuid4(), sample_user_id)
    assert deleted is False


@pytest.mark.asyncio
async def test_get_messages(mock_db):
    msgs = [_make_message("user", "hello"), _make_message("assistant", "hi")]
    mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=msgs))

    from app.services.chat_service import ChatService
    service = ChatService(mock_db)
    result = await service.get_messages(uuid.uuid4())
    assert result == msgs


@pytest.mark.asyncio
async def test_process_message_no_tools_direct_response(mock_db, sample_user_id):
    """When no integrations are connected the LLM is called without tools and yields token + done."""
    conv_id = uuid.uuid4()
    user_msg = _make_message("user", "hello")

    execute_calls = [
        make_execute_result(scalars_all=[]),   # save user message context
        make_execute_result(scalars_all=[user_msg]),  # get_messages for history
    ]
    call_idx = 0

    async def execute_side_effect(*args, **kwargs):
        nonlocal call_idx
        if call_idx < len(execute_calls):
            res = execute_calls[call_idx]
        else:
            res = make_execute_result(scalars_all=[user_msg])
        call_idx += 1
        return res

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    mock_llm = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello from AI"
    mock_response.choices[0].finish_reason = "stop"
    mock_llm.chat = AsyncMock(return_value=mock_response)

    with patch("app.services.chat_service.IntegrationService") as MockIntSvc, \
         patch("app.services.chat_service.get_llm_client", return_value=mock_llm), \
         patch("app.services.chat_service.get_tools_as_openai_format", return_value=[]):

        MockIntSvc.return_value.get_connected_integration_ids = AsyncMock(return_value=[])

        from app.services.chat_service import ChatService
        service = ChatService(mock_db)
        events = []
        async for event in service.process_message(sample_user_id, conv_id, "hello"):
            events.append(event)

    event_types = [e["event"] for e in events]
    assert "token" in event_types
    assert "done" in event_types


@pytest.mark.asyncio
async def test_process_message_yields_error_on_llm_failure(mock_db, sample_user_id):
    conv_id = uuid.uuid4()
    user_msg = _make_message("user", "crash please")

    execute_calls = [
        make_execute_result(scalars_all=[]),
        make_execute_result(scalars_all=[user_msg]),
    ]
    call_idx = 0

    async def execute_side_effect(*args, **kwargs):
        nonlocal call_idx
        if call_idx < len(execute_calls):
            res = execute_calls[call_idx]
        else:
            res = make_execute_result(scalars_all=[user_msg])
        call_idx += 1
        return res

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(side_effect=RuntimeError("LLM exploded"))

    with patch("app.services.chat_service.IntegrationService") as MockIntSvc, \
         patch("app.services.chat_service.get_llm_client", return_value=mock_llm), \
         patch("app.services.chat_service.get_tools_as_openai_format", return_value=[]):

        MockIntSvc.return_value.get_connected_integration_ids = AsyncMock(return_value=[])

        from app.services.chat_service import ChatService
        service = ChatService(mock_db)
        events = []
        async for event in service.process_message(sample_user_id, conv_id, "any"):
            events.append(event)

    event_types = [e["event"] for e in events]
    assert "error" in event_types
