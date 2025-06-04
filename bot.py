import os, traceback
from flask import Flask, request, jsonify, Response
# ── BotFramework imports – commented out ─────────────────────
# from botbuilder.core import (
#     BotFrameworkAdapterSettings,
#     BotFrameworkAdapter,
#     TurnContext,
# )
# from botbuilder.schema import Activity
# ──────────────────────────────────────────────────────────────
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

app = Flask(__name__)
print("Flask app initialized.")

# ───── Foundry client setup ──────────────────────────────────
try:
    print("Initializing Azure credentials...")
    credential = DefaultAzureCredential()
    credential.get_token("https://management.azure.com/.default")
    print("Token acquired ✓")

    project_client = AIProjectClient.from_connection_string(
        credential=credential,
        conn_str="eastus.api.azureml.ms;"
                 "f920ee3b-6bdc-48c6-a487-9e0397b69322;"
                 "rashmitest;"
                 "rashmid-5367",
    )
    agent = project_client.agents.get_agent("asst_cPyJBoSit1obmj3BJyfKSY7R")
    print("Foundry agent initialized.")
except Exception:
    print("Failed to initialize Foundry client:")
    traceback.print_exc()
# ──────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    return Response("✅ Web app is running.", 200)

@app.route("/api/messages", methods=["POST"])
def messages():
    """
    Payload: { "text": "<user prompt>" }
    Response: { "reply": "<assistant text>" }
    """
    try:
        user_input = (request.json or {}).get("text", "")
        if not user_input:
            return jsonify(error="Missing field 'text'"), 400
        print("📩 USER!!!:", user_input)

        # ───── Call Foundry assistant ─────
        thread = project_client.agents.create_thread()
        project_client.agents.create_message(
            thread_id=thread.id, role="user", content=user_input
        )
        project_client.agents.create_and_process_run(
            thread_id=thread.id, assistant_id=agent.id
        )
        msgs = project_client.agents.list_messages(thread_id=thread.id).data
        # ──────────────────────────────────

        reply = next(
            (
                piece["text"]["value"]
                for m in msgs if m.role == "assistant"
                for piece in (m.content if isinstance(m.content, list) else [])
                if piece.get("type") == "text"
            ),
            "(no assistant reply)",
        )
        print("📤 ASSISTANT:", reply)
        return jsonify(reply=reply), 200

    except Exception:
        print("❌ Error while handling request:")
        traceback.print_exc()
        return jsonify(error="internal server error"), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Starting Flask app on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)
