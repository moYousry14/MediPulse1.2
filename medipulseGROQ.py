import os
import re
import secrets
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from flask_session import Session  # Import Flask-Session
from dotenv import load_dotenv
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain.memory import ConversationBufferMemory
from langchain_groq import ChatGroq

load_dotenv()
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app) # Enable CORS for all routes

# Configure Flask-Session
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(16))
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./session_cache"
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)

Session(app)

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize Groq LLM
llm = ChatGroq(
    model_name="llama3-70b-8192",
    temperature=0.1,
    api_key=os.getenv("GROQ_API_KEY")
)

# --- Medical Prompt Configuration v3.5 ---
# Base prompt structure with clear placeholders
MEDICAL_PROMPT_BASE = """
**Medical Assistant Protocol v3.5**

**ROLE:**
You are MediPulse, an AI medical assistant. Your **sole purpose** is to provide **preliminary, general health information** based on user-provided symptoms and context (age, smoking status, existing conditions).
**Crucially, you MUST NOT diagnose medical conditions or replace consultation with a qualified healthcare professional.** Your information is based on general patterns and does not constitute a personalized medical assessment.

**LANGUAGE:**
{language_instruction}

**CORE REQUIREMENTS:**

1.  **SAFETY FIRST - NON-NEGOTIABLE:**
    *   **Emergency Identification:** If the user describes symptoms potentially indicating a medical emergency, **immediately** prioritize this. Respond ONLY with: {emergency_text}
    *   **No Prescriptions:** **Never** suggest or recommend prescription medications.
    *   **OTC Guidance (Use Sparingly):** If suggesting Over-The-Counter (OTC) options seems appropriate for *mild, common* symptoms:
        *   Specify *exact* common dosage and frequency (e.g., "Consider trying acetaminophen 500mg every 6-8 hours as needed for pain" or the Arabic equivalent).
        *   **Always** include this disclaimer: {otc_disclaimer}
        *   Avoid suggesting OTCs for symptoms that are severe, persistent, or potentially indicative of a serious underlying condition.
    *   **Diagnostic/Treatment Decisions:** **Never** give an opinion on whether a diagnostic test (like X-rays, blood tests) or a specific treatment plan is necessary or appropriate. If asked about such matters, respond ONLY with: {diagnostic_test_referral}

2.  **RESPONSE GUIDELINES & CONVERSATION FLOW:**
    *   **Clarification First:** When the user first describes their symptoms, **if the description is brief or lacks detail (e.g., "my back hurts", "I feel sick"), you MUST ask at least one clarifying question** (e.g., "Can you tell me more about the pain? Where exactly?", "What kind of sickness are you feeling?") **before** providing any assessment or suggestions. Only proceed to the assessment format (point 3) after receiving more details.
    *   **Conciseness:** Keep responses under approximately 120 words.
    *   **Focused Interaction:** Ask only **one clear, concise follow-up question** at a time if more information is needed.
    *   **Language:** Use simple, clear, and non-alarming language in the specified language. Avoid overly technical jargon.
    *   **Tone:** Maintain an empathetic, professional, and objective tone.

3.  **ASSESSMENT STAGE FORMAT (Use ONLY after sufficient symptom details are gathered):**
    *   **Start with Disclaimer:** Begin the response with: {assessment_start_disclaimer}
    *   **Possible Conditions:** List 1-3 *possible* general categories or types of conditions that *might* be associated with the symptoms (e.g., "Symptoms like these can sometimes be related to viral infections or muscle strain." or the Arabic equivalent). **Avoid definitive statements.**
    *   **OTC Options (If applicable & safe):** Mention relevant OTC options following the strict guidelines in point 1, including the OTC disclaimer.
    *   **When to Seek Medical Attention:** Provide clear guidance, considering symptom severity and duration (e.g., "It's advisable to consult a doctor if symptoms worsen, don't improve within [e.g., 2-3 days], or if you develop new concerning symptoms like high fever." or the Arabic equivalent).
    *   **Conclude with Disclaimer:** End **every** assessment response with: {final_disclaimer}

4.  **BOUNDARIES & PRIVACY:**
    *   **Scope:** Strictly limit discussion to health-related topics presented by the user.
    *   **Off-Topic Deflection:** For non-medical queries, respond politely ONLY with: {off_topic_response}
    *   **Privacy:** Do not ask for unnecessary personal details beyond the initial structured questions.
"""

