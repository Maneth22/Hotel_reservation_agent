from app.models.reservation import AvailabilityRoom
from app.services.room_allocator import RoomAllocationEngine


def test_allocator_returns_ranked_combinations():
    inventory = [
        AvailabilityRoom(
            room_category="Standard",
            room_type="Queen",
            meal_plans=["Breakfast"],
            max_occupancy=2,
            available_rooms=3,
        ),
        AvailabilityRoom(
            room_category="Family",
            room_type="Suite",
            meal_plans=["Breakfast"],
            max_occupancy=4,
            available_rooms=1,
        ),
    ]

    suggestions = RoomAllocationEngine().suggest(guests=5, inventory=inventory, top_k=2)

    assert suggestions
    total_capacity_first = sum(
        room.room_count * (4 if room.room_type == "Suite" else 2) for room in suggestions[0]
    )
    assert total_capacity_first >= 5


def test_allocator_returns_empty_when_impossible():
    inventory = [
        AvailabilityRoom(
            room_category="Standard",
            room_type="Queen",
            meal_plans=["Breakfast"],
            max_occupancy=2,
            available_rooms=1,
        )
    ]

    suggestions = RoomAllocationEngine().suggest(guests=5, inventory=inventory)
    assert suggestions == []
