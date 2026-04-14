// API Configuration
const API_BASE_URL = '/api';

// State
let currentDocumentId = null;
let currentWorkspaceId = null;
let documents = [];
let workspaces = [];

// DOM Elements
const documentsList = document.getElementById('documentsList');
const workspacesList = document.getElementById('workspacesList');
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const chatFooter = document.getElementById('chatFooter');
const currentChatTitle = document.getElementById('currentChatTitle');
const currentChatType = document.getElementById('currentChatType');
const typingIndicator = document.getElementById('typingIndicator');

// Modals & Sidebar
const sidebar = document.getElementById('sidebar');
const menuBtn = document.getElementById('menuBtn');
const closeSidebarBtn = document.getElementById('closeSidebarBtn');
const mobileOverlay = document.getElementById('mobileOverlay');

const addDocModal = document.getElementById('addDocModal');
const addDocumentBtn = document.getElementById('addDocumentBtn');
const closeAddDocBtn = document.getElementById('closeAddDocBtn');
const addDocOverlay = document.getElementById('addDocOverlay');

const createWsModal = document.getElementById('createWsModal');
const createWorkspaceBtn = document.getElementById('createWorkspaceBtn');
const closeCreateWsBtn = document.getElementById('closeCreateWsBtn');
const createWsOverlay = document.getElementById('createWsOverlay');
const cancelWorkspaceBtn = document.getElementById('cancelWorkspaceBtn');
const confirmCreateWorkspaceBtn = document.getElementById('confirmCreateWorkspaceBtn');
const workspaceNameInput = document.getElementById('workspaceNameInput');
const workspaceDocsList = document.getElementById('workspaceDocsList');
const workspaceCreateStatus = document.getElementById('workspaceCreateStatus');

// Upload Elements
const videoUrl = document.getElementById('videoUrl');
const processVideoBtn = document.getElementById('processVideoBtn');
const videoStatus = document.getElementById('videoStatus');
const pdfFile = document.getElementById('pdfFile');
const uploadBtn = document.getElementById('uploadBtn');
const pdfStatus = document.getElementById('pdfStatus');

// --- Layout & Modals Logic ---
menuBtn.addEventListener('click', () => {
    sidebar.classList.remove('-translate-x-full');
    mobileOverlay.classList.remove('hidden');
});
const closeNav = () => {
    sidebar.classList.add('-translate-x-full');
    mobileOverlay.classList.add('hidden');
};
closeSidebarBtn.addEventListener('click', closeNav);
mobileOverlay.addEventListener('click', closeNav);

// Add Doc Modal
const openAddDoc = () => { addDocModal.classList.remove('hidden'); closeNav(); };
const closeAddDoc = () => { addDocModal.classList.add('hidden'); };
addDocumentBtn.addEventListener('click', openAddDoc);
closeAddDocBtn.addEventListener('click', closeAddDoc);
addDocOverlay.addEventListener('click', closeAddDoc);

// Create Workspace Modal
const openCreateWs = () => { 
    createWsModal.classList.remove('hidden'); 
    closeNav(); 
    populateWorkspaceDocSelector();
    workspaceNameInput.value = '';
    workspaceCreateStatus.classList.add('hidden');
    workspaceCreateStatus.className = 'text-xs mt-2 hidden';
};
const closeCreateWs = () => { createWsModal.classList.add('hidden'); };
createWorkspaceBtn.addEventListener('click', openCreateWs);
closeCreateWsBtn.addEventListener('click', closeCreateWs);
cancelWorkspaceBtn.addEventListener('click', closeCreateWs);
createWsOverlay.addEventListener('click', closeCreateWs);

// Status Helper
function showStatus(el, msg, isError = false) {
    el.textContent = msg;
    el.classList.remove('hidden');
    if(isError) {
        el.classList.add('text-red-400');
        el.classList.remove('text-secondary', 'text-primary');
    } else {
        el.classList.add('text-secondary');
        el.classList.remove('text-red-400');
    }
}

