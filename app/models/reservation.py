from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ReservationStatus(str, Enum):
    draft = "draft"
    confirmed = "confirmed"


class RoomSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_category: str
    room_type: str
    meal_plan: Optional[str] = None
    room_count: int = Field(ge=1)


class ReservationState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_in: Optional[date] = None
    check_out: Optional[date] = None
    guests: Optional[int] = Field(default=None, ge=1)
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    rooms: list[RoomSelection] = Field(default_factory=list)
    status: ReservationStatus = ReservationStatus.draft

    @model_validator(mode="after")
    def validate_dates(self) -> "ReservationState":
        if self.check_in and self.check_out and self.check_in >= self.check_out:
            raise ValueError("check_out must be after check_in")
        return self


class ReservationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_in: Optional[date] = None
    check_out: Optional[date] = None
    guests: Optional[int] = Field(default=None, ge=1)
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    rooms: Optional[list[RoomSelection]] = None


class AvailabilityRoom(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_category: str
    room_type: str
    meal_plans: list[str]
    max_occupancy: int = Field(ge=1)
    available_rooms: int = Field(ge=0)


class AvailabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_in: date
    check_out: date
    inventory: list[AvailabilityRoom]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    message: str


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    reservation: ReservationState
    reply: str
    suggestions: list[list[RoomSelection]] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class RateLineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_category: str
    room_type: str
    meal_plan: Optional[str] = None
    room_count: int = Field(ge=1)
    nightly_rate: float = Field(ge=0)
    nights: int = Field(ge=1)
    total: float = Field(ge=0)


class ReservationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    check_in: date
    check_out: date
    guests: int = Field(ge=1)
    nights: int = Field(ge=1)
    currency: str
    line_items: list[RateLineItem]
    subtotal: float = Field(ge=0)
    taxes: float = Field(ge=0)
    total: float = Field(ge=0)


class ConfirmResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation: ReservationState
    receipt: ReservationReceipt


MANDATORY_FIELDS = ("check_in", "check_out", "guests", "name", "email", "phone")
