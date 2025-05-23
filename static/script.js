document.addEventListener('DOMContentLoaded', () => {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const optionsContainer = document.getElementById('options-container');
    const enBtn = document.getElementById('en-btn');
    const arBtn = document.getElementById('ar-btn');
    const endChatBtn = document.getElementById('end-chat-btn');
    const historyBtn = document.getElementById('history-btn');
    
    // Modal elements
    const summaryModal = document.getElementById('summary-modal');
    const chatSummary = document.getElementById('chat-summary');
    const closeModal = document.querySelector('.close-modal');
    const saveSummaryBtn = document.getElementById('save-summary-btn');
    const newChatBtn = document.getElementById('new-chat-btn');
    
    // History modal elements
    const historyModal = document.getElementById('history-modal');
    const closeHistoryModal = document.querySelector('.close-history-modal');
    const noHistoryMessage = document.getElementById('no-history-message');
    const historyList = document.getElementById('history-list');
    
    // Chat record modal elements
    const chatRecordModal = document.getElementById('chat-record-modal');
    const closeRecordModal = document.querySelector('.close-record-modal');
    const chatRecordContainer = document.getElementById('chat-record-container');
    const deleteRecordBtn = document.getElementById('delete-record-btn');
    const closeRecordBtn = document.getElementById('close-record-btn');
    
    let sessionId = null;
    let selectedLanguage = 'en';
    let isProcessing = false;
    let patientId = localStorage.getItem('patientId') || generatePatientId();
    let currentRecordId = null;

    // Initialize patient storage if not already present
    if (!localStorage.getItem('patientId')) {
        localStorage.setItem('patientId', patientId);
        localStorage.setItem('chatHistory', JSON.stringify([]));
    }

    // Event listeners
    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Language switchers
    enBtn.addEventListener('click', () => setLanguage('en'));
    arBtn.addEventListener('click', () => setLanguage('ar'));
    
    // End chat and history buttons
    endChatBtn.addEventListener('click', endChat);
    historyBtn.addEventListener('click', showHistory);
    
    // Modal event listeners
    closeModal.addEventListener('click', () => summaryModal.style.display = 'none');
    saveSummaryBtn.addEventListener('click', saveChatSummary);
    newChatBtn.addEventListener('click', startNewChat);
    
    closeHistoryModal.addEventListener('click', () => historyModal.style.display = 'none');
    closeRecordModal.addEventListener('click', () => chatRecordModal.style.display = 'none');
    closeRecordBtn.addEventListener('click', () => chatRecordModal.style.display = 'none');
    deleteRecordBtn.addEventListener('click', deleteCurrentRecord);
    
    // Close modals if clicked outside
    window.addEventListener('click', (e) => {
        if (e.target === summaryModal) {
            summaryModal.style.display = 'none';
        } else if (e.target === historyModal) {
            historyModal.style.display = 'none';
        } else if (e.target === chatRecordModal) {
            chatRecordModal.style.display = 'none';
        }
    });

    // Initialize chat
    startSession();

    async function startSession() {
        try {
            // Show loading
            addBotMessage('', true);
            
            const res = await fetch('/api/start', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ language: selectedLanguage })
            });
            
            // Remove loading indicator
            chatBox.removeChild(chatBox.lastChild);
            
            const data = await res.json();
            
            if (data.error) throw new Error(data.error);
            
            sessionId = data.session_id;
            
            if (data.language) {
                selectedLanguage = data.language;
                updateLanguageUI();
            }
            
            addBotMessage(data.response);
            
        } catch (error) {
            // Remove loading indicator if it exists
            if (chatBox.lastChild && chatBox.lastChild.classList.contains('bot-message')) {
                chatBox.removeChild(chatBox.lastChild);
            }
            addBotMessage(`⚠️ Error: ${error.message}`);
        }
    }

    async function sendMessage() {
        if (isProcessing) return;
        
        const message = userInput.value.trim();
        if (!message) return;
        
        try {
            isProcessing = true;
            
            // Clear the input and options
            userInput.value = '';
            optionsContainer.innerHTML = '';
            
            // Add user message to chat
            addUserMessage(message);
            
            // Show loading indicator
            addBotMessage('', true);
            
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ 
                    session_id: sessionId, 
                    message 
                })
            });
            
            // Remove loading indicator
            chatBox.removeChild(chatBox.lastChild);
            
            const data = await res.json();
            
            if (data.error) {
                if (data.action === 'restart') {
                    // Session expired, restart
                    addBotMessage(data.error);
                    setTimeout(startSession, 1000);
                    return;
                }
                throw new Error(data.error);
            }
            
            // Add bot response to chat
            addBotMessage(data.response);
            
            // Display option buttons if provided
            if (data.options && data.options.length > 0) {
                displayOptions(data.options);
            }
            
        } catch (error) {
            // Remove loading indicator if it exists
            if (chatBox.lastChild && chatBox.lastChild.classList.contains('bot-message')) {
                chatBox.removeChild(chatBox.lastChild);
            }
            addBotMessage(`⚠️ Error: ${error.message}`);
        } finally {
            isProcessing = false;
            // Focus on input only if no options are shown
            if (optionsContainer.children.length === 0) {
                userInput.focus();
            }
        }
    }
    
    async function endChat() {
        if (!sessionId) return;
        
        try {
            isProcessing = true;
            
            // Inform the user that the chat is ending
            const endMessage = selectedLanguage === 'en' 
                ? "Thank you for using MediPulse. Generating your medical summary..."
                : "شكراً لاستخدامك MediPulse. جاري إنشاء ملخص طبي...";
            
            addBotMessage(endMessage);
            
            // Generate summary using the API
            const res = await fetch('/api/end_chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ 
                    session_id: sessionId,
                    language: selectedLanguage 
                })
            });
            
            const data = await res.json();
            
            if (data.error) throw new Error(data.error);
            
            // Display the summary modal
            displaySummaryModal(data.summary, getChatHistory());
            
        } catch (error) {
            addBotMessage(`⚠️ Error: ${error.message}`);
        } finally {
            isProcessing = false;
        }
    }
    
    function displaySummaryModal(summary, chatContent) {
        // Create a formatted summary
        let summaryHtml = `<h3>Medical Summary</h3>
                          <p class="summary-date">${new Date().toLocaleString()}</p>
                          <div class="summary-content">${summary || 'No summary available.'}</div>
                          <h3>Conversation History</h3>
                          <div class="conversation-log">`;
        
        // Add conversation history
        chatContent.forEach(msg => {
            const sender = msg.role === 'user' ? 'You' : 'MediPulse';
            summaryHtml += `<p><strong>${sender}:</strong> ${msg.content}</p>`;
        });
        
        summaryHtml += `</div>`;
        
        // Set the content and display modal
        chatSummary.innerHTML = summaryHtml;
        summaryModal.style.display = 'block';
    }
    
    function saveChatSummary() {
        // Get current stored chats
        const chatHistory = JSON.parse(localStorage.getItem('chatHistory')) || [];
        
        // Create new chat record
        const newChat = {
            id: generateChatId(),
            date: new Date().toISOString(),
            language: selectedLanguage,
            summary: chatSummary.innerHTML,
            conversation: getChatHistory()
        };
        
        // Add to history and save
        chatHistory.push(newChat);
        localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
        
        // Notify user
        const saveMessage = selectedLanguage === 'en'
            ? "Chat summary saved successfully!"
            : "تم حفظ ملخص المحادثة بنجاح!";
            
        alert(saveMessage);
        
        // Start a new chat
        startNewChat();
    }
    
    function getChatHistory() {
        const messages = [];
        const messageElements = chatBox.querySelectorAll('.message');
        
        messageElements.forEach(el => {
            if (el.classList.contains('user-message')) {
                messages.push({ role: 'user', content: el.textContent });
            } else if (el.classList.contains('bot-message') && !el.querySelector('.loading-dots')) {
                messages.push({ role: 'assistant', content: el.textContent });
            }
        });
        
        return messages;
    }
    
    function startNewChat() {
        // Close the modal
        summaryModal.style.display = 'none';
        
        // Clear chat box
        chatBox.innerHTML = '';
        
        // Reset and start new session
        sessionId = null;
        startSession();
    }
    
    function showHistory() {
        // Get chat history from localStorage
        const chatHistory = JSON.parse(localStorage.getItem('chatHistory')) || [];
        
        // Clear the history list
        historyList.innerHTML = '';
        
        if (chatHistory.length === 0) {
            // Show no history message
            noHistoryMessage.style.display = 'block';
        } else {
            // Hide no history message
            noHistoryMessage.style.display = 'none';
            
            // Populate history list with the most recent chats first
            chatHistory.slice().reverse().forEach(chat => {
                const date = new Date(chat.date);
                const formattedDate = date.toLocaleString();
                
                // Create a history entry element
                const entryEl = document.createElement('div');
                entryEl.className = 'history-entry';
                entryEl.dataset.id = chat.id;
                
                // Extract the main heading from the summary
                let summaryText = "Medical consultation";
                const summaryDiv = document.createElement('div');
                summaryDiv.innerHTML = chat.summary;
                const summaryHeading = summaryDiv.querySelector('h3');
                if (summaryHeading) {
                    summaryText = summaryHeading.textContent;
                }
                
                entryEl.innerHTML = `
                    <h3>${summaryText}</h3>
                    <p class="history-date">${formattedDate}</p>
                    <p class="history-summary">Click to view details</p>
                `;
                
                // Add click event to view the full record
                entryEl.addEventListener('click', () => {
                    showChatRecord(chat);
                });
                
                historyList.appendChild(entryEl);
            });
        }
        
        // Show the history modal
        historyModal.style.display = 'block';
    }
    
    function showChatRecord(record) {
        // Close history modal
        historyModal.style.display = 'none';
        
        // Set current record ID for deletion
        currentRecordId = record.id;
        
        // Display the record content
        chatRecordContainer.innerHTML = record.summary;
        
        // Show the record modal
        chatRecordModal.style.display = 'block';
    }
    
    function deleteCurrentRecord() {
        if (!currentRecordId) return;
        
        // Confirm deletion
        const confirmMessage = selectedLanguage === 'en'
            ? "Are you sure you want to delete this consultation record? This action cannot be undone."
            : "هل أنت متأكد من أنك تريد حذف سجل الاستشارة هذا؟ لا يمكن التراجع عن هذا الإجراء.";
            
        if (confirm(confirmMessage)) {
            // Get current stored chats
            let chatHistory = JSON.parse(localStorage.getItem('chatHistory')) || [];
            
            // Remove the current record
            chatHistory = chatHistory.filter(chat => chat.id !== currentRecordId);
            
            // Save updated history
            localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
            
            // Close the record modal
            chatRecordModal.style.display = 'none';
            
            // Show updated history
            showHistory();
            
            // Notify user
            const deleteMessage = selectedLanguage === 'en'
                ? "Record deleted successfully!"
                : "تم حذف السجل بنجاح!";
                
            alert(deleteMessage);
        }
    }
    
    function displayOptions(options) {
        optionsContainer.innerHTML = '';
        
        options.forEach(option => {
            const button = document.createElement('button');
            button.className = 'option-btn';
            button.textContent = option;
            button.addEventListener('click', () => {
                userInput.value = option;
                sendMessage();
            });
            optionsContainer.appendChild(button);
        });
    }

    function addUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'user-message message';
        div.textContent = text;
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function addBotMessage(text, isLoading = false) {
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

    async function setLanguage(lang) {
        if (lang === selectedLanguage) return;
        
        try {
            const res = await fetch('/api/set_language', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include', 
                body: JSON.stringify({ language: lang })
            });
            
            const data = await res.json();
            
            if (data.error) throw new Error(data.error);
            
            selectedLanguage = lang;
            updateLanguageUI();
            
            // If switching language mid-conversation, inform the user
            if (sessionId) {
                const message = lang === 'en' 
                    ? 'Language switched to English' 
                    : 'تم تغيير اللغة إلى العربية';
                addBotMessage(message);
            }
            
        } catch (error) {
            addBotMessage(`⚠️ Error: ${error.message}`);
        }
    }
    
    function updateLanguageUI() {
        enBtn.classList.toggle('active', selectedLanguage === 'en');
        arBtn.classList.toggle('active', selectedLanguage === 'ar');
        
        // Update direction based on language
        document.body.dir = selectedLanguage === 'ar' ? 'rtl' : 'ltr';
        
        // Update placeholder text
        userInput.placeholder = selectedLanguage === 'en'
            ? 'Type your message...'
            : 'اكتب رسالتك...';
            
        // Update End Chat button text
        endChatBtn.innerHTML = selectedLanguage === 'en'
            ? '<i class="fas fa-times-circle"></i> End Chat'
            : '<i class="fas fa-times-circle"></i> إنهاء المحادثة';
            
        // Update History button text
        historyBtn.innerHTML = selectedLanguage === 'en'
            ? '<i class="fas fa-history"></i> History'
            : '<i class="fas fa-history"></i> السجل';
    }
    
    // Helper functions for generating IDs
    function generatePatientId() {
        return 'p_' + Math.random().toString(36).substring(2, 10);
    }
    
    function generateChatId() {
        return 'c_' + Date.now().toString(36);
    }
});
