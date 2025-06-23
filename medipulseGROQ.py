import os
import secrets
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from langchain.schema import SystemMessage, HumanMessage
from langchain_groq import ChatGroq

global_session_store = {}

load_dotenv()
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app, supports_credentials=True, origins=["*"])

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.0,
    api_key=os.getenv("GROQ_API_KEY")
)

PROMPT_COMPONENTS = {
    "en": {
        "system_prompt": """
You are MediPulse, a friendly and intelligent AI chatbot that provides early-stage medical information.

Your role:
- Ask the user one relevant medical question at a time, clearly and briefly.
- Use plain language that's easy to understand.
- Do not assume information if the user hasn't provided it.

Format for final summaries:
🩺 Preliminary Summary  
🧠 Symptoms: bullet points  
💊 Suggestions (for mild cases): general advice  
📅 Seek help if: warning signs  
🛑 Disclaimer: "This is not a diagnosis"

❌ Avoid long paragraphs.  
✅ Use emojis, sections, and clear formatting.
Only summarize when you’ve collected enough symptoms.
""",
        "start_msg": "Hello! I'm MediPulse, your digital medical assistant. How can I help you today? Please describe your symptoms."
    },
    "ar": {
        "system_prompt": """
أنت MediPulse، روبوت دردشة ذكي يقدم معلومات طبية مبدئية بشكل مبسط ومسؤول.

دورك:
- اسأل سؤالاً واحدًا فقط في كل مرة، بوضوح وبأسلوب سهل.
- لا تفترض أي معلومات غير مذكورة من قبل المستخدم.

عند تلخيص الحالة، استخدم هذا الشكل:
🩺 ملخص مبدئي  
🧠 الأعراض: نقاط واضحة  
💊 اقتراحات بسيطة  
📅 متى تطلب المساعدة: علامات الخطر  
🛑 تنويه: "هذا ليس تشخيصًا طبياً"

❌ تجنب الفقرات الطويلة  
✅ استخدم الرموز التعبيرية والأقسام المختصرة
لا تُلخّص إلا بعد جمع ما يكفي من المعلومات.
""",
        "start_msg": "مرحباً! أنا MediPulse، المساعد الطبي الرقمي. كيف يمكنني مساعدتك اليوم؟ يرجى وصف الأعراض التي تشعر بها."
    }
}

def get_dynamic_prompt(language):
    return PROMPT_COMPONENTS.get(language, PROMPT_COMPONENTS["en"])["system_prompt"]

@app.route("/api/start", methods=["POST"])
def start_chat():
    data = request.get_json() or {}
    language = data.get("language", "en").lower()
    if language not in PROMPT_COMPONENTS:
        language = "en"

    session_id = secrets.token_urlsafe(32)
    global_session_store[session_id] = {
        "language": language,
        "created_at": datetime.now().isoformat(),
        "history": []
    }

    return jsonify({
        "session_id": session_id,
        "response": PROMPT_COMPONENTS[language]["start_msg"],
        "language": language
    })

@app.route("/api/chat", methods=["POST"])
def handle_chat():
    data = request.get_json()
    session_id = data.get("session_id")
    user_input = data.get("message", "").strip()
    session_data = global_session_store.get(session_id)

    if not session_data:
        return jsonify({"error": "Invalid or expired session.", "action": "restart"}), 401

    language = session_data["language"]
    system_prompt = get_dynamic_prompt(language)

    messages = [SystemMessage(content=system_prompt)]
    for inp, out in session_data["history"]:
        messages.append(HumanMessage(content=inp))
        messages.append(SystemMessage(content=out))
    messages.append(HumanMessage(content=user_input))

    response = llm.invoke(messages).content.strip()
    session_data["history"].append((user_input, response))

    return jsonify({"response": response})

@app.route("/api/end_chat", methods=["POST"])
def end_chat():
    data = request.get_json()
    session_id = data.get("session_id")
    session_data = global_session_store.get(session_id)

    if not session_data:
        return jsonify({"error": "Invalid or expired session.", "action": "restart"}), 401

    messages = [SystemMessage(content="You are a medical summarizer that creates clear, concise summaries of medical conversations.")]
    for inp, out in session_data["history"]:
        messages.append(HumanMessage(content=inp))
        messages.append(SystemMessage(content=out))
    messages.append(HumanMessage(content="Summarize the conversation in bullet points."))

    summary = llm.invoke(messages).content
    return jsonify({"summary": summary})

@app.route("/api/set_language", methods=["POST"])
def set_language():
    data = request.get_json()
    session_id = data.get("session_id")
    language = data.get("language", "en").lower()

    session_data = global_session_store.get(session_id)
    if not session_data:
        return jsonify({"error": "Invalid or expired session.", "action": "restart"}), 401

    if language not in PROMPT_COMPONENTS:
        return jsonify({"error": "Unsupported language"}), 400

    session_data["language"] = language
    return jsonify({"status": "success", "language": language})

@app.route("/")
def home():
    return render_template("index.html")

# if __name__ == "__main__":
#     app.run()
