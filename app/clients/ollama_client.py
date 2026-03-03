from __future__ import annotations

import json
from typing import Any

from ollama import Client
from pydantic import ValidationError

from app.models.reservation import ReservationPatch


EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "check_in": {"type": ["string", "null"], "format": "date"},
        "check_out": {"type": ["string", "null"], "format": "date"},
        "guests": {"type": ["integer", "null"]},
        "name": {"type": ["string", "null"]},
        "email": {"type": ["string", "null"]},
        "phone": {"type": ["string", "null"]},
        "rooms": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {
                    "room_category": {"type": "string"},
                    "room_type": {"type": "string"},
                    "meal_plan": {"type": ["string", "null"]},
                    "room_count": {"type": "integer"},
                },
                "required": ["room_category", "room_type", "room_count"],
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


class OllamaExtractionClient:
    def __init__(self, model: str, base_url: str) -> None:
        self.model = model
        self.client = Client(host=base_url)

    def extract_patch(self, user_message: str, current_state: dict[str, Any], available_options: list[dict[str, Any]]) -> ReservationPatch:
        system_prompt = (
            "You extract reservation updates as STRICT JSON only. "
            "Never invent room options. Use only provided inventory options. "
            "For unknown fields return null."
        )
        user_prompt = {
            "message": user_message,
            "current_reservation": current_state,
            "inventory_options": available_options,
            "required_json_schema": EXTRACTION_SCHEMA,
            "rules": [
                "Output raw JSON object only, no markdown.",
                "Do not overwrite existing values with null unless user explicitly cancels that field.",
                "Rooms must exactly match inventory_options names.",
            ],
        }

        response = self.client.chat(
            model=self.model,
            format="json",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt)},
            ],
            options={"temperature": 0},
        )
        raw = response["message"]["content"]
        return self._parse_patch(raw)

    def _parse_patch(self, raw: str) -> ReservationPatch:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = self._best_effort_json(raw)

        try:
            return ReservationPatch.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"LLM returned invalid reservation patch: {exc}") from exc

    @staticmethod
    def _best_effort_json(raw: str) -> dict[str, Any]:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Unable to recover JSON from model output")
        return json.loads(raw[start : end + 1])
