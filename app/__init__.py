from __future__ import annotations

from flask import Flask

from app.clients.hotel_api_client import HotelAPIClient
from app.clients.ollama_client import OllamaExtractionClient
from app.config import settings
from app.routes import build_blueprint
from app.services.reservation_service import ReservationService
from app.services.room_allocator import RoomAllocationEngine
from app.services.state_store import InMemoryStateStore


def create_app() -> Flask:
    app = Flask(__name__)

    state_store = InMemoryStateStore(ttl_seconds=settings.state_ttl_seconds)
    hotel_client = HotelAPIClient(settings.hotel_api_base_url, settings.hotel_api_key)
    llm_client = OllamaExtractionClient(settings.ollama_model, settings.ollama_base_url)
    allocator = RoomAllocationEngine()

    service = ReservationService(state_store, hotel_client, llm_client, allocator)
    app.register_blueprint(build_blueprint(service))

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
