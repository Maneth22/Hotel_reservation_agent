from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.models.reservation import ChatRequest, ReservationPatch
from app.services.reservation_service import ReservationService


def build_blueprint(service: ReservationService) -> Blueprint:
    bp = Blueprint("api", __name__)

    @bp.post("/chat")
    def chat():
        try:
            payload = ChatRequest.model_validate(request.get_json(force=True))
            response = service.update_draft_from_chat(payload.session_id, payload.message)
            return jsonify(response.model_dump(mode="json"))
        except (ValidationError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.get("/availability")
    def availability():
        try:
            check_in = date.fromisoformat(request.args["check_in"])
            check_out = date.fromisoformat(request.args["check_out"])
            response = service.get_availability(check_in, check_out)
            return jsonify(response.model_dump(mode="json"))
        except (KeyError, ValueError, ValidationError) as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.post("/reservation/draft")
    def update_draft():
        try:
            body = request.get_json(force=True)
            session_id = body["session_id"]
            patch = ReservationPatch.model_validate(body.get("reservation", {}))
            reservation = service.update_draft(session_id, patch)
            return jsonify(reservation.model_dump(mode="json"))
        except (KeyError, ValidationError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.post("/reservation/confirm")
    def confirm():
        try:
            session_id = request.get_json(force=True)["session_id"]
            reservation = service.confirm(session_id)
            return jsonify(reservation.model_dump(mode="json"))
        except (KeyError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    return bp
