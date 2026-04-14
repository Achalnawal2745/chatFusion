import re

with open('stitch_index.html', 'r', encoding='utf-8') as f:
    stitch_content = f.read()

# Extract tailwind config and styles
tailwind_config_match = re.search(r'(<script id="tailwind-config">.*?</script>)', stitch_content, re.DOTALL)
styles_match = re.search(r'(<style>.*?</style>\s*<style>.*?</style>)', stitch_content, re.DOTALL)

tailwind_config = tailwind_config_match.group(1) if tailwind_config_match else ""
styles = styles_match.group(1) if styles_match else ""

html_template = f"""<!DOCTYPE html>
<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>ChatFusion | Knowledge Workspace</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
{tailwind_config}
{styles}
</head>
<body class="bg-background text-on-background font-body min-h-screen selection:bg-primary/30 selection:text-primary overflow-x-hidden">

<div class="fixed inset-0 bg-background/80 backdrop-blur-md z-[100] hidden" id="mobileOverlay"></div>

<!-- NavigationDrawer -->
<aside class="fixed inset-y-0 left-0 z-[110] flex flex-col p-4 w-72 bg-[#1c1b1b]/90 backdrop-blur-2xl shadow-[40px_0_60px_-15px_rgba(0,0,0,0.5)] transform -translate-x-full transition-transform duration-300 md:translate-x-0" id="sidebar">
    <div class="mb-10 px-4 flex justify-between items-center">
        <h1 class="font-headline font-bold text-[#d0bcff] text-2xl tracking-tight">ChatFusion</h1>
        <button id="closeSidebarBtn" class="md:hidden text-outline hover:text-white"><span class="material-symbols-outlined">close</span></button>
    </div>
    <nav class="flex-1 space-y-8 overflow-y-auto no-scrollbar">
        <!-- Dynamic Section: My Documents -->
        <div>
            <span class="block px-4 mb-4 font-label text-[10px] uppercase tracking-[0.2em] text-outline">My Documents</span>
            <div id="documentsList" class="space-y-1">
                <!-- Javascript will inject documents here -->
            </div>
        </div>
        <!-- Dynamic Section: Workspaces -->
        <div>
            <div class="flex justify-between items-center px-4 mb-4">
                <span class="block font-label text-[10px] uppercase tracking-[0.2em] text-outline">Workspaces</span>
                <button id="createWorkspaceBtn" class="text-primary hover:text-white"><span class="material-symbols-outlined text-xl">add_box</span></button>
            </div>
            <div id="workspacesList" class="space-y-1">
                <!-- Javascript will inject workspaces here -->
            </div>
        </div>
    </nav>
    <div class="mt-auto p-2">
        <button id="addDocumentBtn" class="w-full py-4 rounded-xl font-headline font-bold text-sm bg-gradient-to-r from-primary to-primary-container text-on-primary-container shadow-[0_0_20px_rgba(208,188,255,0.3)] hover:scale-[1.02] active:scale-95 transition-all flex items-center justify-center gap-2">
            <span class="material-symbols-outlined">add_circle</span>
            Add Document
        </button>
    </div>
</aside>

<!-- Main Content Canvas -->
<main class="md:ml-72 flex flex-col min-h-screen max-h-screen relative bg-surface overflow-hidden">
    <!-- TopAppBar -->
    <header class="absolute top-0 z-50 w-full flex justify-between items-center px-6 h-16 bg-[#131313]/80 backdrop-blur-xl tonal-transition shadow-[0_8px_32px_0_rgba(139,92,246,0.08)]">
        <div class="flex items-center gap-4">
            <button id="menuBtn" class="md:hidden text-[#d0bcff] active:scale-95 duration-200">
                <span class="material-symbols-outlined">menu</span>
            </button>
            <span id="currentChatTitle" class="font-headline tracking-tight text-xl font-bold bg-gradient-to-r from-[#d0bcff] to-[#a078ff] bg-clip-text text-transparent truncate max-w-[200px] md:max-w-full">Select a Document</span>
        </div>
        <div class="flex items-center gap-4">
            <span id="currentChatType" class="text-outline text-[10px] md:text-xs tracking-wider uppercase font-bold"></span>
        </div>
    </header>

    <!-- Chat Container -->
    <section class="flex-1 pt-24 pb-32 px-4 md:px-12 max-w-4xl mx-auto w-full space-y-12 overflow-y-auto no-scrollbar" id="chatMessages">
        <div class="flex items-center justify-center h-full text-outline/50 flex-col gap-4">
            <span class="material-symbols-outlined text-6xl">chat_bubble</span>
            <p>Select a document or workspace to start chatting.</p>
        </div>
    </section>

    <!-- Floating Message Input -->
    <footer id="chatFooter" class="absolute bottom-0 left-0 right-0 p-4 md:p-8 bg-gradient-to-t from-background via-background/90 to-transparent z-40 hidden">
        <div class="max-w-4xl mx-auto relative group">
            <div class="absolute -inset-1 bg-gradient-to-r from-primary/20 via-secondary/20 to-primary/20 rounded-2xl blur-lg opacity-30 group-focus-within:opacity-100 transition-opacity"></div>
            <div class="relative bg-surface-container-low glass-panel border border-outline-variant/20 rounded-2xl p-2 flex items-center gap-2 shadow-2xl">
                <input id="chatInput" class="flex-1 bg-transparent border-none outline-none focus:ring-0 text-on-surface font-body placeholder:text-outline/50 px-4 py-3 text-sm md:text-base" placeholder="Ask ChatFusion anything..." type="text"/>
                <button id="sendBtn" class="w-12 h-12 flex items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary-container shadow-[0_0_15px_rgba(208,188,255,0.4)] hover:shadow-[0_0_25px_rgba(208,188,255,0.6)] active:scale-95 transition-all outline-none">
                    <span class="material-symbols-outlined">send</span>
                </button>
            </div>
            <div id="typingIndicator" class="text-xs text-secondary mt-2 px-4 hidden font-bold">Synthesizing response...</div>
        </div>
    </footer>
</main>

<!-- Add Document Modal -->
<div id="addDocModal" class="fixed inset-0 z-[200] hidden items-center justify-center flex">
    <div class="absolute inset-0 bg-background/80 backdrop-blur-md" id="addDocOverlay"></div>
    <div class="relative w-[90%] max-w-lg bg-surface-container border border-outline-variant/20 rounded-2xl p-6 shadow-2xl animate-in fade-in zoom-in duration-200">
        <div class="flex justify-between items-center mb-6">
            <h2 class="font-headline text-xl text-primary font-bold">Add Document</h2>
            <button id="closeAddDocBtn" class="text-outline hover:text-white"><span class="material-symbols-outlined">close</span></button>
        </div>
        
        <div class="space-y-6">
            <!-- YouTube Input -->
            <div class="bg-surface-container-low p-4 rounded-xl border border-outline-variant/10">
                <h3 class="text-sm font-bold text-on-surface mb-2 flex items-center gap-2"><span class="material-symbols-outlined text-red-400">smart_display</span>YouTube Video</h3>
                <div class="flex gap-2 flex-col sm:flex-row">
                    <input type="text" id="videoUrl" class="flex-1 bg-surface border border-outline-variant/30 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary text-white" placeholder="Paste YouTube URL..."/>
                    <button id="processVideoBtn" class="bg-primary/20 text-primary hover:bg-primary hover:text-on-primary px-4 py-2 rounded-lg text-sm font-bold transition-all">Process</button>
                </div>
                <div id="videoStatus" class="mt-2 text-xs text-secondary hidden">Processing...</div>
            </div>

            <!-- PDF Upload -->
            <div class="bg-surface-container-low p-4 rounded-xl border border-outline-variant/10 pb-6 text-center">
                <h3 class="text-sm font-bold text-on-surface mb-2 flex flex-col items-center gap-2"><span class="material-symbols-outlined text-secondary text-3xl">upload_file</span>Upload PDF</h3>
                <p class="text-xs text-outline mb-4">Max size: 10MB</p>
                <input type="file" id="pdfFile" accept=".pdf" class="hidden" />
                <button id="uploadBtn" class="bg-secondary/20 text-secondary hover:bg-secondary hover:text-on-secondary px-6 py-2 rounded-lg text-sm font-bold transition-all">Choose PDF File</button>
                <div id="pdfStatus" class="mt-2 text-xs text-primary hidden">Uploading...</div>
            </div>
        </div>
    </div>
</div>

<!-- Create Workspace Modal -->
<div id="createWsModal" class="fixed inset-0 z-[200] hidden items-center justify-center flex">
    <div class="absolute inset-0 bg-background/80 backdrop-blur-md" id="createWsOverlay"></div>
    <div class="relative w-[90%] max-w-lg bg-surface-container border border-outline-variant/20 rounded-2xl p-6 shadow-2xl animate-in fade-in zoom-in duration-200">
        <div class="flex justify-between items-center mb-6">
            <h2 class="font-headline text-xl text-primary font-bold">Create Workspace</h2>
            <button id="closeCreateWsBtn" class="text-outline hover:text-white"><span class="material-symbols-outlined">close</span></button>
        </div>
        <p class="text-[11px] text-outline mb-4">Combine multiple documents into one unified AI brain.</p>
        
        <div class="space-y-4 flex flex-col">
            <input type="text" id="workspaceNameInput" class="w-full bg-surface border border-outline-variant/30 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary text-white" placeholder="Workspace Name (e.g. Deep Learning Study)"/>
            
            <div class="text-sm text-on-surface font-bold mt-2">Select documents to merge:</div>
            <div id="workspaceDocsList" class="bg-surface-container-low border border-outline-variant/10 rounded-xl p-3 max-h-48 overflow-y-auto flex flex-col space-y-2">
                <!-- Javascript fills this -->
            </div>
            
            <div id="workspaceCreateStatus" class="text-xs text-secondary mt-2 hidden">Creating workspace...</div>
            
            <div class="flex justify-end gap-3 mt-2">
                <button id="cancelWorkspaceBtn" class="text-outline hover:text-white px-4 py-2 text-sm font-bold">Cancel</button>
                <button id="confirmCreateWorkspaceBtn" class="bg-gradient-to-r from-primary to-primary-container text-on-primary-container px-6 py-2 rounded-lg text-sm font-bold transition-all shadow-[0_0_15px_rgba(208,188,255,0.4)] hover:scale-105 active:scale-95">Create</button>
            </div>
        </div>
    </div>
</div>

<script src="script.js"></script>
</body></html>
"""

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html_template)
