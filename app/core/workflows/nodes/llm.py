from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from config.prompts import APPOINTMENT_PROMPT, CONTACT_PROMPT, HANDOFF_PROMPT
from config.settings import settings
import logging
import re


class LLMNode:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=settings.google_api_key,
            temperature=0.3
        )
        self.generic = ChatPromptTemplate.from_template("{prompt}")

    async def __call__(self, state):
        # Skip LLM if intent is appointment, FAQ, or contact info
        if state.get("intent") == "appointment":
            return state
        if state.get("intent") == "faqs":
            return state
        if state.get("intent") == "contact_info":
            # Double check - if this is a location query that somehow reached here, skip LLM
            message = state.get("user_message", "").lower()
            location_keywords = ["location", "address", "where", "office", "clinic", "directions"]
            if any(keyword in message for keyword in location_keywords):
                logging.info(f"LLM node detected location query that wasn't handled: {message}")
                # Return without modifying state so it can be handled by the static info node
                return state

        # Safety: Override if an old intent like "intake" is still around
        if state.get("intent") == "intake":
            state["intent"] = "appointment"

        # Define available prompt mappings
        prompt_map = {
            "handoff": HANDOFF_PROMPT,
        }

        # Use the mapped prompt or fallback
        prompt = prompt_map.get(state.get("intent"))

        if not prompt:
            # Check one more time if this might be a location question before defaulting
            message = state.get("user_message", "").lower()
            if "location" in message or "address" in message or "where" in message:
                logging.info(f"LLM detected unhandled location query: {message}")
                state["intent"] = "contact_info"
                return state
                
            state["final_response"] = (
                "🤖 Sorry, I'm not sure how to handle that request right now."
            )
            return state

        chain = self.generic | self.llm
        out = await chain.ainvoke({"prompt": prompt})

        # Handle response structure from LLM
        state["final_response"] = out[0] if isinstance(out, list) else out
        return state
