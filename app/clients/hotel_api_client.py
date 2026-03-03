from __future__ import annotations

from datetime import date

from app.models.reservation import AvailabilityResponse, RoomSelection


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
