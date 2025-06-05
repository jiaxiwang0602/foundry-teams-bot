import os, time, traceback, asyncio
from flask import Flask, request, jsonify, Response

# ── OPTIONAL Bot Framework imports (for /api/echo) ──────────────
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity
# ────────────────────────────────────────────────────────────────

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

app = Flask(__name__)
print("Flask app initialized.")

# ───── Foundry client setup ────────────────────────────────────
try:
    print("Initializing Azure credentials...")
    credential = DefaultAzureCredential()
    credential.get_token("https://management.azure.com/.default")
    print("Token acquired ✓")

    project_client = AIProjectClient.from_connection_string(
        credential=credential,
        conn_str=(
            "eastus.api.azureml.ms;"
            "f920ee3b-6bdc-48c6-a487-9e0397b69322;"
            "rashmitest;"
            "rashmid-5367"
        ),
    )
    agent = project_client.agents.get_agent("asst_cPyJBoSit1obmj3BJyfKSY7R")
    print("Foundry agent initialized.")
except Exception:
    print("Failed to initialize Foundry client:")
    traceback.print_exc()
# ────────────────────────────────────────────────────────────────

# ───── Bot Framework adapter (echo endpoint) ────────────────────
# Leave APP_ID / APP_PW blank for local Emulator tests.
APP_ID = os.getenv("MicrosoftAppId", "")
APP_PW = os.getenv("MicrosoftAppPassword", "")
adapter = BotFrameworkAdapter(
    BotFrameworkAdapterSettings(app_id=APP_ID, app_password=APP_PW)
)
# ────────────────────────────────────────────────────────────────


def repeat_twice(text: str) -> str:
    return text + text


def ask_foundry_with_retry(prompt: str, max_attempts: int = 3) -> str:
    """Create a run, poll until assistant replies or give up."""
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        try:
            thread = project_client.agents.create_thread()
            project_client.agents.create_message(
                thread_id=thread.id, role="user", content=prompt
            )
            project_client.agents.create_and_process_run(
                thread_id=thread.id, assistant_id=agent.id
            )

            for _ in range(5):  # poll up to 10 s
                msgs = project_client.agents.list_messages(thread_id=thread.id).data
                reply = next(
                    (
                        p["text"]["value"]
                        for m in msgs
                        if m.role == "assistant"
                        for p in (m.content if isinstance(m.content, list) else [])
                        if p.get("type") == "text"
                    ),
                    None,
                )
                if reply:
                    return reply
                time.sleep(2)

            return "(assistant still processing – try again in a moment)"

        except Exception:
            print(f"⚠️  Foundry call failed (attempt {attempt}/{max_attempts})")
            traceback.print_exc()
            if attempt < max_attempts:
                time.sleep(2 ** attempt)
            else:
                return "(failed to contact assistant)"


@app.route("/", methods=["GET"])
def index():
    return Response("✅ Web app is running.", 200)


# ─────────────────── Foundry-powered bot (unchanged) ────────────
@app.route("/api/messages", methods=["POST"])
def messages():
    """POST {text} → Foundry assistant reply."""
    try:
        user_input = (request.json or {}).get("text", "")
        if not user_input:
            return jsonify(error="Missing field 'text'"), 400
        print("📩 USER:", user_input)

        reply = ask_foundry_with_retry(user_input)
        print("📤 ASSISTANT:", reply)
        return jsonify(reply=reply), 200

    except Exception:
        print("❌ Error while handling request:")
        traceback.print_exc()
        return jsonify(error="internal server error"), 500


# ───────────────────── NEW: Bot-Framework echo ───────────────────
@app.route("/api/echo", methods=["POST"])
def echo_bot():
    """Teams / Emulator entry — replies with <text><text>."""
    try:
        activity = Activity().deserialize(request.json)

        async def turn(turn_context: TurnContext):
            incoming = turn_context.activity.text or ""
            await turn_context.send_activity(repeat_twice(incoming))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(adapter.process_activity(activity, "", turn))
        loop.close()
        return Response(status=200)

    except Exception:
        traceback.print_exc()
        return Response("Internal Server Error", 500)


# ───────────── NEW: Plain REST echo for Postman/cURL ─────────────
@app.route("/api/repeat", methods=["POST"])
def repeat_endpoint():
    """POST { "text": "abc" } → { "reply": "abcabc" }"""
    txt = (request.json or {}).get("text", "")
    if not txt:
        return jsonify(error="Missing field 'text'"), 400
    return jsonify(reply=repeat_twice(txt)), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Starting Flask app on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)
