// API Configuration
const API_BASE_URL = 'http://localhost:5000/api';

// State
let currentDocumentId = null;
let documents = [];

// DOM Elements
const tabs = document.querySelectorAll('.tab-btn');
const tabPanes = document.querySelectorAll('.tab-pane');
const videoUrl = document.getElementById('videoUrl');
const processVideoBtn = document.getElementById('processVideoBtn');
const videoStatus = document.getElementById('videoStatus');
const pdfFile = document.getElementById('pdfFile');
const uploadBtn = document.getElementById('uploadBtn');
const uploadArea = document.getElementById('uploadArea');
const pdfStatus = document.getElementById('pdfStatus');
const documentsList = document.getElementById('documentsList');
const chatSection = document.getElementById('chatSection');
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const newDocBtn = document.getElementById('newDocBtn');
const currentDocName = document.getElementById('currentDocName');
const docCount = document.getElementById('doc-count');

// Tab Switching
tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const tabName = tab.dataset.tab;

        // Update active tab
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        // Update active pane
        tabPanes.forEach(pane => pane.classList.remove('active'));
        document.getElementById(`${tabName}-tab`).classList.add('active');

        // Load documents if documents tab
        if (tabName === 'documents') {
            loadDocuments();
        }
    });
});

// YouTube Processing
processVideoBtn.addEventListener('click', processVideo);

async function processVideo() {
    const url = videoUrl.value.trim();
    if (!url) {
        showStatus(videoStatus, 'Please enter a YouTube URL', 'error');
        return;
    }

    processVideoBtn.disabled = true;
    processVideoBtn.querySelector('.btn-text').style.display = 'none';
    processVideoBtn.querySelector('.btn-loader').style.display = 'inline';
    showStatus(videoStatus, 'Processing video... This may take 30-60 seconds.', 'info');

    try {
        const response = await fetch(`${API_BASE_URL}/process-video`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to process video');
        }

        currentDocumentId = data.document_id;
        showStatus(videoStatus, `✓ Video processed! Created ${data.chunks_created} chunks.`, 'success');

        setTimeout(() => {
            showChat(data.document_id, `YouTube Video`);
            loadDocuments();
        }, 1500);

    } catch (error) {
        showStatus(videoStatus, `Error: ${error.message}`, 'error');
    } finally {
        processVideoBtn.disabled = false;
        processVideoBtn.querySelector('.btn-text').style.display = 'inline';
        processVideoBtn.querySelector('.btn-loader').style.display = 'none';
    }
}

// PDF Upload
uploadBtn.addEventListener('click', () => pdfFile.click());
pdfFile.addEventListener('change', handleFileSelect);

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        pdfFile.files = files;
        handleFileSelect();
    }
});

async function handleFileSelect() {
    const file = pdfFile.files[0];
    if (!file) return;

    if (!file.name.endsWith('.pdf')) {
        showStatus(pdfStatus, 'Please select a PDF file', 'error');
        return;
    }

    showStatus(pdfStatus, `Processing ${file.name}... This may take 10-30 seconds.`, 'info');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE_URL}/process-pdf`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to process PDF');
        }

        currentDocumentId = data.document_id;
        showStatus(pdfStatus, `✓ PDF processed! Created ${data.chunks_created} chunks.`, 'success');

        setTimeout(() => {
            showChat(data.document_id, data.filename);
            loadDocuments();
        }, 1500);

    } catch (error) {
        showStatus(pdfStatus, `Error: ${error.message}`, 'error');
    }
}

// Load Documents
async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE_URL}/documents`);
        const data = await response.json();

        if (data.success) {
            documents = data.documents;
            docCount.textContent = documents.length;
            renderDocuments();
        }
    } catch (error) {
        console.error('Error loading documents:', error);
    }
}

function renderDocuments() {
    if (documents.length === 0) {
        documentsList.innerHTML = '<p class="empty-state">No documents processed yet</p>';
        return;
    }

    documentsList.innerHTML = documents.map(doc => `
        <div class="doc-card ${doc.id === currentDocumentId ? 'selected' : ''}" 
             onclick="selectDocument('${doc.id}', '${doc.name}')">
            <span class="doc-type ${doc.type}">${doc.type === 'youtube' ? '🎥 Video' : '📄 PDF'}</span>
            <h4>${doc.name}</h4>
            <p>${doc.chunks_count} chunks</p>
            <small>${new Date(doc.created_at).toLocaleDateString()}</small>
            <button class="btn btn-small" onclick="event.stopPropagation(); deleteDocument('${doc.id}')" 
                    style="margin-top: 10px; background: #ff4444; color: white;">Delete</button>
        </div>
    `).join('');
}

// Make functions globally accessible for onclick handlers
window.selectDocument = function (docId, docName) {
    currentDocumentId = docId;
    showChat(docId, docName);
    renderDocuments();
}

