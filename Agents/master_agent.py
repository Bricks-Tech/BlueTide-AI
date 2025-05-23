import openai
import json
from dotenv import load_dotenv
import os
import sys
import re

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from prompts import MASTER_AI_AGENT_SYSTEM_PROMPT, MASTER_AI_AGENT_INSTRUCTIONS
from helpers import create_client, create_assistant, call_openAI, get_current_user_state

# Import all specialist agent classes
from career_coach_agent import CareerCoach
from check_agent import ReflectionAndCheckInAgent # Assuming this is ReflectionAndCheckInAgent
from milestone_generator import MilestoneGeneratorAgent
from onboarding_agent import OnboardingAgent
from skill_gap_analyzer_agent import SkillGapAnalyzerAgent

class MasterAIAgent:
    def __init__(self, thread_id: str):
        load_dotenv()
        self.OPENAI_CLIENT = create_client()
        self.assistant_id = create_assistant(
            name="Master AI Agent Orchestrator",
            instructions=MASTER_AI_AGENT_SYSTEM_PROMPT,
            OPENAI_CLIENT=self.OPENAI_CLIENT
        )
        self.thread_id = thread_id

        # Store agents in a dictionary for easier dynamic calling
        self.agents = {
            "onboarding_agent": OnboardingAgent(thread_id=self.thread_id),
            "career_coach": CareerCoach(thread_id=self.thread_id),
            "milestone_generator": MilestoneGeneratorAgent(thread_id=self.thread_id),
            "skill_gap_analyzer": SkillGapAnalyzerAgent(thread_id=self.thread_id),
            "reflection_check_in_agent": ReflectionAndCheckInAgent(thread_id=self.thread_id),
            # Add other agents here if any
        }
        self.expected_decision_keys = ["action", "agent_to_call", "message_for_agent", "direct_response_message", "transition_phase_to"]


    def _get_master_decision(self, user_input: str) -> dict:
        """
        Internal method to get the routing decision from the Master AI Agent LLM.
        Returns a dictionary with "status", "decision" (if success), or "message" (if error).
        """
        try:
            context_str = get_current_user_state(thread_id=self.thread_id)
        except Exception as e:
            print(f"Master Agent: Error getting current user state: {e}")
            return {
                "status": "error",
                "message": "Master Agent failed to retrieve user context. Cannot proceed.",
                "agent_type": "master_ai_agent",
                "conversation_ended": True
            }

        full_message_for_master = (
            f"User's Latest Message: '{user_input}'\n\n"
            f"Current System Context:\n{context_str}\n\n"
            "Based on the user's message and the current system context, "
            "determine the appropriate action and output the decision as a JSON object "
            "according to the provided schema in MASTER_AI_AGENT_INSTRUCTIONS."
        )

        response_text = call_openAI(
            thread_id=self.thread_id,
            assistant_id=self.assistant_id,
            user_input=full_message_for_master,
            instructions=MASTER_AI_AGENT_INSTRUCTIONS,
            OPENAI_CLIENT=self.OPENAI_CLIENT
        )

        json_block_pattern = re.compile(r"```json\s*\n(?P<json_string>\{[\s\S]*?\})\s*\n```", re.DOTALL | re.MULTILINE)
        json_match = json_block_pattern.search(response_text)
        
        raw_json_string = None
        if json_match:
            raw_json_string = json_match.group("json_string")
        else: # Fallback: try to parse the whole response if no markdown block
            raw_json_string = response_text.strip()
            if not (raw_json_string.startswith('{') and raw_json_string.endswith('}')): # Basic check if it could be JSON
                print(f"Master Agent: LLM response is not a JSON block nor a direct JSON object. Response: {response_text}")
                return {"status": "error", "message": "Master Agent LLM response format error (no JSON).", "agent_type": "master_ai_agent", "conversation_ended": False}

        try:
            decision_data = json.loads(raw_json_string)
            # Validate core structure
            if not all(k in decision_data for k in self.expected_decision_keys):
                # If some expected keys are missing, fill them with None if 'action' is present,
                # otherwise, it's a malformed essential structure.
                if "action" in decision_data:
                    print(f"Master Agent: LLM decision JSON missing some optional fields. Filling with None. Original: {raw_json_string}")
                    for k in self.expected_decision_keys:
                        decision_data.setdefault(k, None)
                else:
                    raise ValueError("Master Agent JSON from LLM missing 'action' or other core fields.")
            
            return {"status": "success", "decision": decision_data, "agent_type": "master_ai_agent"}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Master Agent: Failed to decode/validate JSON from LLM: {e}. JSON string: {raw_json_string[:300]}")
            return {"status": "error", "message": "Master Agent LLM response processing error.", "agent_type": "master_ai_agent", "conversation_ended": False}


    def chat(self, user_input: str) -> dict:
        """
        Processes user input, gets a decision from Master LLM, calls a specialist agent if needed,
        and returns a consolidated response for the user/orchestrator.
        """
        master_decision_result = self._get_master_decision(user_input)

        if master_decision_result["status"] == "error":
            return master_decision_result # Propagate error (already a dict)

        decision_data = master_decision_result["decision"]
        
        final_message_to_user = ""
        final_agent_type = decision_data.get("agent_to_call") or "master_ai_agent"
        conversation_ended = False
        output_json_from_specialist = None
        action_taken_by_master = decision_data.get("action")

        if action_taken_by_master == "call_agent":
            agent_name_to_call = decision_data.get("agent_to_call")
            message_for_specialist = decision_data.get("message_for_agent", user_input) # Fallback to user_input if no specific message

            if agent_name_to_call and agent_name_to_call in self.agents:
                specialist_agent = self.agents[agent_name_to_call]
                print(f"Master Agent: Routing to {agent_name_to_call} with message: '{message_for_specialist}'")
                try:
                    # Assuming specialist_agent.chat() returns a dict as specified
                    specialist_response = specialist_agent.chat(user_input=message_for_specialist)

                    final_message_to_user = specialist_response.get("message", f"The {agent_name_to_call.replace('_', ' ')} processed your request but provided no textual response.")
                    output_json_from_specialist = specialist_response.get("output_json")
                    conversation_ended = specialist_response.get("conversation_ended", False)
                    final_agent_type = specialist_response.get("agent_type", agent_name_to_call) # Prefer specialist's self-reported type

                    if specialist_response.get("status") == "error":
                        print(f"Master Agent: Specialist agent {agent_name_to_call} reported an error: {final_message_to_user}")
                        # final_message_to_user might already be an error message.
                        # Could prepend: "There was an issue with the {agent_name_to_call.replace('_', ' ')}: "
                except Exception as e:
                    print(f"Master Agent: Exception occurred while calling {agent_name_to_call}.chat(): {e}")
                    final_message_to_user = f"I'm sorry, an unexpected error occurred while consulting the {agent_name_to_call.replace('_', ' ')}."
                    final_agent_type = "master_ai_agent" # Error handled at Master level
                    conversation_ended = False # Or True if it's a critical failure
            else:
                print(f"Master Agent: Decision to call unknown or unspecified agent: '{agent_name_to_call}'")
                final_message_to_user = "I'm not sure how to handle that request due to an internal routing issue. Please try rephrasing."
                final_agent_type = "master_ai_agent"

        elif action_taken_by_master == "respond_directly":
            final_message_to_user = decision_data.get("direct_response_message", "I'm ready to help, but I don't have a specific response for that.")
            final_agent_type = "master_ai_agent"
            # Potentially set conversation_ended if the direct response is a concluding remark.
            # This could be part of the Master LLM's decision: decision_data.get("conversation_ended_by_master", False)

        else:
            print(f"Master Agent: Unknown action '{action_taken_by_master}' in decision from LLM.")
            final_message_to_user = "I'm having a bit of trouble with the internal process. Could you please try your request again?"
            final_agent_type = "master_ai_agent"

        # Prepare the final structured response
        response_payload = {
            "status": "success", # Assuming the Master Agent's orchestration part succeeded
            "agent_type": final_agent_type,
            "message": final_message_to_user,
            "output_json": output_json_from_specialist, # This could be a string or a dict
            "conversation_ended": conversation_ended,
            "master_decision_details": decision_data # For logging or external state updates (e.g., transition_phase_to)
        }
        return response_payload