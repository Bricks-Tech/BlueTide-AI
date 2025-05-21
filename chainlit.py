import chainlit as cl
import json
import os
import sys
import re # Using standard 're' module for regex

# Import your agents - adjust paths if your structure is different
from Agents.onboarding_agent import OnboardingAgent
from Agents.career_coach_agent import CareerCoach # Assuming CareerCoach is in Agents/career_coach.py

# Import your prompts and helpers
from prompts import (
    ONBOARDING_AGENT_SYSTEM_PROMPT, ONBOARDING_AGENT_INSTRUCTIONS,
    CAREER_COACH_SYSTEM_PROMPT, CAREER_COACH_INSTRUCTIONS
)
from helpers import create_client, create_thread, contains_json_block # contains_json_block is imported from helpers

# Helper function for JSON extraction with heading (can be in helpers.py or here)
# This function is used by handle_agent_response if the agent's chat method didn't
# already parse and return the JSON directly in `chat_result['data']`.
def extract_json_block_with_heading_and_fences(agent_output: str):
    """
    Extracts the first JSON block preceded by a markdown heading and fenced by ```json ... ```.
    Designed for the CareerCoach's milestone output format.
    """
    pattern = re.compile(
        r"###\s*(?P<heading>[^\n]+)\s*\n"   # Capture heading
        r"```json\s*\n"                     # Match ```json and newline
        r"(?P<json_string>\{[\s\S]*?\})\s*\n" # Capture JSON string (non-greedy, any char)
        r"```",                             # Match closing ```
        re.DOTALL | re.MULTILINE
    )
    match = pattern.search(agent_output)
    if match:
        heading = match.group("heading").strip()
        json_string = match.group("json_string")
        try:
            parsed_json = json.loads(json_string)
            return {"heading": heading, "data": parsed_json}
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error in extract_json_block_with_heading_and_fences: {e}")
            return None
    return None

# Global client and thread initialization (will be used by both agents for a single conversation thread)
OPENAI_CLIENT = create_client()
# Create the thread *once* at the very beginning of the application's lifecycle
# In a multi-user production Chainlit app, you would typically create this inside @cl.on_chat_start
# and store it in cl.user_session for a unique thread per user.
# For this example, we'll keep it global as per the user's implicit setup.
SHARED_THREAD_ID = create_thread(OPENAI_CLIENT=OPENAI_CLIENT)

@cl.on_chat_start
async def on_chat_start():
    # Initialize both agents with the SAME shared thread ID
    onboarding_agent = OnboardingAgent(
        thread_id=SHARED_THREAD_ID # Pass the shared thread ID
    )
    career_coach = CareerCoach(
        thread_id=SHARED_THREAD_ID # Pass the shared thread ID
    )

    # Store both agents and the state variable in the user session
    cl.user_session.set("onboarding_agent", onboarding_agent)
    cl.user_session.set("career_coach", career_coach)
    cl.user_session.set("onboarding_complete", False) # Initial state: onboarding not complete

    print(f"Chat session started. Shared Thread ID: {SHARED_THREAD_ID}")
    print("Onboarding Agent and Career Coach initialized.")

    # Start the conversation with the Onboarding Agent
    initial_chat_result = onboarding_agent.chat("Hello, I'm ready to start my career onboarding.")
    # Handle the initial response from the onboarding agent
    await handle_agent_response(initial_chat_result, agent_type="onboarding")


async def handle_agent_response(chat_result, agent_type):
    """
    Helper function to process and display agent responses based on their status and content.
    Handles JSON extraction if present in the message string.
    """
    message_content = chat_result["message"]
    extracted_data = chat_result.get("data") # Data returned by agent's chat method if parsed

    if chat_result["status"] == "continue":
        await cl.Message(content=message_content).send()

    elif chat_result["status"] == "success":
        # Display the agent's main message
        message_to_display = message_content

        if extracted_data and isinstance(extracted_data, dict):
            # If the agent's chat method already parsed and returned data
            await cl.Message(
                content=f"{message_to_display}\n\n"
                        f"**Structured Data:**\n```json\n{json.dumps(extracted_data, indent=2)}\n```"
            ).send()
            print(f"Agent ({agent_type}) success with extracted data.")
        else:
            # If agent's chat method signaled success but didn't return specific 'data' field
            # Check the message content itself for potential JSON (e.g., from CareerCoach's milestones)
            structured_data_from_message = extract_json_block_with_heading_and_fences(message_content)
            if structured_data_from_message:
                # Remove the JSON part from the message content for display
                text_part = message_content.split('```json')[0].strip()
                await cl.Message(
                    content=f"**Agent ({agent_type}) says:** {text_part}\n\n"
                            f"**Extracted Data ({structured_data_from_message['heading']}):**\n```json\n{json.dumps(structured_data_from_message['data'], indent=2)}\n```"
                ).send()
                print(f"Agent ({agent_type}) success: Detected and parsed JSON block under heading: {structured_data_from_message['heading']}")
                # If it's a milestone plan, you can do further processing here (e.g., save to DB)
                if "milestones" in structured_data_from_message['data']:
                    print("This is a milestone plan! Update the user's dashboard (placeholder).")
                    # save_milestones_to_db(user_id, structured_data_from_message['data'])
            else:
                await cl.Message(content=message_content).send() # No structured data, just a text message
                print(f"Agent ({agent_type}) success: Just a regular message.")

        # --- Transition Logic (only after onboarding success) ---
        if agent_type == "onboarding" and chat_result["conversation_ended"]:
            print("Onboarding complete! Transitioning to Career Coach.")
            cl.user_session.set("onboarding_complete", True)

            # Retrieve onboarding data for the Career Coach's initial context
            user_onboarding_data = extracted_data # Get data directly from success result
            cl.user_session.set("user_onboarding_data", user_onboarding_data)

            # Get the CareerCoach instance
            career_coach = cl.user_session.get("career_coach")

            await cl.Message(
                content="***Great! Your onboarding is complete. Now, let's move on to personalized career guidance.***\n\n"
                        "I am your Career Guidance Coach. To start, I will suggest some career paths based on your profile."
            ).send()

            # Send an initial message to the Career Coach with the onboarding data
            # This primes the CareerCoach with the user's profile context for its first task.
            initial_coach_message = f"User has completed onboarding. Their data is: {json.dumps(user_onboarding_data)}. Please suggest 3 career paths based on this data, as per your instructions."
            coach_initial_response = career_coach.chat(initial_coach_message)
            await handle_agent_response(coach_initial_response, agent_type="career_coach")


    elif chat_result["status"] == "error":
        await cl.Message(
            content=f"An error occurred during {agent_type} phase: {message_content}",
            # For debugging, you might include the raw response:
            # content=f"An error occurred: {message_content}\nRaw response: {chat_result.get('raw_response', 'N/A')}"
        ).send()
        print(f"Error during {agent_type} phase: {message_content}")


@cl.on_message
async def on_message(msg: cl.Message):
    onboarding_complete = cl.user_session.get("onboarding_complete")

    if not onboarding_complete:
        # If onboarding is not complete, send messages to the Onboarding Agent
        current_agent = cl.user_session.get("onboarding_agent")
        chat_result = current_agent.chat(msg.content)
        await handle_agent_response(chat_result, agent_type="onboarding")
    else:
        # If onboarding is complete, use the Career Coach
        current_agent = cl.user_session.get("career_coach")

        # The user's message is passed directly to the career coach
        chat_result = current_agent.chat(msg.content)

        # Handle the career coach's response
        await handle_agent_response(chat_result, agent_type="career_coach")