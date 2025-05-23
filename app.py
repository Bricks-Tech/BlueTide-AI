import chainlit as cl
import json
import os
import sys
import re

# Add the parent directory to the Python path to ensure imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import your agent classes
# Assuming OnboardingAgent is in Agents/onboarding_agent.py
# Assuming MilestoneGeneratorAgent is in Agents/milestone_generator_agent.py
# Assuming CareerCoach is in Agents/career_coach.py
from Agents.onboarding_agent import OnboardingAgent
from Agents.milestone_generator import MilestoneGeneratorAgent
from Agents.career_coach_agent import CareerCoach # This should be your actual CareerCoach class

# Import your prompts and helpers
from prompts import (
    ONBOARDING_AGENT_SYSTEM_PROMPT, ONBOARDING_AGENT_INSTRUCTIONS,
    CAREER_COACH_SYSTEM_PROMPT, CAREER_COACH_INSTRUCTIONS,
    MILESTONE_GENERATOR_SYSTEM_PROMPT, MILESTONE_GENERATOR_INSTRUCTIONS
)
from helpers import create_client, create_thread # create_assistant, call_openAI are used inside agents


# --- Global Client and Thread ---
OPENAI_CLIENT = create_client()
SHARED_THREAD_ID = create_thread(OPENAI_CLIENT=OPENAI_CLIENT)
print(f"Global SHARED_THREAD_ID created: {SHARED_THREAD_ID}")

# --- Agent Instances (initialized in on_chat_start) ---
onboarding_agent: OnboardingAgent = None
milestone_generator_agent: MilestoneGeneratorAgent = None
career_coach_agent: CareerCoach = None

# --- Chainlit Callbacks ---

@cl.on_chat_start
async def start():
    global onboarding_agent, milestone_generator_agent, career_coach_agent

    # Initialize agents with the shared thread ID
    onboarding_agent = OnboardingAgent(thread_id=SHARED_THREAD_ID)
    milestone_generator_agent = MilestoneGeneratorAgent(thread_id=SHARED_THREAD_ID)
    # CareerCoachAgent is initialized later, after data is gathered

    # Store agents and initial state in user session
    cl.user_session.set("onboarding_agent", onboarding_agent)
    cl.user_session.set("milestone_generator_agent", milestone_generator_agent)
    cl.user_session.set("current_stage", 'onboarding')
    cl.user_session.set("user_onboarding_data", {})
    cl.user_session.set("suggested_career_paths", [])
    cl.user_session.set("selected_career_path", "")
    cl.user_session.set("generated_milestones", {})

    await cl.Message(
        content="Hello! I'm your AI Career Assistant. Let's start by getting to know you.",
        author="System"
    ).send()
    
    # Send an initial message to the Onboarding Agent to kick off its process
    initial_onboarding_response = onboarding_agent.chat("Start onboarding.")
    await handle_agent_response(initial_onboarding_response, "Onboarding Agent")


@cl.on_message
async def handle_message(message: cl.Message):
    current_stage = cl.user_session.get("current_stage")
    
    if current_stage == 'onboarding':
        agent_response = cl.user_session.get("onboarding_agent").chat(message.content)
        await handle_agent_response(agent_response, "Onboarding Agent")

    elif current_stage == 'select_path':
        selected_path_input = message.content.strip()
        suggested_paths = cl.user_session.get("suggested_career_paths")
        
        # Simple validation for path selection
        if selected_path_input not in suggested_paths:
            await cl.Message(
                content="That doesn't seem to be one of the suggested paths. Please type the full name of the career path you'd like to pursue from the list above.",
                author="System"
            ).send()
            return # Stay in 'select_path' stage
        
        cl.user_session.set("selected_career_path", selected_path_input)
        
        await cl.Message(
            content=f"You've chosen **{selected_path_input}**! I'm now generating your personalized career milestones...",
            author="System"
        ).send()

        # Transition to generate_milestones stage
        cl.user_session.set("current_stage", 'generate_milestones')

        # Trigger MilestoneGeneratorAgent for initial milestone generation
        milestone_generator_agent = cl.user_session.get("milestone_generator_agent")
        user_onboarding_data = cl.user_session.get("user_onboarding_data")

        # Construct the input as expected by MILESTONE_GENERATOR_INSTRUCTIONS Scenario 2
        milestone_gen_request = {
            "career_path_name": selected_path_input,
            "user_onboarding_data": user_onboarding_data
        }
        milestone_gen_response = milestone_generator_agent.chat(f"Generate initial milestones: {json.dumps(milestone_gen_request)}")
        await handle_agent_response(milestone_gen_response, "Milestone Generator Agent")

    elif current_stage == 'coaching':
        # All subsequent messages go to the Career Coach
        career_coach_agent = cl.user_session.get("career_coach_agent")
        coach_response = career_coach_agent.chat(message.content)
        await handle_agent_response(coach_response, "Career Coach")
        
    else:
        await cl.Message(
            content="An unexpected stage was reached. Please restart the conversation.",
            author="Error"
        ).send()