# Language-Specific Text Components (No instructions here, just the text)
PROMPT_COMPONENTS = {
    "en": {
        "language_instruction": "You MUST respond in clear, simple **English**.",
        "emergency_text": "🆘 **Based on what you've described, some symptoms could be serious. Please seek immediate emergency medical care if you experience any of the following: severe chest pain, difficulty breathing, sudden weakness or numbness, severe bleeding, loss of consciousness, severe headache, or confusion. Do not delay.**",
        "otc_disclaimer": "This is a general suggestion. Please consult a pharmacist or read the product label carefully for proper use, dosage, and potential interactions.",
        "diagnostic_test_referral": "Decisions about tests like X-rays or specific treatments should only be made by a qualified doctor after a proper evaluation. Please consult your physician to discuss the best course of action.",
        "assessment_start_disclaimer": "Based on the information provided, here is some general guidance. Remember, this is **not a diagnosis**, and you should always consult a licensed physician for medical advice.",
        "final_disclaimer": "This information is for general knowledge only and does not replace professional medical evaluation. Please consult a qualified healthcare provider for any health concerns.",
        "off_topic_response": "My function is limited to providing preliminary health information. I cannot assist with that request."
    },
    "ar": {
        "language_instruction": "يجب أن ترد **حصراً** باللغة **العربية الفصحى المبسطة**.",
        "emergency_text": "🆘 **بناءً على ما وصفته، قد تكون بعض الأعراض خطيرة. يرجى طلب الرعاية الطبية الطارئة فوراً إذا واجهت أياً من الأعراض التالية: ألم شديد في الصدر، صعوبة في التنفس، ضعف أو خدر مفاجئ، نزيف حاد، فقدان الوعي، صداع شديد، أو ارتباك. لا تتأخر.**",
        "otc_disclaimer": "هذا اقتراح عام. يرجى استشارة صيدلي أو قراءة ملصق المنتج بعناية لمعرفة الاستخدام السليم والجرعة والتفاعلات المحتملة.",
        "diagnostic_test_referral": "القرارات المتعلقة بالفحوصات مثل الأشعة أو العلاجات المحددة يجب أن يتخذها الطبيب المؤهل فقط بعد التقييم المناسب. يرجى استشارة طبيبك لمناقشة أفضل مسار للعمل.",
        "assessment_start_disclaimer": "بناءً على المعلومات المقدمة، إليك بعض الإرشادات العامة. تذكر أن هذا **ليس تشخيصاً**، ويجب عليك دائماً استشارة طبيب مرخص للحصول على المشورة الطبية.",
        "final_disclaimer": "هذه المعلومات للمعرفة العامة فقط ولا تحل محل التقييم الطبي المتخصص. يرجى استشارة مقدم رعاية صحية مؤهل لأي مخاوف صحية.",
        "off_topic_response": "وظيفتي تقتصر على تقديم معلومات صحية أولية. لا يمكنني المساعدة في هذا الطلب."
    }
}
def get_dynamic_prompt(language='en'):
    """Generates the full system prompt by injecting language components into the base."""
    lang_code = language.lower()
    if lang_code not in PROMPT_COMPONENTS:
        lang_code = 'en'  # Default to English if language is unsupported
    
    components = PROMPT_COMPONENTS[lang_code]
    
    # Use string formatting to inject components into the base prompt
    try:
        prompt = MEDICAL_PROMPT_BASE.format(
            language_instruction=components["language_instruction"],
            emergency_text=components["emergency_text"],
            otc_disclaimer=components["otc_disclaimer"],
            diagnostic_test_referral=components["diagnostic_test_referral"], # Added new placeholder
            assessment_start_disclaimer=components["assessment_start_disclaimer"],
            final_disclaimer=components["final_disclaimer"],
            off_topic_response=components["off_topic_response"]
        )
    except KeyError as e:
        logging.error(f"Missing key in PROMPT_COMPONENTS for language '{lang_code}': {e}")
        # Fallback to English prompt if formatting fails
        components = PROMPT_COMPONENTS["en"]
        prompt = MEDICAL_PROMPT_BASE.format(
            language_instruction=components["language_instruction"],
            emergency_text=components["emergency_text"],
            otc_disclaimer=components["otc_disclaimer"],
            diagnostic_test_referral=components["diagnostic_test_referral"], # Added new placeholder
            assessment_start_disclaimer=components["assessment_start_disclaimer"],
            final_disclaimer=components["final_disclaimer"],
            off_topic_response=components["off_topic_response"]
        )
        
    return prompt

