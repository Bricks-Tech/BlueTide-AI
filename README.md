# BlueTide-AI

# What to do
Create API's for bubble to communicate with the chatbot. Integrate the chatbot with bubble. The overall logic is given in chainlit.py but the other agents would need to be integrated as well. 

# How to Run the Application

To get this career guidance system up and running, follow these steps:

1.  **Install Dependencies:**
    
    ```bash
    pip install -r requirements.txt
    ```
    If any dependnecies are missing please install them manually. 

2.  **Configure Environment Variables:**
    The `.env` file is used for sensitive information like API keys. Create or edit the `.env` file in the root directory of your project and add any required API keys 
    ```
    OPENAI_API_KEY=your_OPENAI_api_key_here
    ```
    **Important:** Replace `your_OPENAI_api_key_here` with your actual API key.

3.  **Run the Application:**
    Navigate to the root directory of your project (`BLUETIDE-AI`) in your terminal (where `chainlit.py` is located). Then, run the application using the `chainlit` command:
    ```bash
    chainlit run chainlit.py -w
    ```
    * `chainlit run chainlit.py`: This command tells Chainlit to execute your `chainlit.py` file.
    * `-w` or `--watch`: This flag enables "watch mode," meaning Chainlit will automatically restart the application if it detects changes in your project files, which is very useful during development.

4.  **Access the Application:**
    Once the command is executed, Chainlit will typically provide a local URL (e.g., `http://localhost:8000`) in your terminal. Open this URL in your web browser to interact with the AI career guidance system.


# File Tree Explanation

This project directory (`BLUETIDE-AI`) is structured to manage a multi-agent AI system for personalized career guidance.

* **`Agents/`**: This folder contains all the individual specialized AI agents that handle different aspects of the career guidance process. Each `.py` file within this directory represents a distinct agent (e.g., `career_coach_agent.py`, `onboarding_agent.py`, `master_agent.py`).
* `chainlit.py`: This is the test file where you can see the output and how the agents would communicate. Running this file would give you a good idea of how the flow of the conversation would go. 
**Note:** Right now it only uses two agents the onboarding agent and the career coach. The final flow should use all the agents respectively whenever their is a need to call them. 
* `helpers.py`: This file contains utility functions that are used across multiple agents or parts of the system to avoid code duplication.
* `prompts.py`: This file is crucial for defining the system prompts and instructions that guide the behavior of the different AI agents. It holds the detailed instructions provided in the original input.
* `user_milestones.json`: This file likely stores the career milestones generated for a specific user, maintaining their progress and plan within the system.
* `user_onboarding_data.json`: This file stores the detailed career information collected from the user during the onboarding process.
**Note:** When Naeem bhai sets up the DB in bubble these jsons should be stored over there in the users table.


# Agent Descriptions

### ONBOARDING_AGENT
**Explanation:** This agent is designed to collect detailed career information from users, guiding them through a series of questions about their goals, preferences, and skills to improve.
**Output:** A JSON object containing the user's complete career profile.

### CAREER_COACH
**Explanation:** As an empathetic and strategic AI Career Guidance Coach, this agent helps users achieve their career objectives by acknowledging onboarding data, suggesting career paths, and generating actionable milestones.
**Output:** JSON for career milestones and personalized guidance.
**Note:** This is supposed to be the career coach that the user would talk to after onboarding is done and milestones are generated. I have created a seperate agent for geneating milestones please once taht is integrated you can remove the milestone generation functionality from here. 

### SKILL_GAP_ANALYZER
**Explanation:** This agent compares a user's existing skills with the requirements of a selected career path, identifying specific skill deficiencies.
**Output:** A JSON object detailing skill gaps and recommending relevant learning resources.

### REFLECTION_CHECK_IN_AGENT
**Explanation:** This agent provides emotional and goal-oriented support through periodic check-ins, prompting users to reflect on their progress and emotional state.
**Output:** Natural, conversational language to offer empathetic guidance and suggest next steps.

### MILESTONE_GENERATOR
**Explanation:** This agent translates career aspirations into actionable career paths and structured milestones, capable of generating initial milestone sets or refining specific milestones based on user feedback.
**Output:** JSON containing either suggested career paths or detailed milestones.

### MASTER_AI_AGENT
**Explanation:** Serving as the central routing system, this agent is the initial point of contact, understanding user intent and directing requests to the most appropriate specialized agent.
**Output:** A JSON object specifying which agent to call and any relevant messages.