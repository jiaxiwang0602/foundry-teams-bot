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
from azure.identity import DefaultAzureCredential, ChainedTokenCredential, AzureCliCredential, ManagedIdentityCredential

# -------------------- Flask App Setup --------------------
app = Flask(__name__)
print("⚙️ Flask app initialized.")

# -------------------- Bot Adapter --------------------
settings = BotFrameworkAdapterSettings(
    app_id=os.environ.get("MicrosoftAppId", ""),
    app_password=os.environ.get("MicrosoftAppPassword", "")
)
adapter = BotFrameworkAdapter(settings)

# -------------------- Foundry Agent Setup --------------------
try:
    print("🔐 Initializing Azure credentials...")
    credential = DefaultAzureCredential()

    # DEBUG: Attempt to fetch token and print its source
    try:
        token = credential.get_token("https://management.azure.com/.default")
        print("🔑 Token acquired:", token.token[:40] + "...")
    except Exception as auth_error:
        print("❌ Failed to acquire token:", auth_error)
        traceback.print_exc()

    print("🔧 Setting up AIProjectClient...")
    project_client = AIProjectClient.from_connection_string(
        credential=credential,
        conn_str="eastus.api.azureml.ms;f920ee3b-6bdc-48c6-a487-9e0397b69322;rashmitest;rashmid-5367"
    )

    agent = project_client.agents.get_agent("asst_cPyJBoSit1obmj3BJyfKSY7R")
    thread = project_client.agents.get_thread("thread_wEYymWvgUhWB1HlVJk3j1tX2")
    print("✅ Foundry agent and thread initialized.")
except Exception as e:
    print(f"❌ Failed to initialize Foundry agent or project client: {e}")
    traceback.print_exc()

# -------------------- Routes --------------------
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
                print("❌ Failed to create message:")
                traceback.print_exc()

            try:
                print("🚀 Triggering agent run...")
                project_client.agents.create_and_process_run(
                    thread_id=thread.id,
                    assistant_id=agent.id
                )
            except Exception as e2:
                print("❌ Failed to trigger run:")
                traceback.print_exc()

            try:
                print("📨 Fetching response from Foundry agent...")
                response_messages = project_client.agents.list_messages(thread_id=thread.id)

                print("🧾 Full response object:")
                for i, msg in enumerate(response_messages.data):
                    print(f"Message[{i}]:", msg.__dict__ if hasattr(msg, "__dict__") else str(msg))

                # Optional: reply with the last assistant message
                for msg in reversed(response_messages.data):
                    if getattr(msg, "role", None) == "assistant":
                        print("📤 Responding with:", msg.content)
                        await turn_context.send_activity(msg.content)
                        break
                else:
                    print("⚠️ No assistant response found.")
                    await turn_context.send_activity("⚠️ No assistant response found.")
            except Exception as e3:
                print("❌ Failed to list or parse messages:")
                traceback.print_exc()
                await turn_context.send_activity("⚠️ Failed to get response from agent.")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(adapter.process_activity(activity, "", process))
        loop.close()

        return Response("Processed", status=200)

    except Exception as e:
        print("❌ Error~~~ handling message:")
        traceback.print_exc()
        return Response("Internal Server Error", status=500)

# -------------------- Entrypoint --------------------
if __name__ == "__main__":
    print("🚀 Starting Flask app...")
    app.run(host="0.0.0.0", port=8000)
