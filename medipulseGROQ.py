import os
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
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "https://graduation-project-jet.vercel.app/"}})
 # Enable CORS for all routes

# Configure Flask-Session
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(16))
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./session_cache"
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = True


Session(app)

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize Groq LLM
llm = ChatGroq(
    model_name="llama3-70b-8192",
    temperature=0.1,
    api_key=os.getenv("GROQ_API_KEY")
)

# --- Medical Prompt Configuration v4.0 ---
# Updated prompt structure with question guidelines embedded
MEDICAL_PROMPT_BASE = """
**Medical Assistant Protocol v4.1**

**ROLE:**
You are MediPulse, an AI medical assistant. Your **sole purpose** is to provide **preliminary, general health information** based on user-provided symptoms and context. **Crucially, you MUST NOT diagnose medical conditions or replace consultation with a qualified healthcare professional.** Your information is based on general patterns and does not constitute a personalized medical assessment.

**LANGUAGE:**
{language_instruction}

**CONVERSATIONAL FLOW & QUESTION PROTOCOL:**

1. **INITIAL INTERACTION:**
   * Begin by greeting the user and asking them to describe their main symptoms or concerns.
   * After they respond, you MUST conduct a structured intake by asking a series of at least 5 key medical questions, one at a time.
   * These questions should gather essential information about:
     - Age (important for risk stratification)
     - Duration and progression of symptoms
     - Severity and characteristics of symptoms
     - Relevant medical history (including chronic conditions, if any)
     - Current medications (if any)
     - Any attempted remedies and their effects
     - Any known allergies (when relevant)
     - Any other symptoms they're experiencing

2. **QUESTION FORMAT & BUTTON SUPPORT:**
   * Present ONE question at a time and wait for a response before asking the next.
   * For yes/no or multiple-choice questions, provide clear options by formatting like this: `[OPTIONS: option1, option2, option3]`
   * When writing in Arabic, use the same format: `[OPTIONS: خيار1, خيار2, خيار3]` - make sure to separate options with a comma
   * When you use this format, the interface will automatically generate clickable buttons for users.
   * For example, in English: "Do you have any allergies to medications? [OPTIONS: Yes, No]"
   * For example, in Arabic: "هل لديك أي حساسية من الأدوية؟ [OPTIONS: نعم, لا]"
   * Use a mix of open-ended and option-based questions to gather detailed information efficiently.

3. **EFFICIENT QUESTION FLOW:**
   * **Important:** Do NOT use phrases like "thank you for sharing" or "thank you for providing this information" between questions. This creates unnecessary repetition.
   * After receiving an answer, ask the next question directly without acknowledgment phrases.
   * Only use acknowledgments at the beginning of the conversation and before delivering the final assessment.
   * When moving from one question to the next, be direct and concise.
   * Good example: "How long have you had these symptoms? [OPTIONS: Less than a day, 1-3 days, 4-7 days, More than a week]"
   * Bad example: "Thank you for sharing. How long have you had these symptoms?"

4. **TAILORED QUESTIONING:**
   * Adapt your questioning based on the specific health concern described.
   * For respiratory issues: ask about cough characteristics, breathing difficulty, etc.
   * For digestive issues: ask about diet changes, pain location, bowel changes, etc.
   * For pain: ask about location, quality, radiation, severity (1-10 scale), timing, etc.

**CORE SAFETY REQUIREMENTS:**

1. **EMERGENCY IDENTIFICATION - NON-NEGOTIABLE:**
   * If the user describes symptoms potentially indicating a medical emergency, **immediately** prioritize this. Respond ONLY with: {emergency_text}

2. **MEDICATION GUIDANCE LIMITATIONS:**
   * **No Prescriptions:** **Never** suggest or recommend prescription medications.
   * **OTC Guidance (Use Sparingly):** If suggesting Over-The-Counter (OTC) options seems appropriate for *mild, common* symptoms:
     * Specify *exact* common dosage and frequency (e.g., "Consider trying acetaminophen 500mg every 6-8 hours as needed for pain" or the Arabic equivalent).
     * **Always** include this disclaimer: {otc_disclaimer}
     * Avoid suggesting OTCs for symptoms that are severe, persistent, or potentially indicative of a serious underlying condition.
   * **Diagnostic/Treatment Decisions:** **Never** give an opinion on whether a diagnostic test (like X-rays, blood tests) or a specific treatment plan is necessary or appropriate. If asked about such matters, respond ONLY with: {diagnostic_test_referral}

**ASSESSMENT GUIDELINES:**

1. **WHEN TO PROVIDE ASSESSMENT:**
   * Only provide an assessment after you have gathered sufficient information through your structured questioning (at least 5 key questions).
   * If the user provides very detailed information in their first message, you may ask fewer questions, but still ask at least 3 clarifying questions.

2. **ASSESSMENT FORMAT:**
   * **Start with Acknowledgment:** Begin with a brief acknowledgment like "Thank you for providing this information."
   * **Disclaimer:** Follow with: {assessment_start_disclaimer}
   * **Possible Conditions:** List 1-3 *possible* general categories or types of conditions that *might* be associated with the symptoms (e.g., "Symptoms like these can sometimes be related to viral infections or muscle strain." or the Arabic equivalent). **Avoid definitive statements.**
   * **OTC Options (If applicable & safe):** Mention relevant OTC options following the strict guidelines above, including the OTC disclaimer.
   * **When to Seek Medical Attention:** Provide clear guidance, considering symptom severity and duration (e.g., "It's advisable to consult a doctor if symptoms worsen, don't improve within [e.g., 2-3 days], or if you develop new concerning symptoms like high fever." or the Arabic equivalent).
   * **Conclude with Disclaimer:** End **every** assessment response with: {final_disclaimer}

**BOUNDARIES & PRIVACY:**
* **Scope:** Strictly limit discussion to health-related topics presented by the user.
* **Off-Topic Deflection:** For non-medical queries, respond politely ONLY with: {off_topic_response}
* **Privacy:** Do not ask for unnecessary personal details beyond the medical information needed for assessment.
"""

