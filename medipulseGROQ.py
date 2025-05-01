import os
import re
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from langchain.memory import ConversationBufferMemory
from langchain_groq import ChatGroq

load_dotenv()
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# Initialize Groq LLM
llm = ChatGroq(
    model_name="llama3-70b-8192",
    temperature=0.1,
    api_key=os.getenv("GROQ_API_KEY")
)

# Medical configuration
MEDICAL_PROMPT = """
**Medical Assistant Protocol v3.0**

ROLE:
You are MediPulse, an AI medical assistant providing preliminary health information only.
Never diagnose or replace professional medical advice.

REQUIREMENTS:
1. SAFETY FIRST:
   - Immediately flag emergency symptoms with: "🆘 Seek emergency care if you experience: [specific symptoms]"
   - Never suggest prescription medications
   - For OTC recommendations:
     * Specify exact dosage (e.g., "500mg acetaminophen every 6-8 hours")
     * Add disclaimer: "Consult pharmacist for proper use"

2. RESPONSE GUIDELINES:
   - Keep responses under 120 words
   - Ask one clear follow-up question at a time
   - Use simple, non-alarming language
   - Maintain professional tone

3. ASSESSMENT FORMAT:
   After gathering information, provide:
   - Possible conditions (1-3 most likely)
   - Recommended OTC options (when appropriate)
   - When to seek medical attention
   - Final disclaimer: 
     "This is informational only. Always consult a licensed physician."

4. BOUNDARIES:
   - Only discuss health-related topics
   - For non-medical queries: "I specialize in health questions only."
"""
questions = [
    {"id": "name", "text": "What is your full name?", "type": "text"},
    {"id": "age", "text": "What is your age?", "type": "number"},
    {"id": "smoker", "text": "Are you currently a smoker?", "type": "boolean"},
    {"id": "conditions", "text": "Do you have any existing medical conditions?", "type": "boolean"},
    {"id": "symptoms", "text": "What specific symptoms are you experiencing?", "type": "text"}
]

user_sessions = {}

@app.route("/api/start", methods=["POST"])
def start_chat():
    session_id = secrets.token_urlsafe(16)
    user_sessions[session_id] = {
        "memory": ConversationBufferMemory(return_messages=True),
        "current_index": 0,
        "stage": "questions",
        "created_at": datetime.now()
    }
    return jsonify({
        "session_id": session_id,
        "question": questions[0],
        "progress": 1
    })

@app.route("/api/chat", methods=["POST"])
def handle_chat():
    data = request.get_json()
    session_id = data.get("session_id")
    session = user_sessions.get(session_id)
    
    if not session:
        return jsonify({"error": "Invalid session"}), 401
    
    user_input = data["message"].strip()
    memory = session["memory"]
    current_index = session["current_index"]
    
    if session["stage"] == "questions":
        current_q = questions[current_index]
        
        if current_q["type"] == "boolean":
            normalized = "Yes" if user_input.lower() in ["yes", "y"] else "No" if user_input.lower() in ["no", "n"] else None
            if not normalized:
                return jsonify({"error": "Please answer Yes or No"}), 400
            user_input = normalized
        
        memory.save_context(
            {"input": current_q["text"]},
            {"output": user_input}
        )
        
        try:
            current_index += 1
            session["current_index"] = current_index
            
            if current_index >= len(questions):
                session["stage"] = "assessment"
                return jsonify({
                    "message": "Please describe your symptoms in detail:",
                    "stage": "assessment"
                })
            
            next_q = questions[current_index]
            return jsonify({
                "next_question": next_q,
                "progress": int((current_index + 1) / len(questions) * 100)
            })
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    elif session["stage"] == "assessment":
        try:
            messages = [
                SystemMessage(content=MEDICAL_PROMPT),
                *memory.load_memory_variables({})["history"],
                HumanMessage(content=user_input)
            ]
            response = llm.invoke(messages).content
            memory.save_context(
                {"input": user_input},
                {"output": response}
            )
            return jsonify({"response": response})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4000, debug=True)
