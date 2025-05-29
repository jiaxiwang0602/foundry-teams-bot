import os
import asyncio
from flask import Flask, request, Response
from botbuilder.core import BotFrameworkAdapter, TurnContext
from botbuilder.schema import Activity
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

app = Flask(__name__)

# Bot credentials (no password because we use federated identity)
adapter = BotFrameworkAdapter(
    app_id=os.environ.get("MicrosoftAppId", ""),
    app_password=""
)

# Azure AI Foundry setup
credential = DefaultAzureCredential()
project_client = AIProjectClient.from_connection_string(
    credential=credential,
    conn_str="eastus.api.azureml.ms;f920ee3b-6bdc-48c6-a487-9e0397b69322;rashmitest;rashmid-5367"
)
agent = project_client.agents.get_agent("asst_cPyJBoSit1obmj3BJyfKSY7R")
thread = project_client.agents.get_thread("thread_wEYymWvgUhWB1HlVJk3j1tX2")

# Health check endpoint (optional, useful for Azure App Service)
@app.route("/", methods=["GET"])
def index():
    return Response("Bot is running.", status=200)

@app.route("/api/messages", methods=["POST"])
def messages():
    try:
        activity = Activity().deserialize(request.json)

        async def process(turn_context: TurnContext):
            user_input = turn_context.activity.text or ""

            # Send user input to Foundry agent
            project_client.agents.create_message(thread.id, "user", user_input)
            project_client.agents.create_and_process_run(thread.id, agent.id)
            response_messages = project_client.agents.list_messages(thread.id)

            # Reply with last assistant response
            for msg in reversed(response_messages.text_messages):
                if msg.role == "assistant":
                    await turn_context.send_activity(msg.content)
                    break

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        task = loop.create_task(adapter.process_activity(activity, "", process))
        loop.run_until_complete(task)
        loop.close()

        return Response(status=200)
    
    except Exception as e:
        print(f"Error handling message: {e}")
        return Response("Internal Server Error", status=500)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
