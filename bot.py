"""
Minimal Flask-based endpoint for Foundry that logs with simple print()
Nothing extra—just print statements and basic try/except.

• POST /api/messages  { "text": "<user prompt>" }  →  { "reply": "<assistant text>" }
• Uses the web-app’s managed identity via DefaultAzureCredential
"""

import os, traceback
from flask import Flask, request, jsonify, Response
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

# ─────────── workspace details (already filled in) ───────────
CONN_STR = (
    "eastus.api.azureml.ms;"
    "f920ee3b-6bdc-48c6-a487-9e0397b69322;"
    "rashmitest;"
    "rashmid-5367"
)
ASSISTANT_ID = "asst_cPyJBoSit1obmj3BJyfKSY7R"
# ─────────────────────────────────────────────────────────────

print("✅ Starting up…")
credential = DefaultAzureCredential()
credential.get_token("https://management.azure.com/.default")
print("🔐 Managed-identity token ok")

project_client = AIProjectClient.from_connection_string(
    credential=credential, conn_str=CONN_STR
)
assistant = project_client.agents.get_agent(ASSISTANT_ID)
print("🤖 Assistant ready:", assistant.id)

app = Flask(__name__)

@app.route("/", methods=["GET"])
def root():
    return Response("✅ Alive", 200)

@app.route("/api/messages", methods=["POST"])
def messages():
    try:
        user_input = (request.json or {}).get("text", "")
        if not user_input:
            print("⚠️ 400 – missing text")
            return jsonify(error="Missing field 'text'"), 400
        print("📩 USER:", user_input)

        # call assistant
        thread = project_client.agents.create_thread()
        project_client.agents.create_message(thread.id, role="user", content=user_input)
        project_client.agents.create_and_process_run(thread.id, assistant.id)
        msgs = project_client.agents.list_messages(thread.id).data

        reply = next(
            (
                part["text"]["value"]
                for m in msgs if m.role == "assistant"
                for part in (m.content if isinstance(m.content, list) else [])
                if part.get("type") == "text"
            ),
            "(no assistant reply)",
        )
        print("📤 ASSISTANT:", reply)
        return jsonify(reply=reply), 200

    except Exception:
        print("❌ 500 – exception below")
        traceback.print_exc()
        return jsonify(error="internal server error"), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))   # Azure injects PORT in production
    print(f"🚀 Listening on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)
