let sessionId = localStorage.getItem('medipulseSessionId') || null;
let selectedLanguage = 'en';
let isProcessing = false;

// DOM elements
const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const optionsContainer = document.getElementById('options-container');
const enBtn = document.getElementById('en-btn');
const arBtn = document.getElementById('ar-btn');
const endChatBtn = document.getElementById('end-chat-btn');

const summaryModal = document.getElementById('summary-modal');
const chatSummary = document.getElementById('chat-summary');
const closeModal = document.querySelector('.close-modal');
const saveSummaryBtn = document.getElementById('save-summary-btn');
const newChatBtn = document.getElementById('new-chat-btn');

document.addEventListener('DOMContentLoaded', () => {
    sendButton.addEventListener('click', handleSend);
    userInput.addEventListener('keypress', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    enBtn.addEventListener('click', () => setLanguage('en'));
    arBtn.addEventListener('click', () => setLanguage('ar'));
    endChatBtn.addEventListener('click', endChat);

    closeModal.addEventListener('click', () => summaryModal.style.display = 'none');
    newChatBtn.addEventListener('click', () => startSession(true)); // force new session

    startSession(); // auto-start
});

async function startSession(forceNew = false) {
    if (!forceNew && sessionId) return;

    const res = await fetch("/api/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ language: selectedLanguage })
    });
    const data = await res.json();
    sessionId = data.session_id;
    localStorage.setItem('medipulseSessionId', sessionId);
    selectedLanguage = data.language;
    updateLanguageUI();
    displayBotMessage(data.response);
}

async function handleSend() {
    if (isProcessing) return;
    const message = userInput.value.trim();
    if (!message) return;
    userInput.value = '';
    optionsContainer.innerHTML = '';
    displayUserMessage(message);
    await sendMessage(message);
}

async function sendMessage(message) {
    if (!sessionId) return;
    isProcessing = true;
    displayBotMessage('', true);

    const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: sessionId, message })
    });
    const data = await res.json();
    chatBox.removeChild(chatBox.lastChild);

    if (data.error) {
        if (data.action === "restart") {
            localStorage.removeItem('medipulseSessionId');
            displayBotMessage(data.error);
            setTimeout(() => startSession(true), 1000);
        } else {
            displayBotMessage(`⚠️ Error: ${data.error}`);
        }
        isProcessing = false;
        return;
    }

    displayBotMessage(data.response);
    if (data.options) displayOptions(data.options);
    isProcessing = false;
    userInput.focus();
}

async function endChat() {
    if (!sessionId) return;
    const res = await fetch("/api/end_chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: sessionId })
    });
    const data = await res.json();

    if (data.error && data.action === "restart") {
        localStorage.removeItem('medipulseSessionId');
        displayBotMessage(data.error);
        setTimeout(() => startSession(true), 1000);
        return;
    }

    if (data.summary) {
        chatSummary.innerHTML = data.summary;
        summaryModal.style.display = 'block';
    }
}

async function setLanguage(lang) {
    if (!sessionId || lang === selectedLanguage) return;
    const res = await fetch("/api/set_language", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: sessionId, language: lang })
    });
    const data = await res.json();
    if (data.status === 'success') {
        selectedLanguage = data.language;
        updateLanguageUI();
    }
}

function updateLanguageUI() {
    enBtn.classList.toggle('active', selectedLanguage === 'en');
    arBtn.classList.toggle('active', selectedLanguage === 'ar');
    document.body.dir = selectedLanguage === 'ar' ? 'rtl' : 'ltr';
    userInput.placeholder = selectedLanguage === 'ar'
        ? 'اكتب رسالتك...'
        : 'Type your message...';
    endChatBtn.innerHTML = selectedLanguage === 'ar'
        ? '<i class="fas fa-times-circle"></i> إنهاء المحادثة'
        : '<i class="fas fa-times-circle"></i> End Chat';
}

function displayUserMessage(text) {
    const div = document.createElement('div');
    div.className = 'user-message message';
    div.textContent = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function displayBotMessage(text, isLoading = false) {
    const div = document.createElement('div');
    div.className = 'bot-message message';
    if (isLoading) {
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'loading-dots';
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('div');
            dot.className = 'dot';
            loadingDiv.appendChild(dot);
        }
        div.appendChild(loadingDiv);
    } else {
        div.textContent = text;
    }
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function displayOptions(options) {
    optionsContainer.innerHTML = '';
    options.forEach(option => {
        const button = document.createElement('button');
        button.className = 'option-btn';
        button.textContent = option;
        button.onclick = () => {
            userInput.value = option;
            handleSend();
        };
        optionsContainer.appendChild(button);
    });
}
