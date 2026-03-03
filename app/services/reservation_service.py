from __future__ import annotations

from datetime import date

from app.clients.hotel_api_client import HotelAPIClient
from app.clients.ollama_client import OllamaExtractionClient
from app.models.reservation import (
    MANDATORY_FIELDS,
    AvailabilityResponse,
    ChatResponse,
    ReservationPatch,
    ReservationState,
    ReservationStatus,
)
from app.services.room_allocator import RoomAllocationEngine
from app.services.state_store import InMemoryStateStore


class ReservationService:
    def __init__(
        self,
        state_store: InMemoryStateStore,
        hotel_client: HotelAPIClient,
        llm_client: OllamaExtractionClient,
        allocator: RoomAllocationEngine,
    ) -> None:
        self.state_store = state_store
        self.hotel_client = hotel_client
        self.llm_client = llm_client
        self.allocator = allocator

    def get_availability(self, check_in: date, check_out: date) -> AvailabilityResponse:
        if check_in >= check_out:
            raise ValueError("check_out must be after check_in")
        return self.hotel_client.get_availability(check_in, check_out)

    def update_draft_from_chat(self, session_id: str, message: str) -> ChatResponse:
        current = self.state_store.get_or_create(session_id)
        options = self._availability_options(current)
        patch = self.llm_client.extract_patch(
            user_message=message,
            current_state=current.model_dump(mode="json"),
            available_options=options,
        )
        merged = self.apply_patch(current, patch)
        self._validate_rooms_with_inventory(merged)

        suggestions = self._suggest_rooms(merged)
        missing = self._missing_fields(merged)
        reply = self._build_reply(merged, missing, suggestions)

        self.state_store.save(session_id, merged)
        return ChatResponse(
            session_id=session_id,
            reservation=merged,
            reply=reply,
            suggestions=suggestions,
            missing_fields=missing,
        )

    def apply_patch(self, current: ReservationState, patch: ReservationPatch) -> ReservationState:
        data = current.model_dump()
        updates = patch.model_dump(exclude_unset=True)

        for key, value in updates.items():
            if value is None:
                continue
            data[key] = value

        return ReservationState.model_validate(data)

    def update_draft(self, session_id: str, patch: ReservationPatch) -> ReservationState:
        current = self.state_store.get_or_create(session_id)
        merged = self.apply_patch(current, patch)
        self._validate_rooms_with_inventory(merged)
        return self.state_store.save(session_id, merged)

    def confirm(self, session_id: str) -> ReservationState:
        reservation = self.state_store.get_or_create(session_id)
        missing = self._missing_fields(reservation)
        if missing:
            raise ValueError(f"Cannot confirm, missing fields: {missing}")
        self._validate_rooms_with_inventory(reservation)
        reservation.status = ReservationStatus.confirmed
        return self.state_store.save(session_id, reservation)

    def _availability_options(self, state: ReservationState) -> list[dict]:
        if not state.check_in or not state.check_out or state.check_in >= state.check_out:
            return []
        availability = self.hotel_client.get_availability(state.check_in, state.check_out)
        return [item.model_dump() for item in availability.inventory]

    def _validate_rooms_with_inventory(self, state: ReservationState) -> None:
        if state.rooms and state.check_in and state.check_out:
            self.hotel_client.validate_room_selection(state.check_in, state.check_out, state.rooms)

    def _suggest_rooms(self, state: ReservationState):
        if not (state.guests and state.check_in and state.check_out):
            return []
        availability = self.hotel_client.get_availability(state.check_in, state.check_out)
        return self.allocator.suggest(state.guests, availability.inventory)

    @staticmethod
    def _missing_fields(state: ReservationState) -> list[str]:
        missing = []
        for field in MANDATORY_FIELDS:
            if getattr(state, field) in (None, ""):
                missing.append(field)
        if not state.rooms:
            missing.append("rooms")
        return missing

    @staticmethod
    def _build_reply(state: ReservationState, missing: list[str], suggestions) -> str:
        if missing:
            return f"Draft updated. I still need: {', '.join(missing)}."
        if not suggestions:
            return "I cannot fit all guests with current availability. Please change dates or reduce guests."
        return "Draft updated and feasible room combinations are provided. Confirm when ready."