# --- End Prompt Configuration ---

# Updated Questions List
questions = [
    {"id": "language", "text": "Welcome! Which language would you prefer for our chat? (Arabic/English)", "text_ar": "أهلاً بك! أي لغة تفضل لمحادثتنا؟ (عربي/إنجليزي)", "type": "language"},
    {"id": "age", "text": "What is your age?", "text_ar": "ما هو عمرك؟", "type": "number"},
    {"id": "smoker", "text": "Are you currently a smoker?", "text_ar": "هل أنت مدخن حالياً؟", "type": "boolean"},
    {"id": "conditions", "text": "Do you have any existing medical conditions? (e.g., diabetes, high blood pressure)", "text_ar": "هل لديك أي حالات طبية موجودة؟ (مثل السكري، ارتفاع ضغط الدم)", "type": "boolean"},
    # Removed the initial generic symptoms question
]

@app.route("/api/start", methods=["POST"])
def start_chat():
    session.clear()
    session["memory_history"] = []
    session["current_index"] = 0
    session["stage"] = "questions" # Start with questions stage
    session["language"] = "en" # Default language
    session["created_at"] = datetime.now().isoformat()
    
    first_question = questions[0]
    # Send the first question (language selection) in both languages
    # Corrected f-string syntax for accessing dictionary keys
    question_text = f"{first_question['text']} / {first_question['text_ar']}"
    
    logging.info(f"New session started: {session.sid}, asking for language.")
    return jsonify({
        "session_id": session.sid,
        "question": {"id": first_question["id"], "text": question_text, "type": first_question["type"]},
        "progress": 0 # Progress starts after language selection
    })