# --- Helper to handle Agent responses and manage state transitions ---
async def handle_agent_response(agent_chat_result: dict, agent_name: str):
    current_stage = cl.user_session.get("current_stage")

    message_content = agent_chat_result.get("message", "No message provided.")
    extracted_data = agent_chat_result.get("data") # This is where agents should return parsed JSON

    # Display the primary message
    await cl.Message(content=message_content, author=agent_name).send()

    # --- Handle state transitions and data saving based on agent and status ---

    if agent_name == "Onboarding Agent":
        if agent_chat_result["status"] == "success" and agent_chat_result.get("conversation_ended"):
            if extracted_data and extracted_data.get("type") == "onboarding_data":
                user_onboarding_data = extracted_data.get("data")
                cl.user_session.set("user_onboarding_data", user_onboarding_data)
                
                await cl.Message(
                    content="--- \n**Onboarding complete!** Now, let's find a career path for you. Please wait while I suggest some options...",
                    author="System"
                ).send()
                
                # Transition to suggesting career paths
                cl.user_session.set("current_stage", 'suggest_paths')
                
                # Directly ask MilestoneGeneratorAgent for career path suggestions
                milestone_generator_agent = cl.user_session.get("milestone_generator_agent")
                
                # The MilestoneGenerator's instructions for 'career_path_suggestion'
                # don't explicitly require user_onboarding_data in the *input message* itself,
                # but it uses it from the thread context. However, providing a structured
                # message helps it identify the request type.
                path_suggestion_request = {
                    "request_type": "suggest_career_paths",
                    "user_onboarding_data": user_onboarding_data # Pass data for context
                }
                path_suggestion_response = milestone_generator_agent.chat(f"Suggest career paths: {json.dumps(path_suggestion_request)}")
                await handle_agent_response(path_suggestion_response, "Milestone Generator Agent")
            else:
                await cl.Message(
                    content="Onboarding complete but couldn't extract user data. Something went wrong.",
                    author="Error"
                ).send()
                cl.user_session.set("current_stage", 'onboarding') # Stay in onboarding to fix

        elif agent_chat_result["status"] == "error":
            await cl.Message(
                content=f"Error during onboarding: {message_content}",
                author="Error"
            ).send()
            # Stays in 'onboarding' stage implicitly

    elif agent_name == "Milestone Generator Agent":
        if agent_chat_result["status"] == "success":
            if extracted_data and extracted_data.get("type") == "career_path_suggestion":
                suggested_paths = extracted_data.get("suggested_paths")
                cl.user_session.set("suggested_career_paths", suggested_paths)
                
                path_list_str = "\n".join([f"- **{path}**" for path in suggested_paths])
                await cl.Message(
                    content=f"Based on your profile, here are a few career paths that might be a great fit for you:\n\n{path_list_str}\n\nPlease choose one by typing its name.",
                    author="Milestone Generator"
                ).send()
                cl.user_session.set("current_stage", 'select_path') # Now user needs to select

            elif extracted_data and extracted_data.get("type") == "initial_generation":
                generated_milestones = extracted_data.get("milestones")
                cl.user_session.set("generated_milestones", generated_milestones)
                
                await cl.Message(
                    content="--- \n### Career Milestones Plan\n"
                            f"```json\n{json.dumps(extracted_data, indent=2)}\n```\n" # Display the full JSON
                            "Your career dashboard is being set up with these milestones! "
                            "I am now handing you over to your Career Coach for ongoing support.",
                    author="System"
                ).send()
                
                # Initialize CareerCoachAgent with all gathered data
                user_onboarding_data = cl.user_session.get("user_onboarding_data")
                selected_career_path = cl.user_session.get("selected_career_path")

                # The CareerCoach needs the context of the user's profile and milestones
                career_coach_agent = CareerCoach(
                    thread_id=SHARED_THREAD_ID,
                    user_onboarding_data=user_onboarding_data,
                    milestones_data={"career_path": selected_career_path, "milestones": generated_milestones}
                )
                cl.user_session.set("career_coach_agent", career_coach_agent) # Store the initialized coach

                # Transition to general coaching
                cl.user_session.set("current_stage", 'coaching')

                # Initiate the first message from the Career Coach
                coach_initial_message = f"Hello! User's onboarding is complete and milestones for {selected_career_path} are set. Ready to guide them."
                coach_response = career_coach_agent.chat(coach_initial_message)
                await handle_agent_response(coach_response, "Career Coach")

            else:
                await cl.Message(
                    content=f"Milestone Generator returned unknown success data type: {json.dumps(extracted_data)}",
                    author="Error"
                ).send()
                cl.user_session.set("current_stage", 'onboarding') # Fallback
        elif agent_chat_result["status"] == "error":
            await cl.Message(
                content=f"Error from Milestone Generator: {message_content}",
                author="Error"
            ).send()
            cl.user_session.set("current_stage", 'onboarding') # Fallback to restart flow

    elif agent_name == "Career Coach":
        # For Career Coach, just display the message. It's the final stage.
        if agent_chat_result["status"] == "error":
            await cl.Message(
                content=f"Error from Career Coach: {message_content}",
                author="Error"
            ).send()