window.deleteDocument = async function (docId) {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
        const response = await fetch(`${API_BASE_URL}/document/${docId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            if (currentDocumentId === docId) {
                currentDocumentId = null;
                chatSection.style.display = 'none';
            }
            loadDocuments();
        }
    } catch (error) {
        console.error('Error deleting document:', error);
    }
}

// Chat Functions
function showChat(docId, docName) {
    currentDocumentId = docId;
    currentDocName.textContent = docName;
    chatSection.style.display = 'flex';

    // Load chat history for this document
    const chatHistory = loadChatHistory(docId);

    if (chatHistory && chatHistory.length > 0) {
        // Restore previous chat
        chatMessages.innerHTML = '';
        chatHistory.forEach(msg => {
            addMessage(msg.text, msg.sender, false); // false = don't save to history
        });
    } else {
        // Show welcome message
        chatMessages.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">💬</div>
                <h3>Ready to chat!</h3>
                <p>Ask me anything about this document</p>
            </div>
        `;
    }

    chatInput.value = '';
    chatInput.focus();
}

// Save chat history to localStorage
function saveChatHistory(docId, message, sender) {
    const key = `chat_history_${docId}`;
    let history = JSON.parse(localStorage.getItem(key) || '[]');
    history.push({ text: message, sender: sender, timestamp: Date.now() });

    // Keep only last 50 messages per document
    if (history.length > 50) {
        history = history.slice(-50);
    }

    localStorage.setItem(key, JSON.stringify(history));
}

// Load chat history from localStorage
function loadChatHistory(docId) {
    const key = `chat_history_${docId}`;
    return JSON.parse(localStorage.getItem(key) || '[]');
}

// Clear chat history for a document
function clearChatHistory(docId) {
    const key = `chat_history_${docId}`;
    localStorage.removeItem(key);
}

sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

async function sendMessage() {
    const question = chatInput.value.trim();
    if (!question || !currentDocumentId) return;

    addMessage(question, 'user');
    chatInput.value = '';

    const typingId = addTypingIndicator();

    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                document_id: currentDocumentId,
                question: question
            })
        });

        const data = await response.json();
        removeTypingIndicator(typingId);

        if (!response.ok) {
            throw new Error(data.error || 'Failed to get response');
        }

        addMessage(data.answer, 'ai');

    } catch (error) {
        removeTypingIndicator(typingId);
        let errorMsg = error.message;
        if (errorMsg.includes('RESOURCE_EXHAUSTED') || errorMsg.includes('Quota exceeded')) {
            errorMsg = '⚠️ API quota exceeded. Please wait a few minutes.';
        }
        addMessage(`Sorry, I encountered an error: ${errorMsg}`, 'ai');
    }
}

function addMessage(text, sender, saveToHistory = true) {
    const welcomeMsg = chatMessages.querySelector('.welcome-message');
    if (welcomeMsg) welcomeMsg.remove();

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = sender === 'user' ? '👤' : '🤖';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.style.whiteSpace = 'pre-wrap';
    contentDiv.textContent = text;

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Save to localStorage
    if (saveToHistory && currentDocumentId) {
        saveChatHistory(currentDocumentId, text, sender);
    }
}

function addTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message ai typing-indicator';
    typingDiv.id = 'typing-' + Date.now();

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = '🤖';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = '<div class="typing-dots"><span>.</span><span>.</span><span>.</span></div>';

    typingDiv.appendChild(avatar);
    typingDiv.appendChild(contentDiv);
    chatMessages.appendChild(typingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return typingDiv.id;
}

function removeTypingIndicator(id) {
    const typingDiv = document.getElementById(id);
    if (typingDiv) typingDiv.remove();
}

function showStatus(element, message, type) {
    element.textContent = message;
    element.className = `status-message ${type}`;
}

newDocBtn.addEventListener('click', () => {
    currentDocumentId = null;
    chatSection.style.display = 'none';
    tabs[0].click(); // Go to YouTube tab
});

// Clear chat button
const clearChatBtn = document.getElementById('clearChatBtn');
clearChatBtn.addEventListener('click', () => {
    if (!currentDocumentId) return;

    if (confirm('Clear chat history for this document?')) {
        clearChatHistory(currentDocumentId);
        chatMessages.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">💬</div>
                <h3>Chat cleared!</h3>
                <p>Start a new conversation</p>
            </div>
        `;
    }
});

// Load documents on page load
loadDocuments();

// Theme Toggle
const themeToggle = document.getElementById('themeToggle');
const themeIcon = document.querySelector('.theme-icon');

// Load saved theme
const savedTheme = localStorage.getItem('theme') || 'light';
if (savedTheme === 'dark') {
    document.body.classList.add('dark-mode');
    themeIcon.textContent = '☀️';
}

themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');

    // Update icon
    themeIcon.textContent = isDark ? '☀️' : '🌙';

    // Save preference
    localStorage.setItem('theme', isDark ? 'dark' : 'light');

    // Add rotation animation
    themeIcon.style.transform = 'rotate(360deg)';
    setTimeout(() => {
        themeIcon.style.transform = 'rotate(0deg)';
    }, 300);
});