// --- Upload Logic ---
processVideoBtn.addEventListener('click', async () => {
    const url = videoUrl.value.trim();
    if (!url) { showStatus(videoStatus, 'Please enter a YouTube URL', true); return; }
    processVideoBtn.disabled = true; processVideoBtn.innerText = '⏳';
    showStatus(videoStatus, 'Processing video...', false);

    try {
        const response = await fetch(`${API_BASE_URL}/process-video`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Failed to process video');
        
        showStatus(videoStatus, `✓ Processed! ${data.chunks_created} chunks.`, false);
        setTimeout(() => { closeAddDoc(); loadDocuments(); window.selectDocument(data.document_id, 'YouTube Video'); }, 1500);
    } catch (e) {
        showStatus(videoStatus, `Error: ${e.message}`, true);
    } finally {
        processVideoBtn.disabled = false; processVideoBtn.innerText = 'Process';
    }
});

uploadBtn.addEventListener('click', () => pdfFile.click());
pdfFile.addEventListener('change', async () => {
    const file = pdfFile.files[0];
    if (!file) return;
    if (!file.name.endsWith('.pdf')) { showStatus(pdfStatus, 'Select a PDF.', true); return; }
    showStatus(pdfStatus, `Uploading ${file.name}...`, false);

    const formData = new FormData(); formData.append('file', file);
    try {
        const response = await fetch(`${API_BASE_URL}/process-pdf`, { method: 'POST', body: formData });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Failed to process PDF');
        
        showStatus(pdfStatus, `✓ Success!`, false);
        setTimeout(() => { closeAddDoc(); loadDocuments(); window.selectDocument(data.document_id, data.filename); }, 1500);
    } catch (e) {
        showStatus(pdfStatus, `Error: ${e.message}`, true);
    }
});

// --- Data Loading & Rendering ---
async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE_URL}/documents`);
        const data = await response.json();
        if(data.success) { documents = data.documents; renderDocuments(); }
    } catch (e) { console.error(e); }
}

async function loadWorkspaces() {
    try {
        const response = await fetch(`${API_BASE_URL}/workspaces`);
        const data = await response.json();
        if(data.success) { workspaces = data.workspaces; renderWorkspaces(); }
    } catch (e) { console.error(e); }
}

function renderDocuments() {
    if(documents.length === 0) {
        documentsList.innerHTML = `<div class="text-xs text-outline px-4 italic">No documents yet</div>`; return;
    }
    documentsList.innerHTML = documents.map(doc => {
        const isSel = doc.id === currentDocumentId;
        const icon = doc.type === 'youtube' ? 'smart_display' : 'description';
        const color = doc.type === 'youtube' ? 'text-red-400' : 'text-primary';
        const activeClass = isSel ? 'bg-gradient-to-r from-[#d0bcff]/10 to-transparent text-[#d0bcff] border-l-2 border-[#d0bcff]' : 'text-[#958ea0] hover:bg-[#2a2a2a] hover:text-white border-l-2 border-transparent';
        
        return `<div class="flex justify-between items-center group px-4 py-3 cursor-pointer transition-all ${activeClass}" onclick="selectDocument('${doc.id}', '${doc.name}')">
            <div class="flex items-center gap-4 truncate">
                <span class="material-symbols-outlined text-xl ${color}">${icon}</span>
                <span class="font-label text-sm tracking-wide truncate pr-2">${doc.name}</span>
            </div>
            <button class="material-symbols-outlined text-sm opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity" onclick="event.stopPropagation(); deleteDocument('${doc.id}')">delete</button>
        </div>`;
    }).join('');
}

function renderWorkspaces() {
    if(workspaces.length === 0) {
        workspacesList.innerHTML = `<div class="text-xs text-outline px-4 italic">No workspaces yet</div>`; return;
    }
    workspacesList.innerHTML = workspaces.map(ws => {
        const isSel = ws.id === currentWorkspaceId;
        const activeClass = isSel ? 'bg-gradient-to-r from-[#4cd7f6]/10 to-transparent text-[#4cd7f6] border-l-2 border-[#4cd7f6]' : 'text-[#958ea0] hover:bg-[#2a2a2a] hover:text-white border-l-2 border-transparent';
        return `<div class="flex justify-between items-center group px-4 py-3 cursor-pointer transition-all ${activeClass}" onclick="selectWorkspace('${ws.id}', '${ws.name}')">
            <div class="flex items-center gap-4 truncate">
                <span class="material-symbols-outlined text-xl text-secondary">grid_view</span>
                <span class="font-label text-sm tracking-wide truncate pr-2">${ws.name}</span>
            </div>
            <button class="material-symbols-outlined text-sm opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity" onclick="event.stopPropagation(); deleteWorkspace('${ws.id}')">delete</button>
        </div>`;
    }).join('');
}

// Workspace Creation
function populateWorkspaceDocSelector() {
    if(documents.length < 2) {
        workspaceDocsList.innerHTML = '<p class="text-xs text-outline">You need at least 2 documents.</p>';
        confirmCreateWorkspaceBtn.disabled = true; return;
    }
    confirmCreateWorkspaceBtn.disabled = false;
    workspaceDocsList.innerHTML = documents.map(doc => `
        <label class="flex items-center gap-2 px-2 py-1.5 hover:bg-surface-container rounded cursor-pointer group text-outline hover:text-white transition-colors">
            <input type="checkbox" value="${doc.id}" class="rounded border-outline-variant/30 text-primary focus:ring-primary bg-background">
            <span class="material-symbols-outlined text-sm ${doc.type === 'youtube' ? 'text-red-400' : 'text-primary'}">${doc.type === 'youtube' ? 'smart_display' : 'description'}</span>
            <span class="text-sm truncate flex-1">${doc.name}</span>
        </label>
    `).join('');
}

confirmCreateWorkspaceBtn.addEventListener('click', async () => {
    const name = workspaceNameInput.value.trim();
    if(!name) { showStatus(workspaceCreateStatus, 'Enter a name', true); return; }
    
    const checkboxes = workspaceDocsList.querySelectorAll('input[type="checkbox"]:checked');
    if(checkboxes.length < 2) { showStatus(workspaceCreateStatus, 'Select 2+ docs', true); return; }
    
    confirmCreateWorkspaceBtn.disabled = true;
    showStatus(workspaceCreateStatus, 'Creating...', false);
    
    try {
        const docIds = Array.from(checkboxes).map(c => c.value);
        const res = await fetch(`${API_BASE_URL}/workspace/create`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name, document_ids: docIds})});
        const data = await res.json();
        if(!res.ok) throw new Error(data.error);
        
        showStatus(workspaceCreateStatus, '✓ Created!');
        setTimeout(() => { closeCreateWs(); loadWorkspaces(); }, 1000);
    } catch(e) { showStatus(workspaceCreateStatus, `Error: ${e.message}`, true); }
    finally { confirmCreateWorkspaceBtn.disabled = false; }
});

// Deletion
window.deleteDocument = async (id) => {
    if(!confirm('Delete this document?')) return;
    try {
        await fetch(`${API_BASE_URL}/document/${id}`, {method: 'DELETE'});
        if(currentDocumentId === id) resetChat();
        loadDocuments();
    } catch(e) {}
}
window.deleteWorkspace = async (id) => {
    if(!confirm('Delete this workspace?')) return;
    try {
        await fetch(`${API_BASE_URL}/workspace/${id}`, {method: 'DELETE'});
        if(currentWorkspaceId === id) resetChat();
        loadWorkspaces();
    } catch(e) {}
}

function resetChat() {
    currentDocumentId = null; currentWorkspaceId = null;
    chatFooter.classList.add('hidden');
    currentChatTitle.textContent = "Select Document";
    currentChatType.textContent = "";
    chatMessages.innerHTML = `
        <div class="flex items-center justify-center h-full text-outline/50 flex-col gap-4">
            <span class="material-symbols-outlined text-6xl">chat_bubble</span>
            <p>Select a document or workspace to start chatting.</p>
        </div>
    `;
    renderDocuments(); renderWorkspaces();
}

// --- Chat Logic ---
window.selectDocument = (id, name) => {
    currentDocumentId = id; currentWorkspaceId = null;
    currentChatTitle.textContent = name;
    currentChatType.innerHTML = `<span class="text-primary flex items-center gap-1"><span class="material-symbols-outlined text-sm">description</span> Document</span>`;
    initChatView(id);
}
window.selectWorkspace = (id, name) => {
    currentWorkspaceId = id; currentDocumentId = null;
    currentChatTitle.textContent = name;
    currentChatType.innerHTML = `<span class="text-secondary flex items-center gap-1"><span class="material-symbols-outlined text-sm">grid_view</span> Workspace</span>`;
    initChatView(id);
}

function initChatView(id) {
    if(window.innerWidth < 768) closeNav();
    chatFooter.classList.remove('hidden');
    renderDocuments(); renderWorkspaces();
    chatMessages.innerHTML = '';
    
    // Load history
    const history = JSON.parse(localStorage.getItem(`chat_${id}`) || '[]');
    if(history.length > 0) {
        history.forEach(m => renderMessage(m.text, m.sender, m.sources));
    } else {
        chatMessages.innerHTML = `
            <div class="flex items-center justify-center h-48 text-outline/50 flex-col gap-4 animate-in fade-in zoom-in">
                <div class="w-16 h-16 rounded-full bg-surface-container-high border border-outline-variant/30 flex items-center justify-center shadow-lg">
                    <span class="material-symbols-outlined text-3xl text-primary">auto_awesome</span>
                </div>
                <p>Hello! Ask me questions about this context.</p>
            </div>
        `;
    }
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function saveHistory(text, sender, sources = null) {
    const activeId = currentWorkspaceId || currentDocumentId;
    if(!activeId) return;
    const history = JSON.parse(localStorage.getItem(`chat_${activeId}`) || '[]');
    history.push({text, sender, sources});
    localStorage.setItem(`chat_${activeId}`, JSON.stringify(history.slice(-50)));
}

function renderMessage(text, sender, sources = null) {
    // Remove blank state if exists
    if(chatMessages.querySelector('.h-48')) chatMessages.innerHTML = '';

    const el = document.createElement('div');
    if(sender === 'user') {
        el.className = "group flex flex-col items-end animate-in fade-in slide-in-from-right-4 duration-500 mb-8";
        el.innerHTML = `
            <div class="max-w-[85%] md:max-w-[70%] bg-surface-container-low border border-outline-variant/10 rounded-2xl rounded-tr-none px-6 py-4 shadow-[0_10px_30px_rgba(0,0,0,0.3)]">
                <p class="text-on-surface font-body leading-relaxed whitespace-pre-wrap">${text}</p>
            </div>
            <span class="mt-2 text-[10px] uppercase tracking-widest text-outline px-2">User</span>
        `;
    } else {
        el.className = "group relative flex flex-col items-start animate-in fade-in slide-in-from-left-4 duration-500 mb-8";
        
        let sourcesHtml = '';
        if(sources && sources.length > 0) {
            sourcesHtml = `
            <div class="mt-6 pt-4 border-t border-outline-variant/10">
                <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-container-highest/50 border border-outline-variant/20 hover:border-primary/40 transition-all cursor-default">
                    <span class="material-symbols-outlined text-primary text-xs">library_books</span>
                    <span class="font-label text-[10px] font-semibold tracking-wide uppercase text-on-surface">Sources Used</span>
                </div>
                <div class="mt-3 flex flex-wrap gap-2">
                    ${sources.map(s => `
                    <div class="flex items-center gap-1.5 px-2 py-1 rounded-md bg-surface-container-lowest border border-outline-variant/5 text-[11px] text-outline-variant">
                        <span class="material-symbols-outlined text-sm ${s.type === 'pdf' ? 'text-primary' : 'text-red-400'}">${s.type === 'pdf' ? 'description' : 'movie'}</span>
                        <span class="truncate max-w-[150px]">${s.name}</span>
                    </div>`).join('')}
                </div>
            </div>`;
        }

        el.innerHTML = `
            <div class="absolute -left-4 top-0 bottom-0 w-0.5 bg-secondary opacity-0 group-hover:opacity-100 transition-all duration-500 shadow-[0_0_15px_#4cd7f6]"></div>
            <div class="max-w-[95%] md:max-w-[85%] bg-surface-container/40 glass-panel border border-secondary/10 rounded-3xl rounded-tl-none p-6 md:p-8 shadow-[0_20px_50px_rgba(0,0,0,0.5)]">
                <div class="flex items-center gap-3 mb-4">
                    <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-[0_0_15px_rgba(76,215,246,0.3)] shrink-0">
                        <span class="material-symbols-outlined text-background font-bold text-lg">bolt</span>
                    </div>
                    <div>
                        <h3 class="font-headline font-bold text-[#d0bcff] text-sm md:text-base">Synthesizing Intelligence</h3>
                        <span class="text-[9px] md:text-[10px] uppercase tracking-widest text-secondary/60">ChatFusion Core</span>
                    </div>
                </div>
                <div class="text-on-surface-variant font-body leading-relaxed text-sm md:text-base whitespace-pre-wrap">${text}</div>
                ${sourcesHtml}
            </div>
        `;
    }
    chatMessages.appendChild(el);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

sendBtn.addEventListener('click', sendChat);
chatInput.addEventListener('keypress', (e) => { if(e.key === 'Enter') sendChat(); });

async function sendChat() {
    const q = chatInput.value.trim();
    if(!q || (!currentDocumentId && !currentWorkspaceId)) return;
    
    renderMessage(q, 'user');
    saveHistory(q, 'user');
    chatInput.value = '';
    
    typingIndicator.classList.remove('hidden');
    
    try {
        let endpoint = `${API_BASE_URL}/chat`;
        let payload = { question: q };
        if(currentWorkspaceId) {
            endpoint = `${API_BASE_URL}/workspace/chat`;
            payload.workspace_id = currentWorkspaceId;
        } else {
            payload.document_id = currentDocumentId;
        }
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        typingIndicator.classList.add('hidden');
        if(!response.ok) throw new Error(data.error);
        
        renderMessage(data.answer, 'ai', data.sources_used);
        saveHistory(data.answer, 'ai', data.sources_used);
        
    } catch(e) {
        typingIndicator.classList.add('hidden');
        renderMessage(`⚠️ Error: ${e.message}`, 'ai');
    }
}

// Init
loadDocuments();
loadWorkspaces();
