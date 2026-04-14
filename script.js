// API Configuration
const API_BASE_URL = 'http://localhost:5000/api';

// State
let currentDocumentId = null;
let currentWorkspaceId = null;
let documents = [];
let workspaces = [];

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

// Workspace DOM
const workspacesList = document.getElementById('workspacesList');
const createWorkspaceBtn = document.getElementById('createWorkspaceBtn');
const workspaceModal = document.getElementById('workspaceModal');
const closeWorkspaceModal = document.getElementById('closeWorkspaceModal');
const cancelWorkspaceBtn = document.getElementById('cancelWorkspaceBtn');
const confirmCreateWorkspaceBtn = document.getElementById('confirmCreateWorkspaceBtn');
const workspaceNameInput = document.getElementById('workspaceNameInput');
const workspaceDocsList = document.getElementById('workspaceDocsList');
const workspaceCreateStatus = document.getElementById('workspaceCreateStatus');

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
        } else if (tabName === 'workspaces') {
            loadWorkspaces();
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

// Workspace Logic
createWorkspaceBtn.addEventListener('click', () => {
    workspaceModal.style.display = 'block';
    populateWorkspaceDocSelector();
    workspaceNameInput.value = '';
    workspaceCreateStatus.textContent = '';
    workspaceCreateStatus.className = 'status-message';
});

function closeWorkspaceModalFn() {
    workspaceModal.style.display = 'none';
}
closeWorkspaceModal.addEventListener('click', closeWorkspaceModalFn);
cancelWorkspaceBtn.addEventListener('click', closeWorkspaceModalFn);

window.addEventListener('click', (e) => {
    if (e.target === workspaceModal) closeWorkspaceModalFn();
});

function populateWorkspaceDocSelector() {
    if (documents.length < 2) {
        workspaceDocsList.innerHTML = '<p class="empty-state" style="padding: 10px;">You need at least 2 processed documents to create a workspace.</p>';
        confirmCreateWorkspaceBtn.disabled = true;
        return;
    }
    
    confirmCreateWorkspaceBtn.disabled = false;
    workspaceDocsList.innerHTML = documents.map(doc => `
        <div class="doc-select-item">
            <input type="checkbox" id="ws_doc_${doc.id}" value="${doc.id}">
            <label for="ws_doc_${doc.id}">
                ${doc.type === 'youtube' ? '🎥' : '📄'} ${doc.name} 
                <small style="color: var(--text-secondary); margin-left: 10px;">(${doc.chunks_count} chunks)</small>
            </label>
        </div>
    `).join('');
}

confirmCreateWorkspaceBtn.addEventListener('click', async () => {
    const name = workspaceNameInput.value.trim();
    if (!name) {
        showStatus(workspaceCreateStatus, 'Please enter a workspace name', 'error');
        return;
    }
    
    const selectedCheckboxes = workspaceDocsList.querySelectorAll('input[type="checkbox"]:checked');
    if (selectedCheckboxes.length < 2) {
        showStatus(workspaceCreateStatus, 'Please select at least 2 documents', 'error');
        return;
    }
    
    const documentIds = Array.from(selectedCheckboxes).map(cb => cb.value);
    
    confirmCreateWorkspaceBtn.disabled = true;
    confirmCreateWorkspaceBtn.querySelector('.btn-text').style.display = 'none';
    confirmCreateWorkspaceBtn.querySelector('.btn-loader').style.display = 'inline';
    showStatus(workspaceCreateStatus, 'Merging documents... (This is instant!)', 'info');
    
    try {
        const response = await fetch(`${API_BASE_URL}/workspace/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, document_ids: documentIds })
        });
        
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Failed to create workspace');
        
        showStatus(workspaceCreateStatus, '✓ Workspace created successfully!', 'success');
        
        setTimeout(() => {
            closeWorkspaceModalFn();
            loadWorkspaces();
        }, 1000);
        
    } catch (error) {
        showStatus(workspaceCreateStatus, `Error: ${error.message}`, 'error');
    } finally {
        confirmCreateWorkspaceBtn.disabled = false;
        confirmCreateWorkspaceBtn.querySelector('.btn-text').style.display = 'inline';
        confirmCreateWorkspaceBtn.querySelector('.btn-loader').style.display = 'none';
    }
});

async function loadWorkspaces() {
    try {
        const response = await fetch(`${API_BASE_URL}/workspaces`);
        const data = await response.json();
        if (data.success) {
            workspaces = data.workspaces;
            renderWorkspaces();
        }
    } catch (error) {
        console.error('Error loading workspaces:', error);
    }
}

function renderWorkspaces() {
    if (workspaces.length === 0) {
        workspacesList.innerHTML = '<p class="empty-state">No workspaces created yet. A workspace lets you merge multiple documents into one unified brain!</p>';
        return;
    }
    
    workspacesList.innerHTML = workspaces.map(ws => `
        <div class="doc-card ${ws.id === currentWorkspaceId ? 'selected' : ''}" 
             onclick="selectWorkspace('${ws.id}', '${ws.name}')">
            <span class="doc-type" style="background: #764ba2; color: white;">🧠 Workspace</span>
            <h4>${ws.name}</h4>
            <p>${ws.document_ids.length} docs • ${ws.total_chunks} chunks</p>
            <small>Merged Knowledge Space</small>
            <button class="btn btn-small" onclick="event.stopPropagation(); deleteWorkspace('${ws.id}')" 
                    style="margin-top: 10px; background: #ff4444; color: white;">Delete</button>
        </div>
    `).join('');
}

// Make functions globally accessible for onclick handlers
window.selectDocument = function (docId, docName) {
    currentDocumentId = docId;
    currentWorkspaceId = null;
    showChat(docId, docName, false);
    renderDocuments();
    renderWorkspaces();
}

window.selectWorkspace = function (wsId, wsName) {
    currentWorkspaceId = wsId;
    currentDocumentId = null;
    showChat(wsId, wsName, true);
    renderDocuments();
    renderWorkspaces();
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

window.deleteWorkspace = async function (wsId) {
    if (!confirm('Delete this workspace? (Original documents won\'t be affected)')) return;
    try {
        const response = await fetch(`${API_BASE_URL}/workspace/${wsId}`, {
            method: 'DELETE'
        });
        if (response.ok) {
            if (currentWorkspaceId === wsId) {
                currentWorkspaceId = null;
                chatSection.style.display = 'none';
            }
            loadWorkspaces();
        }
    } catch (error) {
        console.error('Error deleting workspace:', error);
    }
}

// Chat Functions
function showChat(id, name, isWorkspace) {
    if (isWorkspace) {
        currentDocName.innerHTML = `🧠 <span style="margin-left:8px;">${name} (Merged Brain)</span>`;
    } else {
        currentDocName.innerHTML = `📄 <span style="margin-left:8px;">${name}</span>`;
    }
    chatSection.style.display = 'flex';

    // Load chat history for this document/workspace
    const chatHistory = loadChatHistory(id);

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
    if (!question || (!currentDocumentId && !currentWorkspaceId)) return;

    addMessage(question, 'user');
    chatInput.value = '';

    const typingId = addTypingIndicator();

    try {
        let endpoint = `${API_BASE_URL}/chat`;
        let payload = { question: question };

        if (currentWorkspaceId) {
            endpoint = `${API_BASE_URL}/workspace/chat`;
            payload.workspace_id = currentWorkspaceId;
        } else {
            payload.document_id = currentDocumentId;
        }

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        removeTypingIndicator(typingId);

        if (!response.ok) {
            throw new Error(data.error || 'Failed to get response');
        }

        addMessage(data.answer, 'ai');

        if (currentWorkspaceId && data.sources_used && data.sources_used.length > 0) {
            const lastMsg = chatMessages.lastElementChild.querySelector('.message-content');
            if (lastMsg) {
                const panel = document.createElement('div');
                panel.className = 'sources-used-panel';
                panel.innerHTML = `
                    <h4>📊 Knowledge Used from:</h4>
                    <ul style="list-style-type: none; margin-left: 5px;">
                        ${data.sources_used.map(s => `<li style="margin-bottom: 3px;">${s.type === 'pdf' ? '📄' : '🎥'} ${s.name} <span style="color:var(--text-secondary);font-size:0.8rem">(${s.chunks_used} matching chunks)</span></li>`).join('')}
                    </ul>
                `;
                lastMsg.appendChild(panel);
            }
        }

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
    const activeId = currentWorkspaceId || currentDocumentId;
    if (saveToHistory && activeId) {
        saveChatHistory(activeId, text, sender);
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
    currentWorkspaceId = null;
    chatSection.style.display = 'none';
    tabs[0].click(); // Go to YouTube tab
});

// Clear chat button
const clearChatBtn = document.getElementById('clearChatBtn');
clearChatBtn.addEventListener('click', () => {
    const activeId = currentWorkspaceId || currentDocumentId;
    if (!activeId) return;

    if (confirm('Clear chat history?')) {
        clearChatHistory(activeId);
        chatMessages.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">💬</div>
                <h3>Chat cleared!</h3>
                <p>Start a new conversation</p>
            </div>
        `;
    }
});

// Load documents and workspaces on page load
loadDocuments();
loadWorkspaces();

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
