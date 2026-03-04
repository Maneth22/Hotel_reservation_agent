from __future__ import annotations

from datetime import date

from app.models.reservation import AvailabilityResponse, RateLineItem, ReservationState, RoomSelection


class HotelAPIClient:
    """
    Replace mock methods with real HTTP calls to hotel management APIs.
    This client is the single source of truth for room catalog and availability.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url
        self.api_key = api_key

    def get_availability(self, check_in: date, check_out: date) -> AvailabilityResponse:
        # Mock payload for local testing. In production, call upstream API.
        payload = {
            "check_in": check_in,
            "check_out": check_out,
            "inventory": [
                {
                    "room_category": "Standard",
                    "room_type": "Queen",
                    "meal_plans": ["Room Only", "Breakfast"],
                    "max_occupancy": 2,
                    "available_rooms": 4,
                },
                {
                    "room_category": "Deluxe",
                    "room_type": "King",
                    "meal_plans": ["Breakfast", "Half Board"],
                    "max_occupancy": 3,
                    "available_rooms": 2,
                },
                {
                    "room_category": "Family",
                    "room_type": "Suite",
                    "meal_plans": ["Breakfast", "Full Board"],
                    "max_occupancy": 4,
                    "available_rooms": 1,
                },
            ],
        }
        return AvailabilityResponse.model_validate(payload)

    def validate_room_selection(self, check_in: date, check_out: date, rooms: list[RoomSelection]) -> None:
        availability = self.get_availability(check_in, check_out)
        inventory_by_key = {
            (item.room_category, item.room_type): item for item in availability.inventory
        }
        for room in rooms:
            key = (room.room_category, room.room_type)
            if key not in inventory_by_key:
                raise ValueError(f"Unknown room option: {room.room_category}/{room.room_type}")
            item = inventory_by_key[key]
            if room.room_count > item.available_rooms:
                raise ValueError(
                    f"Requested {room.room_count}x {room.room_category}/{room.room_type} but only {item.available_rooms} available"
                )
            if room.meal_plan and room.meal_plan not in item.meal_plans:
                raise ValueError(
                    f"Invalid meal_plan {room.meal_plan} for {room.room_category}/{room.room_type}; use one of {item.meal_plans}"
                )

    def get_rate_quote(self, reservation: ReservationState) -> tuple[str, list[RateLineItem], float, float, float]:
        if not reservation.check_in or not reservation.check_out:
            raise ValueError("Cannot calculate rates without check_in and check_out")
        if not reservation.rooms:
            raise ValueError("Cannot calculate rates without selected rooms")

        nights = (reservation.check_out - reservation.check_in).days
        if nights < 1:
            raise ValueError("Cannot calculate rates for invalid date range")

        rate_card = {
            ("Standard", "Queen"): 100.0,
            ("Deluxe", "King"): 165.0,
            ("Family", "Suite"): 220.0,
        }

        line_items: list[RateLineItem] = []
        subtotal = 0.0
        for room in reservation.rooms:
            key = (room.room_category, room.room_type)
            nightly_rate = rate_card.get(key)
            if nightly_rate is None:
                raise ValueError(f"No rate configured for {room.room_category}/{room.room_type}")
            total = nightly_rate * nights * room.room_count
            subtotal += total
            line_items.append(
                RateLineItem(
                    room_category=room.room_category,
                    room_type=room.room_type,
                    meal_plan=room.meal_plan,
                    room_count=room.room_count,
                    nightly_rate=nightly_rate,
                    nights=nights,
                    total=round(total, 2),
                )
            )

        taxes = round(subtotal * 0.12, 2)
        subtotal = round(subtotal, 2)
        total = round(subtotal + taxes, 2)
        return "USD", line_items, subtotal, taxes, total
