from datetime import date

from app.clients.hotel_api_client import HotelAPIClient
from app.models.reservation import ReservationPatch, ReservationState
from app.services.reservation_service import ReservationService
from app.services.room_allocator import RoomAllocationEngine
from app.services.state_store import InMemoryStateStore


class FakeLLMClient:
    def extract_patch(self, user_message, current_state, available_options):
        return ReservationPatch(
            check_in=date(2026, 6, 2),
            check_out=date(2026, 6, 5),
            guests=3,
            name="John",
            email="john@example.com",
            phone="+12025550123",
        )


class FakeChatAgent:
    def generate_reply(self, user_message, reservation, suggestions, availability_inventory, missing_fields):
        return f"Agent response for {reservation.get('name')} with {len(suggestions)} room suggestion sets."


def test_chat_with_agent_uses_langchain_reply():
    service = ReservationService(
        state_store=InMemoryStateStore(),
        hotel_client=HotelAPIClient("mock", ""),
        llm_client=FakeLLMClient(),
        allocator=RoomAllocationEngine(),
        chat_agent=FakeChatAgent(),
    )

    response = service.chat_with_agent("session-1", "Need 3 guests")

    assert response.reply.startswith("Agent response for John")
    assert response.reservation.email == "john@example.com"
    assert isinstance(response.suggestions, list)


def test_chat_with_agent_falls_back_to_basic_reply_without_agent():
    service = ReservationService(
        state_store=InMemoryStateStore(),
        hotel_client=HotelAPIClient("mock", ""),
        llm_client=FakeLLMClient(),
        allocator=RoomAllocationEngine(),
        chat_agent=None,
    )

    response = service.chat_with_agent("session-2", "Need 3 guests")

    assert "Draft updated" in response.reply
