import openai
import json
from dotenv import load_dotenv
import os
import sys
import re # Using standard 're' module for regex

# Add the parent directory to the Python path for imports like 'prompts' and 'helpers'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from prompts import SKILL_GAP_ANALYZER_INSTRUCTIONS, SKILL_GAP_ANALYZER_SYSTEM_PROMPT
from helpers import create_client, create_assistant, call_openAI, contains_json_block


class SkillGapAnalyzerAgent:
    def __init__(self, thread_id: str):
        load_dotenv() # Ensure .env is loaded
        self.OPENAI_CLIENT = create_client()
        self.assistant_id = create_assistant(
            name="Skill Gap Analyzer",
            instructions=SKILL_GAP_ANALYZER_SYSTEM_PROMPT,
            OPENAI_CLIENT=self.OPENAI_CLIENT
        )
        self.thread_id = thread_id # The shared conversational thread ID

    def chat(self, user_input: str):
        """
        Processes a user message related to skill gap analysis.
        The user_input should typically contain the user's current skills
        and the target career path requirements.
        """
        response = call_openAI(
            thread_id=self.thread_id,
            assistant_id=self.assistant_id,
            user_input=user_input, # This input should convey relevant context for analysis
            instructions=SKILL_GAP_ANALYZER_INSTRUCTIONS,
            OPENAI_CLIENT=self.OPENAI_CLIENT
        )

        # Attempt to extract the structured JSON output
        # It expects a heading "### Skill Gap Analysis" followed by ```json ... ```
        json_block_pattern = re.compile(
            r"###\s*Skill Gap Analysis\s*\n"   # Specific heading
            r"```json\s*\n"                     # Match ```json and newline
            r"(?P<json_string>\{[\s\S]*?\})\s*\n" # Capture JSON string (non-greedy)
            r"```",                             # Match closing ```
            re.DOTALL | re.MULTILINE
        )
        json_match = json_block_pattern.search(response)

        if json_match:
            json_string = json_match.group("json_string")
            try:
                skill_gap_analysis_data = json.loads(json_string)
                return {
                    "status": "success",
                    "message": "Skill gap analysis complete and data extracted.",
                    "data": skill_gap_analysis_data,
                    "conversation_ended": False # Analysis might lead to further discussion
                }
            except json.JSONDecodeError as e:
                return {
                    "status": "error",
                    "message": f"Skill Gap Analyzer: Failed to decode JSON output: {e}. Raw JSON part: {json_string[:200]}...",
                    "raw_response": response,
                    "conversation_ended": False
                }
        else:
            # If no structured JSON is found, it's a conversational response or an error
            return {
                "status": "continue",
                "message": response,
                "conversation_ended": False
            }