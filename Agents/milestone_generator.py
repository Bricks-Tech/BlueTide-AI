import openai
import json
from dotenv import load_dotenv
import os
import sys
import re # Using standard 're' module for regex

# Add the parent directory to the Python path for imports like 'prompts' and 'helpers'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from prompts import MILESTONE_GENERATOR_INSTRUCTIONS, MILESTONE_GENERATOR_SYSTEM_PROMPT
from helpers import create_client, create_assistant, call_openAI, contains_json_block


class MilestoneGeneratorAgent:
    def __init__(self, thread_id: str):
        load_dotenv() # Ensure .env is loaded
        self.OPENAI_CLIENT = create_client()
        self.assistant_id = create_assistant(
            name="Milestone Generator",
            instructions=MILESTONE_GENERATOR_SYSTEM_PROMPT,
            OPENAI_CLIENT=self.OPENAI_CLIENT
        )
        self.thread_id = thread_id # The shared conversational thread ID

    def chat(self, user_input: str):
        response = call_openAI(
            thread_id=self.thread_id,
            assistant_id=self.assistant_id,
            user_input=user_input,
            instructions=MILESTONE_GENERATOR_INSTRUCTIONS, # Use specific instructions for the run
            OPENAI_CLIENT=self.OPENAI_CLIENT
        )

        json_block_pattern = re.compile(
            r"```json\s*\n"                    
            r"(?P<json_string>\{[\s\S]*?\})\s*\n" 
            r"```",                             
            re.DOTALL | re.MULTILINE
        )
        json_match = json_block_pattern.search(response)

        if json_match:
            json_string = json_match.group("json_string")
            try:
                milestone_data = json.loads(json_string)
                
                # Determine status based on the type of output
                status_message = "Milestones generated successfully!" if milestone_data.get("type") == "initial_generation" else "Milestone regenerated successfully!"

                return {
                    "status": "success",
                    "message": status_message,
                    "data": milestone_data, # Contains either full milestones or regenerated single milestone
                    "conversation_ended": False # The agent's task is done, but the overall conversation continues
                }
            except json.JSONDecodeError as e:
                return {
                    "status": "error",
                    "message": f"Milestone Generator: Failed to decode JSON output: {e}. Raw JSON part: {json_string[:200]}...",
                    "raw_response": response,
                    "conversation_ended": False
                }
        else:
            # If no structured JSON is found, it's an unexpected response
            return {
                "status": "error", # If it doesn't return JSON, it's an error in this agent's contract
                "message": f"Milestone Generator: Expected JSON output but received conversational response: {response}",
                "raw_response": response,
                "conversation_ended": False
            }
