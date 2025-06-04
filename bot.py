import os
import asyncio
import traceback
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
print("✅ Flask app initialized.")

# Hardcoded App ID (from Azure app registration)
app_id = "4313e013-ed55-4640-8827-ee970c9e6390"
app_password = None  # Federated credentials, so no password needed
print(f"🆔 App ID: {app_id}")
print(f"🔑 App Password set: {bool(app_password)}")

# Bot Framework adapter setup
settings = BotFrameworkAdapterSettings(
    app_id=app_id,
    app_password=app_password
)
adapter = BotFrameworkAdapter(settings)

# Foundry client setup
try:
    print("🔐 Initializing Azure credentials...")
    credential = DefaultAzureCredential()
    token = credential.get_token("https://management.azure.com/.default")
    print("✅ Token acquired:", token.token[:40] + "...")

    print("🔧 Setting up AIProjectClient...")
    project_client = AIProjectClient.from_connection_string(
        credential=credential,
        conn_str="eastus.api.azureml.ms;f920ee3b-6bdc-48c6-a487-9e0397b69322;rashmitest;rashmid-5367"
    )
    agent = project_client.agents.get_agent("asst_cPyJBoSit1obmj3BJyfKSY7R")
    print("🤖 Foundry agent initialized.")
except Exception as e:
    print("❌ Failed to initialize Foundry client:")
    traceback.print_exc()

@app.route("/", methods=["GET"])
def index():
    return Response("✅ Bot is running.", status=200)

@app.route("/api/messages", methods=["POST"])
def messages():
    try:
        activity = Activity().deserialize(request.json)
        print("📩 Message received:", activity.text)

        async def process(turn_context: TurnContext):
            user_input = turn_context.activity.text or "[No input]"
            print("🔍 Processing input:", user_input)

            try:
                new_thread = project_client.agents.create_thread()
                print("🧵 New thread created:", new_thread.id)

                project_client.agents.create_message(
                    thread_id=new_thread.id,
                    role="user",
                    content=user_input
                )

                project_client.agents.create_and_process_run(
                    thread_id=new_thread.id,
                    assistant_id=agent.id
                )

                response_messages = project_client.agents.list_messages(thread_id=new_thread.id)
                print("🧾 Full response object:")
                for i, msg in enumerate(response_messages.data):
                    print(f"Message[{i}]:", msg.__dict__)

                for msg in response_messages.data:
                    if getattr(msg, "role", None) == "assistant":
                        text = ""
                        if isinstance(msg.content, list):
                            for content_piece in msg.content:
                                if content_piece.get("type") == "text":
                                    text = content_piece["text"]["value"]
                                    break
                        else:
                            text = str(msg.content)

                        print("📤 Responding with:", text)
                        await turn_context.send_activity(text)
                        return

                await turn_context.send_activity("⚠️ No assistant response found.")
            except Exception:
                print("❌ Error during agent interaction:")
                traceback.print_exc()
                await turn_context.send_activity("❌ Failed to get response from agent.")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(adapter.process_activity(activity, "", process))
        loop.close()

        return Response("✅ Processed", status=200)

    except Exception:
        print("❌ Error handling message:")
        traceback.print_exc()
        return Response("Internal Server Error", status=500)

if __name__ == "__main__":
    print("🚀 Starting Flask app...")
    app.run(host="0.0.0.0", port=8000)
