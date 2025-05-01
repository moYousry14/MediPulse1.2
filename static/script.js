document.addEventListener('DOMContentLoaded', () => {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const boolOptions = document.getElementById('bool-options');
    const yesBtn = document.getElementById('yes-btn');
    const noBtn = document.getElementById('no-btn');
    let sessionId = null;

    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => e.key === 'Enter' && sendMessage());
    yesBtn.addEventListener('click', () => handleBoolean('Yes'));
    noBtn.addEventListener('click', () => handleBoolean('No'));

    async function startSession() {
        try {
            const res = await fetch('/api/start', { method: 'POST' });
            const data = await res.json();
            sessionId = data.session_id;
            handleQuestion(data.question);
        } catch (error) {
            addMessage('bot', `⚠️ Error: ${error.message}`);
        }
    }

    async function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;
        
        addMessage('user', message);
        userInput.value = '';
        
        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, message })
            });
            
            const data = await res.json();
            if (data.error) throw new Error(data.error);
            
            if (data.stage === "assessment") {
                userInput.placeholder = "Describe symptoms in detail...";
                boolOptions.style.display = "none";
                userInput.style.display = "block";
                addMessage('bot', data.message);
            }
            else if (data.next_question) {
                handleQuestion(data.next_question);
            }
            else if (data.response) {
                addMessage('bot', data.response);
            }
            
        } catch (error) {
            addMessage('bot', `⚠️ Error: ${error.message}`);
        }
    }

    function handleBoolean(answer) {
        userInput.value = answer;
        sendMessage();
    }

    function handleQuestion(question) {
        addMessage('bot', question.text);
        boolOptions.classList.toggle('visible', question.type === 'boolean');
        userInput.style.display = question.type === 'boolean' ? 'none' : 'block';
        userInput.focus();
    }

    function addMessage(sender, text) {
        const div = document.createElement('div');
        div.className = `${sender}-message message`;
        div.textContent = text;
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    startSession();
});