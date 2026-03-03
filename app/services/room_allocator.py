from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from app.models.reservation import AvailabilityRoom, RoomSelection


@dataclass(frozen=True)
class AllocationCandidate:
    rooms: list[RoomSelection]
    total_capacity: int
    unused_capacity: int


class RoomAllocationEngine:
    def suggest(self, guests: int, inventory: list[AvailabilityRoom], top_k: int = 3) -> list[list[RoomSelection]]:
        if guests <= 0:
            raise ValueError("Guest count must be positive")

        max_capacity = sum(item.max_occupancy * item.available_rooms for item in inventory)
        if guests > max_capacity:
            return []

        ranges = [range(item.available_rooms + 1) for item in inventory]
        candidates: list[AllocationCandidate] = []

        for counts in product(*ranges):
            if not any(counts):
                continue
            capacity = sum(count * item.max_occupancy for count, item in zip(counts, inventory))
            if capacity < guests:
                continue
            unused = capacity - guests
            rooms: list[RoomSelection] = []
            for count, item in zip(counts, inventory):
                if count == 0:
                    continue
                rooms.append(
                    RoomSelection(
                        room_category=item.room_category,
                        room_type=item.room_type,
                        meal_plan=item.meal_plans[0] if item.meal_plans else None,
                        room_count=count,
                    )
                )
            candidates.append(AllocationCandidate(rooms=rooms, total_capacity=capacity, unused_capacity=unused))

        candidates.sort(key=lambda x: (x.unused_capacity, len(x.rooms), x.total_capacity))
        return [candidate.rooms for candidate in candidates[:top_k]]
