from __future__ import annotations

from flask import Flask, render_template


def create_app() -> Flask:
    from app.agents_langchain import LangChainHotelAgent
    from app.clients.hotel_api_client import HotelAPIClient
    from app.clients.ollama_client import OllamaExtractionClient
    from app.config import settings
    from app.routes import build_blueprint
    from app.services.reservation_service import ReservationService
    from app.services.room_allocator import RoomAllocationEngine
    from app.services.state_store import InMemoryStateStore

    app = Flask(__name__)

    state_store = InMemoryStateStore(ttl_seconds=settings.state_ttl_seconds)
    hotel_client = HotelAPIClient(settings.hotel_api_base_url, settings.hotel_api_key)
    llm_client = OllamaExtractionClient(settings.ollama_model, settings.ollama_base_url)
    allocator = RoomAllocationEngine()
    chat_agent = LangChainHotelAgent(settings.ollama_model, settings.ollama_base_url)

    service = ReservationService(state_store, hotel_client, llm_client, allocator, chat_agent=chat_agent)
    app.register_blueprint(build_blueprint(service))

    @app.get("/ui")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
