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

An AI-powered **Knowledge Workspace** that lets you have intelligent conversations with — and **combine knowledge from** — YouTube videos, PDF documents, and audio files. Built on Retrieval Augmented Generation (RAG) with local embeddings and local audio transcription for blazing-fast, cost-free performance and a stunning glassmorphism UI.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)
![Gemini](https://img.shields.io/badge/Gemini-Flash%20Lite-orange.svg)
![Whisper](https://img.shields.io/badge/Whisper-Local%20Transcription-yellow.svg)
![Sentence-Transformers](https://img.shields.io/badge/Sentence--Transformers-Local-green.svg)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.0-38bdf8.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ Features

- 🎥 **YouTube Videos** — Extract and analyze video transcripts automatically
- 📄 **PDF Documents** — Upload and query any PDF document
- 🎙️ **Audio Transcription** — Upload lecture recordings, podcasts, or any audio file — transcribed locally using faster-whisper (free, no API cost!)
- 🖼️ **Image OCR** — Extract text from diagrams, screenshots, or scanned pages automatically using EasyOCR.
- 📝 **Direct Context Notes** — Jot down manual text notes and index them into the AI brain.
- 🧠 **Knowledge Workspaces** — Merge multiple documents (PDFs + Videos + Audio + Images + Notes) into a unified AI brain and chat across all of them at once
- ➕ **Seamless Merging** — Add new documents directly to existing workspaces with a single click (non-destructive appending)
- ⚡ **Local Embeddings** — 10x faster processing with Sentence Transformers, no embedding API costs
- 🗣️ **Local Transcription** — Audio files transcribed on-device using OpenAI's Whisper model via faster-whisper — completely free and private
- 🔍 **RAG Technology** — ChromaDB vector database for intelligent, precise context retrieval
- 💬 **Multi-source Synthesis** — AI seamlessly weaves knowledge from all merged sources to answer questions comprehensively
- 📊 **Source Attribution** — Every AI answer shows exactly which documents and chunks were used
- 🌍 **Multi-language Support** — Works with Hindi, English, and 90+ languages (auto-detected for audio)
- 🎨 **Glassmorphism UI** — Premium dark-mode interface with neon purple/cyan accents designed with Stitch
- 💾 **Persistent Storage** — All documents and workspaces survive server restarts via `registry.json`

## 🆕 What's New

### 🎙️ Audio Transcription (v2)

Record your lectures, upload podcasts, or drop any audio file — ChatFusion transcribes it **100% locally** using faster-whisper and makes it fully searchable and chattable.

**Perfect for students:**
1. Record a lecture on your phone.
2. Upload the audio file (MP3, WAV, M4A, OGG, FLAC, AAC, WebM).
3. ChatFusion transcribes it locally (no API costs!), auto-detects the language.
4. Chat with your lecture — ask for explanations, summaries, or specific topics.
5. Merge it into a **Workspace** with your PDF notes for a unified study brain.

**Supported formats:** MP3, M4A, WAV, OGG, FLAC, AAC, WebM — up to 100MB.

### 🧠 Knowledge Workspaces

The standout feature of ChatFusion is **Knowledge Workspaces** — a multi-source synthesis engine.

**Scenario**: You have a PDF tutorial, a YouTube lecture, and an audio recording on the same topic. Instead of chatting with each one separately, you can:
1. Create a **Workspace** that merges all documents.
2. Add new knowledge directly into the workspace (Direct Notes, Images, URLs). These are **Universally Isolated**—they stay inside your workspace and won't clutter your global document list.
3. Every document added to a workspace functions as an **Independent Copy**. Deleting the original file from your computer or global list will *not* break your workspace.
4. Ask any question — the AI synthesizes a unified, comprehensive answer drawing from all sources at once.
5. Results include a **Sources Used** panel showing exactly which document contributed which knowledge.

**Example queries that work beautifully across merged sources:**
- "Solve Question 6 from the tutorial using steps from the video explanation."
- "What did the professor say in the lecture about topic X compared to the PDF notes?"
- "Give me a combined summary of all resources."

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Google Gemini API key ([Get one free](https://aistudio.google.com/apikey))
- ~1GB RAM for embedding + whisper models

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
   
   On first run, models will be downloaded automatically:
   - Sentence Transformers `all-MiniLM-L6-v2` (~90MB)
   - Whisper `base` model (~140MB)

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
   Sentence Transformer loaded!
   Loading Whisper model (base)... this may take a moment on first run...
   Whisper model loaded!
   * Running on http://127.0.0.1:5000
   ```

2. **Open your browser**
   
   Navigate to [http://localhost:5000](http://localhost:5000) — the Flask server directly serves the frontend.

3. **Start using ChatFusion!**
   - Click **+ Add Document** to process a YouTube URL, upload a PDF, or upload an audio file.
   - Your documents appear instantly in the left sidebar — click any to start chatting.
   - Click the **+** icon next to "Workspaces" to merge multiple documents into a unified Knowledge Workspace.
   - Hover any document and click the **➕ (Add to Workspace)** icon to seamlessly merge it into an already-created workspace.

## 📖 How It Works

### Single Document Chat
```
YouTube URL / PDF Upload / Audio Upload → Text Extraction / Transcription
→ Chunking → Local Embeddings → ChromaDB Storage → Chat Interface
```

### Audio Transcription Pipeline
```
Audio File → faster-whisper (local, CPU) → Language Auto-Detection
→ Full Transcript → Chunking → Embeddings → ChromaDB → Chat
```

### Knowledge Workspace (Multi-source)
```
Select Documents (PDFs + Videos + Audio) → Instant Merge (re-uses existing embeddings)
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
1. **Content Processing**: Extract text from videos (transcripts), PDFs, or audio (local Whisper transcription)
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
| 5-min audio file | ~30-60s | 5–10 |
| 30-min lecture recording | ~2-4 min | 20–30 |
| Workspace creation | ~instant | merged |

**10x faster** than API-based embeddings with no rate limits on processing!

## 🎯 Usage Tips

### Adding Content
- ✅ YouTube videos with auto-generated or manual captions
- ✅ PDF documents (text-based; scanned PDFs may have limited extraction)
- ✅ Audio files: MP3, M4A, WAV, OGG, FLAC, AAC, WebM (up to 100MB)
- ✅ Images: PNG, JPG, JPEG (uses local OCR)
- ✅ Text notes: direct manual entry
- ✅ Multiple documents of different types — mix freely in one Workspace
- ❌ Videos without any captions (no transcript = no content)

### Asking Questions
- **Specific Questions**: "Explain NFA epsilon transitions" → precise answer from the right chunks.
- **Cross-source**: "Using the video's method, solve Question 6 from the PDF."
- **Lecture Queries**: "What did the speaker say about machine learning in the audio?"
- **Summaries**: "Give me a combined overview of all documents."
- **Calculations / Proofs**: The AI will reproduce full step-by-step working — it won't skip steps.

## 🌍 Language Support

The app supports multiple languages:

**YouTube transcripts** — Priority order:
1. **Hindi** (`hi`) — Tried first
2. **English** (`en`) — Fallback
3. **Any available** — Uses whatever transcript exists

**Audio transcription** — Auto-detected from 90+ languages by Whisper. Works great with Hindi, English, Spanish, French, German, and many more.

You can ask questions in any language, and Gemini will respond accordingly!

## ⚙️ Configuration

### Embedding Model

**Model**: `all-MiniLM-L6-v2` (Sentence Transformers)
- **Size**: ~90MB
- **Quality**: Excellent for semantic search
- **Speed**: Very fast on CPU
- **Location**: Auto-downloaded to `~/.cache/torch/sentence_transformers/`

### Whisper Model (Audio Transcription)

**Model**: `base` (faster-whisper / OpenAI Whisper)
- **Size**: ~140MB
- **Quality**: Good accuracy for clear speech
- **Speed**: ~2x realtime on CPU
- **Location**: Auto-downloaded to `~/.cache/huggingface/hub/`
- **Upgrade options**: Change to `small` (~460MB) or `medium` (~1.5GB) for better accuracy

### Chat Model

**Model**: `gemini-2.5-flash-lite` (Google Gemini)
- Used for both single-document chat and multi-source workspace synthesis
- **Free tier rate limit**: ~15 requests per minute
- **Usage**: Chat responses only — embeddings and transcription are fully local

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

### "Could not extract any speech from the audio file"
- **Cause**: Audio file has no clear speech, or is too short
- **Solution**: Ensure the file contains clear spoken content and is at least a few seconds long

### "503 UNAVAILABLE" from Gemini
- **Cause**: Temporary high load on Gemini's servers (free tier)
- **Solution**: Wait a few seconds and retry — the UI will show a friendly error message

### Model download fails
- **Cause**: Network issues or disk space
- **Solution**: Ensure stable internet and ~500MB free space for all models

### Audio transcription is slow
- **Cause**: Running on CPU with a large audio file
- **Solution**: Use shorter audio clips, or upgrade to a machine with a GPU for faster processing. You can also try the `tiny` model for faster (but less accurate) transcription by editing `app.py`.

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
├── app.py              # Flask backend: RAG logic, audio transcription, workspace endpoints
├── index.html          # Frontend — glassmorphism UI (Tailwind CSS, Stitch-generated)
├── script.js           # Frontend JS: sidebar, modals, chat rendering, API calls
├── registry.json       # Persistent metadata for docs & workspaces (auto-created)
├── requirements.txt    # Python dependencies
├── .env               # API key (create this)
├── .gitignore         # Git ignore rules
├── Dockerfile         # Docker config for Hugging Face Spaces deployment
├── chroma_db/         # Vector database (auto-created)
├── uploads/           # Temporary file storage during processing (auto-cleaned)
└── README.md          # Full documentation
```

> `style.css` has been superseded by Tailwind CSS embedded in `index.html`.

## 🔒 Security & Privacy

- ✅ `.env` file is gitignored (API key protected)
- ✅ **Embeddings processed locally** (transcripts/PDFs never sent to Gemini for embedding)
- ✅ **Audio transcription runs locally** — your recordings never leave your machine
- ✅ Only retrieved context chunks sent to Gemini for chat responses
- ✅ Uploaded files are auto-deleted after processing
- ✅ CORS enabled for local development
- ⚠️ For production: restrict CORS, use HTTPS, add authentication
- ⚠️ Free tier Gemini may use submitted data for model improvement

## 🛠️ Technologies Used

| Component | Technology |
|-----------|-----------|
| Backend | Flask (Python) |
| Embeddings | Sentence Transformers (`all-MiniLM-L6-v2`) — Local |
| Audio Transcription | faster-whisper (OpenAI Whisper) — Local, Free |
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

### `POST /api/process-audio`
Upload and transcribe an audio file (multipart/form-data).
- **Supported formats**: MP3, M4A, WAV, OGG, FLAC, AAC, WebM
- **Max size**: 100MB
- **Transcription**: Local (faster-whisper), auto-detects language

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

### `POST /api/workspace/<workspace_id>/add-document`
Append an existing document's chunks into a previously created workspace (non-destructive).
```json
{ "document_id": "id3" }
```

### `POST /api/workspace/chat`
Chat with a merged Knowledge Workspace.
```json
{ "workspace_id": "...", "question": "Synthesize all sources on NFA." }
```

### `POST /api/rename`
Rename a document or workspace.
```json
{ "type": "document", "id": "...", "name": "New Name" }
```

### `GET /api/workspaces`
Returns all workspaces with metadata.

### `DELETE /api/workspace/<id>`
Deletes a workspace (original documents are preserved).

### `GET /api/health`
Health check endpoint.

## 🎨 UI Features

- ✨ Premium glassmorphism dark mode with purple/cyan/amber neon accents
- 📌 Persistent left sidebar with instant document & workspace switching
- 🗂️ Animated modals for adding documents and creating workspaces
- 🎙️ Audio upload with transcription progress indicator
- 💬 Styled chat bubbles with AI identity header ("Synthesizing Intelligence")
- 📊 Expandable "Sources Used" pills under workspace AI responses
- 🔖 Distinct icons per source type — 🎥 YouTube / 📄 PDF / 🎙️ Audio
- 📱 Responsive — collapsible sidebar with slide-in overlay on mobile
- 🔄 Persistent chat history per document via `localStorage`
- ✏️ Rename and delete documents/workspaces inline
- ⌨️ Enter key to send messages

## 📈 Future Enhancements

- [ ] 🎙️ Live in-browser recording (no file upload needed)
- [ ] 📝 One-click "Generate Notes" from any document
- [ ] 🃏 Auto-generated flashcards for exam revision
- [ ] 📊 Quiz mode — AI-generated MCQs to test your knowledge
- [ ] 📋 Export chat/notes to PDF or Markdown
- [ ] 🌐 Website/article URL → chattable document
- [ ] 🔗 Interactive mind maps from workspace content
- [ ] Chat history export to Markdown or PDF
- [ ] Document-level weightings in workspaces
- [ ] Clickable timestamps in YouTube answers
- [x] Workspace editing: Add new documents post-creation
- [x] Workspace editing: Seamless independent source copies
- [x] Image/slide upload with OCR text extraction

## 💡 Why Local Processing?

### Local Embeddings + Local Transcription:
- ⚡ **10x faster** — No network latency or rate limits
- 💰 **Free forever** — No API costs for embeddings or transcription
- 🔒 **More private** — Your content stays on your machine
- 🌐 **Works offline** — After initial model download (except for chat, which needs Gemini)
- ∞ **Unlimited** — Process as many documents and audio files as you want

### Trade-offs:
- 📦 ~230MB model downloads (one-time, automatic: 90MB embeddings + 140MB whisper)
- 💻 ~1GB RAM usage for both models
- 🎯 Slightly lower quality than cloud models (still excellent for RAG!)

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

**Made with ❤️ using Sentence Transformers, faster-whisper, Google Gemini AI & Stitch**

**Star ⭐ this project if you find it useful!**
