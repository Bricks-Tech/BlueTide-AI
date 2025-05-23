import os
import time
from dotenv import load_dotenv
import openai
import regex as re

load_dotenv()

# Cache assistant ID (file-based for simplicity)
ASSISTANT_ID_FILE = ".assistant_id"

ONBOARDING_FILE_PATH = "user_onboarding_data.json"
MILESTONES_FILE_PATH = "user_milestones.json"


def create_client():
    API_KEY = os.getenv("OPENAI_API_KEY")
    return openai.OpenAI(api_key=API_KEY)


def create_assistant(name, instructions, OPENAI_CLIENT):
    # Check for cached assistant
    if os.path.exists(ASSISTANT_ID_FILE):
        with open(ASSISTANT_ID_FILE, "r") as f:
            return f.read().strip()

    assistant = OPENAI_CLIENT.beta.assistants.create(
        name=name,
        instructions=instructions,
        tools=[{"type": "code_interpreter"}],
        model="gpt-4o",
    )

    with open(ASSISTANT_ID_FILE, "w") as f:
        f.write(assistant.id)

    return assistant.id


def create_thread(OPENAI_CLIENT):
    thread = OPENAI_CLIENT.beta.threads.create()
    return thread.id


def call_openAI(thread_id, assistant_id, user_input, instructions, OPENAI_CLIENT):
    # Add user message to thread
    OPENAI_CLIENT.beta.threads.messages.create(
        thread_id=thread_id, role="user", content=user_input
    )

    # Create a run with instructions
    run = OPENAI_CLIENT.beta.threads.runs.create(
        thread_id=thread_id, assistant_id=assistant_id, instructions=instructions
    )

    # Poll status
    while True:
        run_status = OPENAI_CLIENT.beta.threads.runs.retrieve(
            thread_id=thread_id, run_id=run.id
        )

        if run_status.status == "completed":
            break
        elif run_status.status in ["failed", "cancelled", "expired"]:
            raise Exception(f"Run failed with status: {run_status.status}")

        time.sleep(1)

    # Fetch latest assistant message
    messages = OPENAI_CLIENT.beta.threads.messages.list(thread_id=thread_id)
    return messages.data[0].content[0].text.value


def get_all_messages_from_thread(thread_id, OPENAI_CLIENT):
    try:
        messages = OPENAI_CLIENT.beta.threads.messages.list(
            thread_id=thread_id,
            order="asc",  # Fetch messages in ascending order (chronological)
        )
        formatted_messages = []
        for msg in messages.data:
            if msg.content and msg.content[0].type == "text":
                formatted_messages.append(
                    {
                        "role": msg.role,
                        "content": msg.content[0].text.value,
                        "id": msg.id,
                        "created_at": msg.created_at,
                    }
                )
        return formatted_messages
    except Exception as e:
        print(f"Error retrieving messages: {e}")
        return []


def delete_thread(thread_id, OPENAI_CLIENT):
    try:
        response = OPENAI_CLIENT.beta.threads.delete(thread_id)
        return response
    except Exception as e:
        print(f"Error deleting thread {thread_id}: {e}")
        return None


def get_thread_details(thread_id, OPENAI_CLIENT):
    try:
        thread_info = OPENAI_CLIENT.beta.threads.retrieve(thread_id)
        return thread_info
    except Exception as e:
        print(f"Error retrieving thread details for {thread_id}: {e}")
        return None


def contains_json_block(response_string: str) -> bool:
    
    # This regex is simpler because it only needs to check for the presence
    # of the pattern, not necessarily capture the content for parsing yet.
    # It looks for ```json followed by any characters (non-greedy) until ```
    pattern = re.compile(r"```json.*?```", re.DOTALL)
    return bool(pattern.search(response_string))


def check_onboarding_file_present() -> bool:
    """
    Checks if the user_onboarding_data.json file exists.
    """
    return os.path.exists(ONBOARDING_FILE_PATH)

def check_milestones_file_present() -> bool:
    """
    Checks if the user_milestones.json file exists.
    """
    return os.path.exists(MILESTONES_FILE_PATH)

def get_current_user_state() -> str:
    """
    Determines the current state of the user's journey based on the presence of
    onboarding and milestones files.

    Returns:
        str: A string indicating the current state ('onboarding', 'milestones', 'career_coach').
    """
    onboarding_present = check_onboarding_file_present()
    milestones_present = check_milestones_file_present()

    if not onboarding_present:
        return "onboarding"
    elif onboarding_present and not milestones_present:
        return "milestones"
    else:  # both onboarding and milestones are present
        return "career_coach"