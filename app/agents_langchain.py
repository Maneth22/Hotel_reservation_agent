from __future__ import annotations

import json
from typing import Any


class LangChainHotelAgent:
    """Produces a final conversational response using LangChain + Ollama."""

    def __init__(self, model: str, base_url: str) -> None:
        self.model = model
        self.base_url = base_url

    def generate_reply(
        self,
        user_message: str,
        reservation: dict[str, Any],
        suggestions: list[list[dict[str, Any]]],
        availability_inventory: list[dict[str, Any]],
        missing_fields: list[str],
    ) -> str:
        try:
            from langchain.agents import AgentExecutor, create_tool_calling_agent
            from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
            from langchain_core.tools import tool
            from langchain_ollama import ChatOllama
        except Exception:
            return self._fallback_reply(reservation, missing_fields)

        reservation_json = json.dumps(reservation)
        suggestions_json = json.dumps(suggestions)
        availability_json = json.dumps(availability_inventory)

        @tool
        def get_reservation() -> str:
            """Get current reservation profile containing guest and contact information."""
            return reservation_json

        @tool
        def get_inventory() -> str:
            """Get available room inventory from hotel system."""
            return availability_json

        @tool
        def get_room_suggestions() -> str:
            """Get computed room combinations that fit the guest count."""
            return suggestions_json

        @tool
        def analyze_capacity() -> str:
            """Analyze how suggested room combinations match the guest count."""
            guests = reservation.get("guests")
            if not guests:
                return "Guest count is not available yet."
            if not suggestions:
                return f"No feasible room combination currently fits {guests} guests."

            occupancy_map = {
                (room["room_category"], room["room_type"]): room["max_occupancy"]
                for room in availability_inventory
            }
            lines = []
            for idx, combo in enumerate(suggestions, start=1):
                capacity = 0
                for selection in combo:
                    key = (selection["room_category"], selection["room_type"])
                    capacity += occupancy_map.get(key, 0) * selection["room_count"]
                lines.append(f"Option {idx}: capacity {capacity} for {guests} guests")
            return "\n".join(lines)

        tools = [get_reservation, get_inventory, get_room_suggestions, analyze_capacity]
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a hotel reservation assistant. Always ground your answer on tool output only. "
                    "Summarize available room options, explain capacity fit for guest count, "
                    "confirm captured user identity/contact details, and ask for missing fields: "
                    f"{missing_fields}",
                ),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        try:
            llm = ChatOllama(model=self.model, base_url=self.base_url, temperature=0)
            agent = create_tool_calling_agent(llm, tools, prompt)
            executor = AgentExecutor(agent=agent, tools=tools, verbose=False)
            result = executor.invoke({"input": user_message})
            return str(result["output"])
        except Exception:
            return self._fallback_reply(reservation, missing_fields)

    @staticmethod
    def _fallback_reply(reservation: dict[str, Any], missing_fields: list[str]) -> str:
        name = reservation.get("name") or "guest"
        if missing_fields:
            return f"Draft updated for {name}. Please provide: {', '.join(missing_fields)}."
        return f"Draft updated for {name}. Room-fit analysis and options are ready for confirmation."
