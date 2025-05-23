import os
import secrets
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from langchain.schema import SystemMessage, HumanMessage
from langchain_groq import ChatGroq

# In-memory session storage for Railway compatibility
global_session_store = {}

load_dotenv()
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app, supports_credentials=True, origins=["https://graduation-project-jet.vercel.app"])

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

llm = ChatGroq(
    model_name="llama3-70b-8192",
    temperature=0.1,
    api_key=os.getenv("GROQ_API_KEY")
)

MEDICAL_PROMPT_BASE = """
**Medical Assistant Protocol v4.2**

**ROLE:**
Your role is to act strictly as MediPulse, a responsible AI-powered preliminary health assistant. Your **sole purpose** is to provide **general health guidance only** based on symptoms and context shared by the user. You MUST NOT diagnose, suggest tests, or replace a healthcare provider.

**LANGUAGE:**
{language_instruction}

**CONVERSATIONAL FLOW:**
1. Greet the user and ask about their symptoms.
2. Ask 5–7 structured medical questions one at a time (age, symptom duration, severity, history, meds, allergies...)
3. Provide one question at a time only. Use this format for choices: `[OPTIONS: Yes, No]`

**ASSESSMENT FORMAT:**
You may provide a health summary *only* after enough input.  
You MUST follow the exact structure below when generating the assessment. Do NOT include any paragraphs, introductions, or extra explanations outside this format.

🩺 **Preliminary Health Summary**

**🧾 Based on your responses:**
- Symptoms may be related to:
  - 🔹 [General Category 1]
  - 🔹 [General Category 2]

**💊 Suggestions (if mild):**
- [OTC Suggestion with dosage]  
  _Note: {otc_disclaimer}_

**📅 Seek medical attention if:**
- Symptoms worsen or persist more than 2–3 days
- You experience: chest pain, breathing difficulty, dizziness...

🛑 _This is not a diagnosis. Always consult a doctor._

**SAFETY RULES:**
- For emergency symptoms, stop and respond only with: {emergency_text}
- Do NOT name specific diseases (e.g., "you have pneumonia")
- Do NOT recommend diagnostic tests (X-ray, bloodwork...): use {diagnostic_test_referral}
- Do NOT engage in unrelated, personal, or joke questions: use {off_topic_response}
"""

PROMPT_COMPONENTS = {
    "en": {
        "language_instruction": "You MUST respond in clear, simple **English**.",
        "emergency_text": "🆘 **Some symptoms may be serious. Please seek emergency medical help immediately.**",
        "otc_disclaimer": "This is a general suggestion. Consult a pharmacist or doctor for details.",
        "diagnostic_test_referral": "Only a doctor can decide if diagnostic tests are needed. Please consult one.",
        "assessment_start_disclaimer": "Here is a general summary. This is **not a diagnosis**.",
        "final_disclaimer": "This is not medical advice. Always consult a licensed doctor.",
        "off_topic_response": "I'm a health assistant. I can't help with that."
    },
    "ar": {
        "language_instruction": "يجب أن ترد باللغة **العربية الفصحى المبسطة** فقط.",
        "emergency_text": "🆘 **بعض الأعراض قد تكون خطيرة. يرجى التوجه فوراً للطوارئ أو الاتصال بالطبيب.**",
        "otc_disclaimer": "هذا مجرد اقتراح عام. استشر صيدلي أو طبيب للتفاصيل.",
        "diagnostic_test_referral": "الطبيب وحده هو من يمكنه تحديد إذا كنت بحاجة لفحوصات. يرجى استشارته.",
        "assessment_start_disclaimer": "إليك ملخصًا عامًا. هذا **ليس تشخيصًا طبيًا**.",
        "final_disclaimer": "هذا لا يُغني عن زيارة الطبيب. استشر طبيبًا مرخصًا دائمًا.",
        "off_topic_response": "أنا مساعد صحي ولا أستطيع المساعدة في هذا النوع من الأسئلة."
    }
}

def get_dynamic_prompt(language='en'):
    lang_code = language.lower()
    if lang_code not in PROMPT_COMPONENTS:
        lang_code = 'en'
    components = PROMPT_COMPONENTS[lang_code]
    return MEDICAL_PROMPT_BASE.format(
        language_instruction=components["language_instruction"],
        emergency_text=components["emergency_text"],
        otc_disclaimer=components["otc_disclaimer"],
        diagnostic_test_referral=components["diagnostic_test_referral"],
        assessment_start_disclaimer=components["assessment_start_disclaimer"],
        final_disclaimer=components["final_disclaimer"],
        off_topic_response=components["off_topic_response"]
    )

def extract_options(message):
    import re
    match = re.search(r'\[OPTIONS:\s*(.*?)\]', message)
    if match:
        options_str = match.group(1)
        options = [opt.strip() for opt in re.split('[،,]', options_str) if opt.strip()]
        clean_message = re.sub(r'\[OPTIONS:\s*(.*?)\]', '', message).strip()
        return clean_message, options
    return message, None

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

    initial_message = (
        "مرحباً! أنا MediPulse، المساعد الطبي الرقمي. كيف يمكنني مساعدتك اليوم؟ يرجى وصف الأعراض أو المخاوف الصحية التي تواجهها."
        if language == "ar" else
        "Hello! I'm MediPulse, your digital medical assistant. How can I help you today? Please describe your symptoms."
    )

    logging.info(f"New session started: {session_id}, language: {language}")
    return jsonify({
        "session_id": session_id,
        "response": initial_message,
        "language": language
    })

@app.route("/api/chat", methods=["POST"])
def handle_chat():
    data = request.get_json()
    session_id = data.get("session_id")
    user_input = data.get("message", "").strip()
    session_data = global_session_store.get(session_id)

    if not session_data:
        logging.warning(f"Invalid session: {session_id}")
        return jsonify({"error": "Invalid or expired session.", "action": "restart"}), 401

    language = session_data["language"]
    prompt = get_dynamic_prompt(language)

    messages = [SystemMessage(content=prompt)]
    for inp, out in session_data["history"]:
        messages.append(HumanMessage(content=inp))
        messages.append(SystemMessage(content=out))
    messages.append(HumanMessage(content=user_input))

    response = llm.invoke(messages).content
    session_data["history"].append((user_input, response))

    clean_response, options = extract_options(response)
    response_data = {"response": clean_response}
    if options:
        response_data["options"] = options
    return jsonify(response_data)

@app.route("/api/end_chat", methods=["POST"])
def end_chat():
    data = request.get_json()
    session_id = data.get("session_id")
    session_data = global_session_store.get(session_id)

    if not session_data:
        return jsonify({"error": "Invalid or expired session.", "action": "restart"}), 401

    language = session_data["language"]
    summary_prompt = PROMPT_COMPONENTS[language].get("summary_prompt") or PROMPT_COMPONENTS["en"].get("summary_prompt")

    messages = [SystemMessage(content="You are a medical summarizer that creates clear, concise summaries of medical conversations.")]
    for inp, out in session_data["history"]:
        messages.append(HumanMessage(content=inp))
        messages.append(SystemMessage(content=out))
    messages.append(HumanMessage(content=summary_prompt))

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
