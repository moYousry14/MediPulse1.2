# MediPulse — AI-Powered Health Assistant

**MediPulse** is a web application that helps users get safe, structured, early-stage health information in Arabic or English.  
It guides people through structured questions, providing general health info — never diagnoses — to reduce confusion from random online searches.

---

## 🚀 Features

- 🌐 **Multilingual support** — Arabic & English, with proper RTL/LTR layouts.
- 💬 **AI-powered chatbot** that asks structured questions and offers safe health guidance.
- 📝 **Session summary** at the end of the conversation.
- 🎯 Designed for general health awareness — not for diagnosis.

---

## ⚙️ Tech Stack

- **Frontend:**  
  - HTML, CSS, JavaScript (Vanilla)
- **Backend:**  
  - Python Flask
  - Flask-Session, Flask-CORS, dotenv
  - LangChain + Groq for AI chat
  - Gunicorn for production
- **Deployment:**  
  - Hosted on Railway

---

## 📚 What I Learned

- Working with pretrained AI models and prompt engineering to shape outputs.
- Handling multilingual UI (LTR & RTL) and structured conversational flows.
- Managing sessions and summaries with secure cookies + local storage.

---

## 🔥 Challenges

- Couldn’t train a model from scratch due to lack of comprehensive medical datasets.
- Focused on maximizing accuracy and safety through prompt tuning of a pretrained model.

---

## 🚀 Running Locally

1. **Clone the repo**
    ```bash
    git clone https://github.com/yourusername/medipulse.git
    cd medipulse
    ```

2. **Create a virtual environment & activate**
    ```bash
    python -m venv venv
    source venv/bin/activate  # on Windows use `venv\Scripts\activate`
    ```

3. **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4. **Create a `.env` file**
    ```
    FLASK_SECRET_KEY=your_secret_key
    # add any other required environment variables
    ```

5. **Run the app**
    ```bash
    flask run
    ```
    Then visit `http://127.0.0.1:5000` in your browser.

---

## 🌐 Live Demo

[https://medipulse12-production.up.railway.app/](https://medipulse12-production.up.railway.app/)

---

## 🤝 Credits

- The full MediPulse app was a team project.
- The chatbot (AI-powered structured conversation flow) was developed entirely by me.

---