# Language-Specific Text Components
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
            diagnostic_test_referral=components["diagnostic_test_referral"],
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
            diagnostic_test_referral=components["diagnostic_test_referral"],
            assessment_start_disclaimer=components["assessment_start_disclaimer"],
            final_disclaimer=components["final_disclaimer"],
            off_topic_response=components["off_topic_response"]
        )
        
    return prompt

# Helper function to extract options from LLM response
def extract_options(message):
    """Extract options from message formatted with [OPTIONS: option1, option2, ...]"""
    import re
    
    # Look for the options pattern in the message
    options_pattern = r'\[OPTIONS:\s*(.*?)\]'
    match = re.search(options_pattern, message)
    
    if match:
        options_str = match.group(1)
        
        # Handle both English and Arabic commas
        # Arabic comma: '،' (different from English comma ',')
        if '،' in options_str:
            options = [opt.strip() for opt in options_str.split('،')]
        else:
            options = [opt.strip() for opt in options_str.split(',')]
        
        # Remove any empty options
        options = [opt for opt in options if opt]
        
        # Replace the options pattern with empty string to clean the message
        clean_message = re.sub(options_pattern, '', message).strip()
        return clean_message, options
    
    return message, None

@app.route("/api/start", methods=["POST"])
def start_chat():
    data = request.get_json() or {}
    language = data.get("language", "en").lower()
    
    if language not in PROMPT_COMPONENTS:
        language = "en"  # Default to English if invalid language
    
    session.clear()
    session["memory_history"] = []
    session["language"] = language
    session["created_at"] = datetime.now().isoformat()
    
    # Initialize LLM interaction
    system_prompt = get_dynamic_prompt(language)
    
    try:
        # Prepare initial greeting message based on language
        if language == "ar":
            initial_message = "مرحباً! أنا MediPulse، المساعد الطبي الرقمي. كيف يمكنني مساعدتك اليوم؟ يرجى وصف الأعراض أو المخاوف الصحية التي تواجهها."
        else:
            initial_message = "Hello! I'm MediPulse, your digital medical assistant. How can I help you today? Please describe the symptoms or health concerns you're experiencing."
        
        logging.info(f"New session started: {session.sid}, language: {language}")
        return jsonify({
            "session_id": session.sid,
            "response": initial_message, 
            "language": language
        })
    except Exception as e:
        error_msg = "An error occurred starting the session" if language == "en" else "حدث خطأ أثناء بدء الجلسة"
        logging.error(f"Error starting session: {e}", exc_info=True)
        return jsonify({"error": error_msg}), 500

