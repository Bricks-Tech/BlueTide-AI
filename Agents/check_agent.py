import openai
import json
from dotenv import load_dotenv
import os
import sys
import re # Using standard 're' module for regex

# Add the parent directory to the Python path for imports like 'prompts' and 'helpers'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from prompts import REFLECTION_CHECK_IN_INSTRUCTIONS, REFLECTION_CHECK_IN_SYSTEM_PROMPT
from helpers import create_client, create_assistant, call_openAI


class ReflectionAndCheckInAgent:
    def __init__(self, thread_id: str):
        load_dotenv() # Ensure .env is loaded
        self.OPENAI_CLIENT = create_client()
        self.assistant_id = create_assistant(
            name="Reflection & Check-In",
            instructions=REFLECTION_CHECK_IN_SYSTEM_PROMPT,
            OPENAI_CLIENT=self.OPENAI_CLIENT
        )
        self.thread_id = thread_id # The shared conversational thread ID

    def chat(self, user_input: str):
        """
        Processes a message for reflection and check-in.
        The user_input might be a direct user response or a system-triggered prompt.
        """
        response = call_openAI(
            thread_id=self.thread_id,
            assistant_id=self.assistant_id,
            user_input=user_input, # This input will be the basis for the check-in
            instructions=REFLECTION_CHECK_IN_INSTRUCTIONS,
            OPENAI_CLIENT=self.OPENAI_CLIENT
        )

        # The Reflection & Check-In Agent primarily provides conversational output.
        # No specific JSON extraction is expected unless defined in future prompts.
        return {
            "status": "continue", # Usually continues the conversation
            "message": response,
            "conversation_ended": False
        }