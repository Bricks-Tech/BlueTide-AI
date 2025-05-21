import openai
import json
from dotenv import load_dotenv
import os
import sys
from prompts import CAREER_COACH_INSTRUCTIONS, CAREER_COACH_SYSTEM_PROMPT
from helpers import create_client, create_assistant, create_thread, call_openAI , contains_json_block
import regex as re
# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class CareerCoach: 
    def __init__(self,thread_id):
        self.OPENAI_CLIENT = create_client()
        self.assistant_id = create_assistant(
            name="Career Coach",
            instructions=CAREER_COACH_SYSTEM_PROMPT,
            OPENAI_CLIENT=self.OPENAI_CLIENT
        )
        self.thread_id = thread_id

    def create_thread(self):
        thread = create_thread(self.OPENAI_CLIENT)
        return thread.id
    
    def chat(self,message):
        response = call_openAI(
            assistant_id= self.assistant_id, 
            user_input= message,
            instructions=CAREER_COACH_INSTRUCTIONS, 
            OPENAI_CLIENT= self.OPENAI_CLIENT , 
            thread_id=self.thread_id
        )

        if contains_json_block (response_string=response):
            json_match = re.search(r"```json\s*(\{.*\})\s*```", response, re.DOTALL)
            if not json_match:
                # Fallback if markdown fence is not used but plain JSON is present
                # This regex is more general and tries to find any JSON-like object
                json_match = re.search(r"(\{[\s\S]*?\})", response, re.DOTALL)
                if not json_match:
                    # If JSON still isn't found, report an error but acknowledge 'DONE'
                    return {
                        "status": "error",
                        "message": "Milestones done, but JSON data not found in the assistant's output. Please check the assistant's response format.",
                        "raw_response": response,
                        "conversation_ended": True
                    }
            json_string = json_match.group(1)

            try:
                milestones = json.loads(json_string)
            except json.JSONDecodeError as e:
                return {
                    "status": "error",
                    "message": f"Failed to decode JSON from assistant's response: {e}. Raw JSON string: {json_string[:200]}...",
                    "raw_response": response,
                    "conversation_ended": True
                }
            
            filename = "user_milestones.json"
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(milestones, f, indent=4, ensure_ascii=False)
                
                return {
                    "status": "success",
                    "message": f"Your milestones have been successfully saved to **{filename}**.",
                    "data": milestones,
                    "conversation_ended": True
                }
            except IOError as e:
                return {
                    "status": "error",
                    "message": f"Failed to save data to file {filename}: {e}",
                    "raw_response": response,
                    "conversation_ended": True
                }
        else:
          
            return {
                "status": "continue",
                "message": response, 
                "conversation_ended": False
            }


