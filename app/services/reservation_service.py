from __future__ import annotations

from datetime import date

from app.clients.hotel_api_client import HotelAPIClient
from app.clients.ollama_client import OllamaExtractionClient
from app.models.reservation import (
    MANDATORY_FIELDS,
    AvailabilityResponse,
    ChatResponse,
    ConfirmResponse,
    ReservationReceipt,
    ReservationPatch,
    ReservationState,
    ReservationStatus,
)
from app.services.room_allocator import RoomAllocationEngine
from app.agents_langchain import LangChainHotelAgent
from app.services.state_store import InMemoryStateStore


class ReservationService:
    def __init__(
        self,
        state_store: InMemoryStateStore,
        hotel_client: HotelAPIClient,
        llm_client: OllamaExtractionClient,
        allocator: RoomAllocationEngine,
        chat_agent: LangChainHotelAgent | None = None,
    ) -> None:
        self.state_store = state_store
        self.hotel_client = hotel_client
        self.llm_client = llm_client
        self.allocator = allocator
        self.chat_agent = chat_agent

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
        self._validate_guest_capacity_constraints(merged)

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


    def chat_with_agent(self, session_id: str, message: str) -> ChatResponse:
        response = self.update_draft_from_chat(session_id, message)
        inventory = []
        if response.reservation.check_in and response.reservation.check_out:
            availability = self.hotel_client.get_availability(
                response.reservation.check_in, response.reservation.check_out
            )
            inventory = [item.model_dump(mode="json") for item in availability.inventory]

        if self.chat_agent:
            response.reply = self.chat_agent.generate_reply(
                user_message=message,
                reservation=response.reservation.model_dump(mode="json"),
                suggestions=[
                    [room.model_dump(mode="json") for room in combo]
                    for combo in response.suggestions
                ],
                availability_inventory=inventory,
                missing_fields=response.missing_fields,
            )
        return response

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
        self._validate_guest_capacity_constraints(merged)
        return self.state_store.save(session_id, merged)

    def confirm(self, session_id: str) -> ConfirmResponse:
        reservation = self.state_store.get_or_create(session_id)
        missing = self._missing_fields(reservation)
        if missing:
            raise ValueError(f"Cannot confirm, missing fields: {missing}")
        self._validate_rooms_with_inventory(reservation)
        self._validate_guest_capacity_constraints(reservation)
        reservation.status = ReservationStatus.confirmed
        saved = self.state_store.save(session_id, reservation)
        receipt = self.generate_receipt(session_id)
        return ConfirmResponse(reservation=saved, receipt=receipt)

    def generate_receipt(self, session_id: str) -> ReservationReceipt:
        reservation = self.state_store.get_or_create(session_id)
        if reservation.status != ReservationStatus.confirmed:
            raise ValueError("Reservation must be confirmed before generating receipt")
        if not (reservation.check_in and reservation.check_out and reservation.guests):
            raise ValueError("Missing reservation details for receipt generation")

        currency, line_items, subtotal, taxes, total = self.hotel_client.get_rate_quote(reservation)
        nights = (reservation.check_out - reservation.check_in).days
        return ReservationReceipt(
            session_id=session_id,
            check_in=reservation.check_in,
            check_out=reservation.check_out,
            guests=reservation.guests,
            nights=nights,
            currency=currency,
            line_items=line_items,
            subtotal=subtotal,
            taxes=taxes,
            total=total,
        )

    def _availability_options(self, state: ReservationState) -> list[dict]:
        if not state.check_in or not state.check_out or state.check_in >= state.check_out:
            return []
        availability = self.hotel_client.get_availability(state.check_in, state.check_out)
        return [item.model_dump() for item in availability.inventory]

    def _validate_rooms_with_inventory(self, state: ReservationState) -> None:
        if state.rooms and state.check_in and state.check_out:
            self.hotel_client.validate_room_selection(state.check_in, state.check_out, state.rooms)


    def _validate_guest_capacity_constraints(self, state: ReservationState) -> None:
        if not state.rooms or not state.guests:
            return
        if not (state.check_in and state.check_out):
            raise ValueError("check_in and check_out are required when rooms are selected")

        availability = self.hotel_client.get_availability(state.check_in, state.check_out)
        occupancy_map = {
            (item.room_category, item.room_type): item.max_occupancy for item in availability.inventory
        }
        selected_capacity = 0
        for room in state.rooms:
            key = (room.room_category, room.room_type)
            if key not in occupancy_map:
                raise ValueError(f"Unknown room option: {room.room_category}/{room.room_type}")
            selected_capacity += occupancy_map[key] * room.room_count

        if selected_capacity < state.guests:
            raise ValueError(
                f"Selected rooms can host {selected_capacity} guests, but reservation requires {state.guests}"
            )

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
