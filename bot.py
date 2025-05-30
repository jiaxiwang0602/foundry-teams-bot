import os
import asyncio
from flask import Flask, request, Response
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    BotFrameworkAdapter,
    TurnContext,
)
from botbuilder.schema import Activity
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

app = Flask(__name__)
print("⚙️ Flask app initialized.")

settings = BotFrameworkAdapterSettings(
    app_id=os.environ.get("MicrosoftAppId", ""),
    app_password=os.environ.get("MicrosoftAppPassword", "")
)
adapter = BotFrameworkAdapter(settings)

try:
    credential = DefaultAzureCredential()
    project_client = AIProjectClient.from_connection_string(
        credential=credential,
        conn_str="eastus.api.azureml.ms;f920ee3b-6bdc-48c6-a487-9e0397b69322;rashmitest;rashmid-5367"
    )
    agent = project_client.agents.get_agent("asst_cPyJBoSit1obmj3BJyfKSY7R")
    thread = project_client.agents.get_thread("thread_wEYymWvgUhWB1HlVJk3j1tX2")
    print("✅ Foundry agent and thread initialized.")
except Exception as e:
    print(f"❌ Failed to initialize Foundry agent: {e}")

@app.route("/", methods=["GET"])
def index():
    return Response("✅ Bot is running.", status=200)

@app.route("/api/messages", methods=["POST"])
def messages():
    try:
        print("📥 Raw POST body:", request.json)
        activity = Activity().deserialize(request.json)
        print("📩 Message received from Teams:", activity.text)

        async def process(turn_context: TurnContext):
            user_input = turn_context.activity.text or "[No input]"
            print("🔍 Processing:", user_input)

            try:
                print("🧠 Sending user message to Foundry agent...")
                project_client.agents.create_message(
                    thread_id=thread.id,
                    role="user",
                    content=user_input
                )
            except Exception as e1:
                print("❌ Failed to create message:", e1)

            try:
                print("🚀 Triggering agent run...")
                project_client.agents.create_and_process_run(
                    thread_id=thread.id,
                    assistant_id=agent.id
                )
            except Exception as e2:
                print("❌ Failed to trigger run:", e2)

            try:
                print("📨 Fetching response from Foundry agent...")
                response_messages = list(project_client.agents.list_messages(thread_id=thread.id))

                print("🧾 Full response object:")
                for i, msg in enumerate(response_messages):
                    print(f"Message[{i}]:", msg.__dict__ if hasattr(msg, "__dict__") else str(msg))

                # Optionally send a message back
                await turn_context.send_activity("✅ Messages fetched and logged in server.")

            except Exception as e3:
                print("❌ Failed to list or parse messages:", e3)
                await turn_context.send_activity("⚠️ Failed to get response from agent.")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(adapter.process_activity(activity, "", process))
        loop.close()

        return Response("Processed", status=200)

    except Exception as e:
        print(f"❌ Error!!! handling message: {e}")
        return Response("Internal Server Error", status=500)

if __name__ == "__main__":
    print("🚀 Starting Flask app...")
    app.run(host="0.0.0.0", port=8000)