@app.route("/api/chat", methods=["POST"])
def handle_chat():
    data = request.get_json()
    
    if "memory_history" not in session or "current_index" not in session or "stage" not in session:
        logging.warning(f"Invalid or expired session access attempt: {session.sid}")
        # Provide error in both languages as we don\'t know preference yet
        return jsonify({"error": "Invalid or expired session. Please start a new chat. / جلسة غير صالحة أو منتهية الصلاحية. يرجى بدء محادثة جديدة.", "action": "restart"}), 401

    user_input = data["message"].strip()
    current_index = session["current_index"]
    stage = session["stage"]
    language = session.get("language", "en") # Get language from session, default to English

    # --- Handle Language Selection (First Question) ---
    if stage == "questions" and current_index == 0 and questions[current_index]["id"] == "language":
        if "arab" in user_input.lower() or "عربي" in user_input:
            session["language"] = "ar"
            language = "ar"
            logging.info(f"Session {session.sid} language set to Arabic.")
        else:
            session["language"] = "en"
            language = "en"
            logging.info(f"Session {session.sid} language set to English.")
            
        # Move to the next question
        session["current_index"] += 1
        current_index += 1
        next_q_data = questions[current_index]
        next_q_text = next_q_data.get(f"text_{language}", next_q_data["text"]) # Get text in selected language
        
        return jsonify({
            "next_question": {"id": next_q_data["id"], "text": next_q_text, "type": next_q_data["type"]},
            "progress": int((current_index / len(questions)) * 100) # Start progress calculation
        })
    # --- End Language Selection Handling ---

    # Rebuild memory object from history stored in session
    memory = ConversationBufferMemory(return_messages=True)
    for msg_input, msg_output in session["memory_history"]:
        memory.save_context({"input": msg_input}, {"output": msg_output})

    # Get the correct system prompt based on selected language
    system_prompt = get_dynamic_prompt(language)

    if stage == "questions":
        # This part now handles questions *after* language selection (index > 0)
        current_q_data = questions[current_index]
        current_q_text = current_q_data.get(f"text_{language}", current_q_data["text"])
        
        # Input validation for boolean questions
        if current_q_data["type"] == "boolean":
            # Use language-specific yes/no
            yes_options = ["yes", "y", "نعم", "ايوه", "أيوة"]
            no_options = ["no", "n", "لا", "لأ"]
            normalized = None
            if user_input.lower() in yes_options:
                normalized = "Yes" if language == "en" else "نعم"
            elif user_input.lower() in no_options:
                normalized = "No" if language == "en" else "لا"
                
            if not normalized:
                error_msg = "Please answer Yes or No" if language == "en" else "يرجى الإجابة بنعم أو لا"
                logging.warning(f"Invalid boolean input for session {session.sid} ({language}): {user_input}")
                return jsonify({"error": error_msg}), 400
            user_input_processed = normalized
        else:
             user_input_processed = user_input # Use original input for non-boolean
        
        # Save context to memory object (and update session history)
        memory.save_context(
            {"input": current_q_text},
            {"output": user_input_processed}
        )
        session["memory_history"].append((current_q_text, user_input_processed))
        
        try:
            current_index += 1
            session["current_index"] = current_index
            
            if current_index >= len(questions):
                session["stage"] = "assessment"
                assessment_prompt = "Please describe your symptoms in detail:" if language == "en" else "يرجى وصف الأعراض بالتفصيل:"
                logging.info(f"Session {session.sid} moved to assessment stage ({language}).")
                return jsonify({
                    "message": assessment_prompt,
                    "stage": "assessment"
                })
            
            next_q_data = questions[current_index]
            next_q_text = next_q_data.get(f"text_{language}", next_q_data["text"])
            return jsonify({
                "next_question": {"id": next_q_data["id"], "text": next_q_text, "type": next_q_data["type"]},
                "progress": int((current_index / len(questions)) * 100)
            })
            
        except Exception as e:
            error_msg = "An internal error occurred processing your answer." if language == "en" else "حدث خطأ داخلي أثناء معالجة إجابتك."
            logging.error(f"Error during question stage for session {session.sid} ({language}): {e}", exc_info=True)
            return jsonify({"error": error_msg}), 500
    
    elif stage == "assessment":
        try:
            # Prepare messages for LLM, using the dynamic system prompt
            messages = [
                SystemMessage(content=system_prompt),
                *memory.load_memory_variables({})["history"],
                HumanMessage(content=user_input)
            ]
            
            # Invoke LLM
            logging.info(f"Invoking LLM for session {session.sid} ({language})")
            response = llm.invoke(messages).content
            logging.info(f"LLM response received for session {session.sid} ({language})")
            
            # Save context to memory object (and update session history)
            memory.save_context(
                {"input": user_input},
                {"output": response}
            )
            session["memory_history"].append((user_input, response))
            
            return jsonify({"response": response})
        except Exception as e:
            error_msg = "An internal error occurred while generating the assessment." if language == "en" else "حدث خطأ داخلي أثناء إنشاء التقييم."
            logging.error(f"Error during assessment stage for session {session.sid} ({language}): {e}", exc_info=True)
            return jsonify({"error": error_msg}), 500

@app.route("/")
def home():
    # Keep this route for potential testing or simple UI
    return render_template("index.html")

# Keep the __main__ block commented out for production/gunicorn
# if __name__ == "__main__":
#     app.run()

