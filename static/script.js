let sessionId = localStorage.getItem('medipulseSessionId') || null;
let selectedLanguage = 'en';
let isProcessing = false;

// DOM elements
const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const optionsContainer = document.getElementById('options-container');
const endChatBtn = document.getElementById('end-chat-btn');

const summaryModal = document.getElementById('summary-modal');
const chatSummary = document.getElementById('chat-summary');
const closeModal = document.querySelector('.close-modal');
const saveSummaryBtn = document.getElementById('save-summary-btn');
const newChatBtn = document.getElementById('new-chat-btn');

// New modal for language selection
const langModal = document.getElementById('language-modal');
const chooseEn = document.getElementById('choose-en');
const chooseAr = document.getElementById('choose-ar');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    langModal.style.display = 'flex';

    chooseEn.addEventListener('click', () => {
        selectedLanguage = 'en';
        langModal.style.display = 'none';
        startSession(true);
    });

    chooseAr.addEventListener('click', () => {
        selectedLanguage = 'ar';
        langModal.style.display = 'none';
        startSession(true);
    });

    sendButton.addEventListener('click', handleSend);
    userInput.addEventListener('keypress', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    endChatBtn.addEventListener('click', endChat);
    closeModal.addEventListener('click', () => summaryModal.style.display = 'none');
    newChatBtn.addEventListener('click', () => {
        localStorage.removeItem('medipulseSessionId');
        location.reload();
    });
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

function updateLanguageUI() {
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
        const cleanText = simplifyFinalResponse(text);
        cleanText.split('\n').forEach(line => {
            const p = document.createElement('p');
            p.textContent = line.trim();
            div.appendChild(p);
        });
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

// 🧼 Clean + structure bot replies
function simplifyFinalResponse(text) {
    if (text.includes("🩺") || text.includes("Preliminary") || text.includes("ملخص مبدئي")) {
        return text
            .replace(/[*_#]/g, '')
            .replace(/🩺|🧠|💊|📅|🛑/g, '\n\n$&') // spacing before section emojis
            .replace(/\n{2,}/g, '\n\n') // normalize multiple newlines
            .trim();
    }
    return text;
}
