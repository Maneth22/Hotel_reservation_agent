from datetime import date

from app.clients.hotel_api_client import HotelAPIClient
from app.models.reservation import ReservationPatch, ReservationState, RoomSelection
from app.services.reservation_service import ReservationService
from app.services.room_allocator import RoomAllocationEngine
from app.services.state_store import InMemoryStateStore


class FakeLLMClient:
    def extract_patch(self, user_message, current_state, available_options):
        return ReservationPatch(guests=3)


def build_service() -> ReservationService:
    return ReservationService(
        state_store=InMemoryStateStore(),
        hotel_client=HotelAPIClient("mock", ""),
        llm_client=FakeLLMClient(),
        allocator=RoomAllocationEngine(),
    )


def test_apply_patch_does_not_overwrite_with_null():
    service = build_service()
    current = ReservationState(
        check_in=date(2026, 6, 1),
        check_out=date(2026, 6, 4),
        guests=2,
        email="old@example.com",
        rooms=[RoomSelection(room_category="Standard", room_type="Queen", room_count=1)],
    )
    patch = ReservationPatch(email=None, guests=4)

    merged = service.apply_patch(current, patch)

    assert merged.email == "old@example.com"
    assert merged.guests == 4


def test_confirm_fails_when_missing_required_fields():
    service = build_service()
    session_id = "s1"
    service.state_store.save(session_id, ReservationState())

    try:
        service.confirm(session_id)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "missing fields" in str(exc)


def test_confirm_fails_when_room_capacity_is_insufficient():
    service = build_service()
    session_id = "s2"
    service.state_store.save(
        session_id,
        ReservationState(
            check_in=date(2026, 6, 1),
            check_out=date(2026, 6, 4),
            guests=5,
            name="John",
            email="john@example.com",
            phone="+12025550123",
            rooms=[RoomSelection(room_category="Standard", room_type="Queen", room_count=1)],
        ),
    )

    try:
        service.confirm(session_id)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Selected rooms can host" in str(exc)