@app.route("/api/chat", methods=["POST"])
def handle_chat():
    data = request.get_json()
    
    if "memory_history" not in session:
        logging.warning(f"Invalid or expired session access attempt: {session.sid}")
        return jsonify({"error": "Invalid or expired session. Please start a new chat.", "action": "restart"}), 401

    user_input = data["message"].strip()
    language = session.get("language", "en")
    
    # Rebuild memory object from history stored in session
    memory = ConversationBufferMemory(return_messages=True)
    for msg_input, msg_output in session["memory_history"]:
        memory.save_context({"input": msg_input}, {"output": msg_output})

    try:
        # Get the correct system prompt based on selected language
        system_prompt = get_dynamic_prompt(language)
        
        # Prepare messages for LLM
        messages = [
            SystemMessage(content=system_prompt),
            *memory.load_memory_variables({})["history"],
            HumanMessage(content=user_input)
        ]
        
        # Invoke LLM
        logging.info(f"Invoking LLM for session {session.sid} ({language})")
        response = llm.invoke(messages).content
        logging.info(f"LLM response received for session {session.sid} ({language})")
        
        # Process response to extract options if present
        clean_response, options = extract_options(response)
        
        # Save context to memory object (and update session history)
        memory.save_context(
            {"input": user_input},
            {"output": response}  # Save the original response with options
        )
        session["memory_history"].append((user_input, response))
        
        response_data = {"response": clean_response}
        if options:
            response_data["options"] = options
        
        return jsonify(response_data)
    except Exception as e:
        error_msg = "An internal error occurred" if language == "en" else "حدث خطأ داخلي"
        logging.error(f"Error during chat for session {session.sid} ({language}): {e}", exc_info=True)
        return jsonify({"error": error_msg}), 500

@app.route("/api/end_chat", methods=["POST"])
def end_chat():
    data = request.get_json()
    
    if "memory_history" not in session:
        logging.warning(f"Invalid or expired session access attempt: {session.sid}")
        return jsonify({"error": "Invalid or expired session. Please start a new chat.", "action": "restart"}), 401

    language = session.get("language", "en")
    
    try:
        # Rebuild memory object from history stored in session
        memory = ConversationBufferMemory(return_messages=True)
        for msg_input, msg_output in session["memory_history"]:
            memory.save_context({"input": msg_input}, {"output": msg_output})
        
        # Create a summary prompt based on language
        if language == "ar":
            summary_prompt = """
            استناداً إلى المحادثة السابقة، قم بإنشاء ملخص طبي موجز (250 كلمة كحد أقصى) يتضمن:

            1. الأعراض الرئيسية التي ذكرها المريض
            2. المعلومات المهمة مثل العمر والحالات الصحية الموجودة مسبقاً
            3. النصائح العامة التي قدمتها
            4. أي إرشادات للمتابعة

            يجب أن يكون الملخص منظماً بتنسيق واضح مع عناوين فرعية. تذكر أن تشمل تنويهاً أن هذا ليس تشخيصاً طبياً رسمياً.
            """
        else:
            summary_prompt = """
            Based on the previous conversation, create a concise medical summary (maximum 250 words) that includes:

            1. The main symptoms reported by the patient
            2. Important information like age and pre-existing conditions
            3. The general advice you provided
            4. Any follow-up recommendations
            
            The summary should be organized with clear formatting and subheadings. Remember to include a disclaimer that this is not an official medical diagnosis.
            """
        
        # Prepare messages for LLM
        messages = [
            SystemMessage(content="You are a medical summarizer that creates clear, concise summaries of medical conversations."),
            *memory.load_memory_variables({})["history"],
            HumanMessage(content=summary_prompt)
        ]
        
        # Invoke LLM
        logging.info(f"Generating summary for session {session.sid} ({language})")
        summary = llm.invoke(messages).content
        logging.info(f"Summary generated for session {session.sid} ({language})")
        
        return jsonify({"summary": summary})
    
    except Exception as e:
        error_msg = "An error occurred generating the summary" if language == "en" else "حدث خطأ أثناء إنشاء الملخص"
        logging.error(f"Error generating summary for session {session.sid} ({language}): {e}", exc_info=True)
        return jsonify({"error": error_msg}), 500

@app.route("/api/set_language", methods=["POST"])
def set_language():
    """Endpoint to update session language preference"""
    if "memory_history" not in session:
        return jsonify({"error": "Invalid or expired session. Please start a new chat.", "action": "restart"}), 401
    
    data = request.get_json()
    language = data.get("language", "en").lower()
    
    if language not in PROMPT_COMPONENTS:
        return jsonify({"error": "Unsupported language"}), 400
    
    session["language"] = language
    logging.info(f"Session {session.sid} language updated to: {language}")
    
    return jsonify({"status": "success", "language": language})

@app.route("/")
def home():
    return render_template("index.html")

# if __name__ == "__main__":
#    app.run()

