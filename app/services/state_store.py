from __future__ import annotations

import time
from dataclasses import dataclass

from app.models.reservation import ReservationState


@dataclass
class SessionState:
    reservation: ReservationState
    updated_at: float


class InMemoryStateStore:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._ttl_seconds = ttl_seconds
        self._store: dict[str, SessionState] = {}

    def get_or_create(self, session_id: str) -> ReservationState:
        self._cleanup()
        session = self._store.get(session_id)
        if session:
            return session.reservation

        reservation = ReservationState()
        self._store[session_id] = SessionState(reservation=reservation, updated_at=time.time())
        return reservation

    def save(self, session_id: str, reservation: ReservationState) -> ReservationState:
        self._store[session_id] = SessionState(reservation=reservation, updated_at=time.time())
        return reservation

    def _cleanup(self) -> None:
        now = time.time()
        expired = [key for key, value in self._store.items() if now - value.updated_at > self._ttl_seconds]
        for key in expired:
            self._store.pop(key, None)
