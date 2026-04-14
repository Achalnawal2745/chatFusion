---
title: ChatFusion
emoji: ⚡
colorFrom: purple
colorTo: blue
sdk: docker
pinned: false
short_description: Multi-source RAG workspace
---

# ⚡ ChatFusion

An AI-powered **Knowledge Workspace** that lets you have intelligent conversations with — and **combine knowledge from** — YouTube videos and PDF documents. Built on Retrieval Augmented Generation (RAG) with local embeddings for blazing-fast performance and a stunning glassmorphism UI.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)
![Gemini](https://img.shields.io/badge/Gemini-Flash%20Lite-orange.svg)
![Sentence-Transformers](https://img.shields.io/badge/Sentence--Transformers-Local-green.svg)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.0-38bdf8.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ Features

- 🎥 **YouTube Videos** — Extract and analyze video transcripts automatically
- 📄 **PDF Documents** — Upload and query any PDF document
- 🧠 **Knowledge Workspaces** — Merge multiple documents (PDFs + Videos) into a unified AI brain and chat across all of them at once
- ⚡ **Local Embeddings** — 10x faster processing with Sentence Transformers, no embedding API costs
- 🔍 **RAG Technology** — ChromaDB vector database for intelligent, precise context retrieval
- 💬 **Multi-source Synthesis** — AI seamlessly weaves knowledge from all merged sources to answer questions comprehensively
- 📊 **Source Attribution** — Every AI answer shows exactly which documents and chunks were used
- 🌍 **Multi-language Support** — Works with Hindi, English, and other languages
- 🎨 **Glassmorphism UI** — Premium dark-mode interface with neon purple/cyan accents designed with Stitch
- 💾 **Persistent Storage** — All documents and workspaces survive server restarts via `registry.json`

## 🆕 What's New: Knowledge Workspaces

The standout feature of ChatFusion is **Knowledge Workspaces** — a multi-source synthesis engine.

**Scenario**: You have a PDF tutorial and a YouTube lecture on the same topic. Instead of chatting with each one separately, you can:
1. Create a **Workspace** that merges both documents.
2. Ask any question — the AI synthesizes a unified, comprehensive answer drawing from both sources at once.
3. Results include a **Sources Used** panel showing exactly which document contributed which knowledge.

**Example queries that work beautifully across merged sources:**
- "Solve Question 6 from the tutorial using steps from the video explanation."
- "What is the theory from the PDF, and how does the video's approach apply to it?"
- "Give me a combined summary of both resources."

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Google Gemini API key ([Get one free](https://aistudio.google.com/apikey))
- ~500MB RAM for the embedding model

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Achalnawal2745/chatfusion.git
   cd chatfusion
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   On first run, Sentence Transformers will download the model (~90MB) automatically.

3. **Set up your API key**
   
   Create a `.env` file in the project root:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```

### Running the Application

1. **Start the backend server**
   ```bash
   python app.py
   ```
   
   You should see:
   ```
   Loading Sentence Transformer model...
   Model loaded successfully!
   * Running on http://127.0.0.1:5000
   ```

2. **Open your browser**
   
   Navigate to [http://localhost:5000](http://localhost:5000) — the Flask server directly serves the frontend.

3. **Start using ChatFusion!**
   - Click **+ Add Document** to process a YouTube URL or upload a PDF.
   - Your documents appear instantly in the left sidebar — click any to start chatting.
   - Click the **+** icon next to "Workspaces" to merge multiple documents into a unified Knowledge Workspace.

## 📖 How It Works

### Single Document Chat
```
YouTube URL / PDF Upload → Text Extraction → Chunking
→ Local Embeddings → ChromaDB Storage → Chat Interface
```

### Knowledge Workspace (Multi-source)
```
Select Documents → Instant Merge (re-uses existing embeddings)
→ Combined Collection → User Query → Parallel Retrieval from all sources
→ Gemini Synthesis Engine → Unified Answer with Source Attribution
```

### The Synthesis Protocol
When chatting with a Workspace, a specialized prompt instructs Gemini to:
1. Treat all sources as a single unified knowledge base.
2. Seamlessly blend and cross-reference information across documents.
3. Be comprehensive — never artificially shorten or suppress valuable detail.
4. Organically attribute sources within the narrative (not just list them).
5. Handle simple greetings conversationally, not with full document summaries.

**Key Technical Steps:**
1. **Content Processing**: Extract text from videos (transcripts) or PDFs
2. **Chunking**: Split into segments with overlap (configurable)
3. **Local Embeddings**: Convert to vectors using `all-MiniLM-L6-v2` (instant, free)
4. **Storage**: ChromaDB (`chroma_db/` folder) + `registry.json` for metadata persistence
5. **Query**: Embed user question locally → find relevant chunks across all collections
6. **Response**: `gemini-2.5-flash-lite` generates answers from retrieved context

## ⚡ Performance

### Processing Speed

| Content | Processing Time | Chunks |
|---------|-----------------|--------|
| 5-min video | ~15s | 10–12 |
| 20-min video | ~60s | 30–40 |
| 10-page PDF | ~10s | 15–20 |
| Workspace creation | ~instant | merged |

**10x faster** than API-based embeddings with no rate limits on processing!

## 🎯 Usage Tips

### Adding Content
- ✅ YouTube videos with auto-generated or manual captions
- ✅ PDF documents (text-based; scanned PDFs may have limited extraction)
- ✅ Multiple documents of different types — mix freely in one Workspace
- ❌ Videos without any captions (no transcript = no content)

### Asking Questions
- **Specific Questions**: "Explain NFA epsilon transitions" → precise answer from the right chunks.
- **Cross-source**: "Using the video's method, solve Question 6 from the PDF."
- **Summaries**: "Give me a combined overview of both documents."
- **Calculations / Proofs**: The AI will reproduce full step-by-step working — it won't skip steps.

## 🌍 Language Support

The app supports multiple languages with this priority:
1. **Hindi** (`hi`) — Tried first
2. **English** (`en`) — Fallback
3. **Any available** — Uses whatever transcript exists

You can ask questions in any language, and Gemini will respond accordingly!

## ⚙️ Configuration

### Embedding Model

**Model**: `all-MiniLM-L6-v2` (Sentence Transformers)
- **Size**: ~90MB
- **Quality**: Excellent for semantic search
- **Speed**: Very fast on CPU
- **Location**: Auto-downloaded to `~/.cache/torch/sentence_transformers/`

### Chat Model

**Model**: `gemini-2.5-flash-lite` (Google Gemini)
- Used for both single-document chat and multi-source workspace synthesis
- **Free tier rate limit**: ~15 requests per minute
- **Usage**: Chat responses only — embeddings are fully local

### Persistence

| Data | Storage |
|------|---------|
| Document vectors | `chroma_db/` (ChromaDB) |
| Document + workspace metadata | `registry.json` (auto-created) |
| Chat history per session | Browser `localStorage` |

### Environment Variables

Create a `.env` file:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

## 🐛 Troubleshooting

### "No transcript found"
- **Cause**: Video doesn't have captions
- **Solution**: Try a different video with captions enabled

### "503 UNAVAILABLE" from Gemini
- **Cause**: Temporary high load on Gemini's servers (free tier)
- **Solution**: Wait a few seconds and retry — the UI will show a friendly error message

### Model download fails
- **Cause**: Network issues or disk space
- **Solution**: Ensure stable internet and ~500MB free space

### Port 5000 already in use
```bash
# Windows
netstat -ano | findstr :5000
taskkill /F /PID <PID>

# Linux/Mac
lsof -ti:5000 | xargs kill -9
```

### Server won't start
- Check if `.env` file exists with valid API key
- Ensure all dependencies are installed
- Try reinstalling: `pip install -r requirements.txt --force-reinstall`

## 📁 Project Structure

```
chatfusion/
├── app.py              # Flask backend: RAG logic, workspace endpoints, registry persistence
├── index.html          # Frontend — glassmorphism UI (Tailwind CSS, Stitch-generated)
├── script.js           # Frontend JS: sidebar, modals, chat rendering, API calls
├── registry.json       # Persistent metadata for docs & workspaces (auto-created)
├── requirements.txt    # Python dependencies
├── .env               # API key (create this)
├── .env.example       # Template for .env
├── .gitignore         # Git ignore rules
├── chroma_db/         # Vector database (auto-created)
├── uploads/           # Temporary PDF storage (auto-created)
└── README.md          # Full documentation
```

> `style.css` has been superseded by Tailwind CSS embedded in `index.html`.
> `download.py` and `build_index.py` are utility scripts used during UI generation — not needed at runtime.

## 🔒 Security & Privacy

- ✅ `.env` file is gitignored (API key protected)
- ✅ **Embeddings processed locally** (transcripts/PDFs never sent to Gemini)
- ✅ Only retrieved context chunks sent to Gemini for chat responses
- ✅ CORS enabled for local development
- ⚠️ For production: restrict CORS, use HTTPS, add authentication
- ⚠️ Free tier Gemini may use submitted data for model improvement

## 🛠️ Technologies Used

| Component | Technology |
|-----------|-----------|
| Backend | Flask (Python) |
| Embeddings | Sentence Transformers (`all-MiniLM-L6-v2`) — Local |
| Vector Database | ChromaDB |
| AI Chat & Synthesis | Google Gemini API (`gemini-2.5-flash-lite`) |
| Transcript API | youtube-transcript-api |
| Frontend | Tailwind CSS (via CDN), Vanilla JS |
| UI Design System | Stitch (Google) — "Aether Glass" dark theme |
| Fonts | Space Grotesk + Inter (Google Fonts) |

## 📊 API Endpoints

### `POST /api/process-video`
Process a YouTube video and create embeddings.
```json
{ "url": "https://www.youtube.com/watch?v=..." }
```

### `POST /api/process-pdf`
Upload and process a PDF file (multipart/form-data).

### `GET /api/documents`
Returns all processed documents with metadata.

### `DELETE /api/document/<id>`
Deletes a document and its embeddings.

### `POST /api/chat`
Chat with a single document.
```json
{ "document_id": "...", "question": "What is this about?" }
```

### `POST /api/workspace/create`
Create a new Knowledge Workspace from existing documents.
```json
{ "name": "My Study Brain", "document_ids": ["id1", "id2"] }
```

### `POST /api/workspace/chat`
Chat with a merged Knowledge Workspace.
```json
{ "workspace_id": "...", "question": "Synthesize both sources on NFA." }
```

### `GET /api/workspaces`
Returns all workspaces with metadata.

### `DELETE /api/workspace/<id>`
Deletes a workspace (original documents are preserved).

### `GET /api/health`
Health check endpoint.

## 🎨 UI Features

- ✨ Premium glassmorphism dark mode with purple/cyan neon accents
- 📌 Persistent left sidebar with instant document & workspace switching
- 🗂️ Animated modals for adding documents and creating workspaces
- 💬 Styled chat bubbles with AI identity header ("Synthesizing Intelligence")
- 📊 Expandable "Sources Used" pills under workspace AI responses
- 📱 Responsive — collapsible sidebar with slide-in overlay on mobile
- 🔄 Persistent chat history per document via `localStorage`
- ⌨️ Enter key to send messages

## 📈 Future Enhancements

- [ ] Chat history export to Markdown or PDF
- [ ] OCR support for scanned (image-based) PDFs
- [ ] Document-level weightings in workspaces (prioritize specific sources)
- [ ] Auto-generated summaries on document upload
- [ ] Clickable timestamps in YouTube answers
- [ ] Workspace editing (add/remove documents post-creation)
- [ ] Move to paid Gemini tier to eliminate rate-limit interruptions

## 💡 Why Local Embeddings?

### Benefits over API-based embeddings:
- ⚡ **10x faster** — No network latency or rate limits
- 💰 **Free forever** — No API costs for embeddings
- 🔒 **More private** — Your content stays on your machine
- 🌐 **Works offline** — After initial model download
- ∞ **Unlimited** — Process as many documents as you want

### Trade-offs:
- 📦 ~90MB model download (one-time, automatic)
- 💻 ~500MB RAM usage
- 🎯 Slightly lower quality than Gemini embeddings (still excellent for RAG!)

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

**Made with ❤️ using Sentence Transformers, Google Gemini AI & Stitch**

**Star ⭐ this project if you find it useful!**
