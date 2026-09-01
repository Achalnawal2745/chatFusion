import os
import sys
import threading

# Force unbuffered/line-buffered stdout so logs show in real time in Hugging Face / Gunicorn
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

# Suppress TensorFlow warnings and info messages
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=all, 1=filter INFO, 2=filter WARNING, 3=filter ERROR

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from google import genai
from google.genai import types
import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
import re
from urllib.parse import urlparse, parse_qs
import PyPDF2
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
import numpy as np
import cv2

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure Gemini API (only for chat, not embeddings)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("⚠️ WARNING: GEMINI_API_KEY not found in environment variables. Chat endpoints will require an API key.")
    client = None
else:
    client = genai.Client(api_key=GEMINI_API_KEY)


# Lazy Model Proxy to prevent slow synchronous startup, Gunicorn timeouts, and high idle memory
class LazyModelProxy:
    """Delays model loading and downloading until the first time it is actually needed."""
    def __init__(self, loader, name="Model"):
        self._loader = loader
        self._name = name
        self._instance = None
        self._lock = threading.Lock()

    def _get_instance(self):
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    print(f"Loading {self._name}...")
                    self._instance = self._loader()
                    print(f"✅ {self._name} loaded successfully!")
        return self._instance

    def __getattr__(self, name):
        return getattr(self._get_instance(), name)


def _load_sentence_transformer():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer('all-MiniLM-L6-v2')


def _load_whisper_model():
    from faster_whisper import WhisperModel
    # 'base' = ~140MB download, good speed/accuracy
    return WhisperModel("base", device="cpu", compute_type="int8")


def _load_ocr_reader():
    import easyocr
    return easyocr.Reader(['en'], gpu=False)


# Initialize lazy proxies
embedding_model = LazyModelProxy(_load_sentence_transformer, "Sentence Transformer (all-MiniLM-L6-v2)")
whisper_model = LazyModelProxy(_load_whisper_model, "faster-whisper (base)")
ocr_reader = LazyModelProxy(_load_ocr_reader, "EasyOCR (en)")

def _warmup_embedding_model():
    """Warm up sentence-transformer in background so the first user request is instant."""
    import time
    time.sleep(2)
    try:
        print("🔥 [warmup] Pre-warming embedding model in background...", flush=True)
        embedding_model.encode(["warmup query"])
        print("✅ [warmup] Embedding model is ready in RAM!", flush=True)
    except Exception as w_err:
        print(f"⚠️ [warmup] Background warmup note: {w_err}", flush=True)

threading.Thread(target=_warmup_embedding_model, daemon=True).start()

# Initialize ChromaDB with persistent storage
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Configure file uploads
UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'webp'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'm4a', 'wav', 'ogg', 'flac', 'aac', 'weba', 'webm'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB (for audio files)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

import json

REGISTRY_FILE = 'registry.json'

# Unified document registry (videos + PDFs)
documents_registry = {}

# Knowledge workspaces registry
workspaces = {}

def load_registry():
    global documents_registry, workspaces
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, 'r') as f:
                data = json.load(f)
                # Try all possible key names for documents
                documents_registry = data.get('documents') or data.get('sources') or {}
                
                # Try all possible key names for workspaces
                # Priority: 'workspaces' (new), then 'personal_spaces' (reverted style), then 'spaces'
                workspaces = data.get('workspaces') or data.get('personal_spaces') or data.get('spaces') or {}
                
                # Patch existing orphaned sources that are in workspaces
                try:
                    patched = False
                    for ws_id, ws in workspaces.items():
                        # Auto-upgrade older workspaces with independent sources array
                        if 'sources' not in ws:
                            ws['sources'] = []
                            patched = True
                        
                        existing_source_ids = [s['id'] for s in ws['sources']]
                        
                        for doc_id in ws.get('document_ids', []):
                            if doc_id in documents_registry:
                                doc = documents_registry[doc_id]
                                
                                # Protect source lists so global delete doesn't break them
                                if doc_id not in existing_source_ids:
                                    ws['sources'].append({
                                        'id': doc['id'],
                                        'name': doc.get('name', 'Unknown'),
                                        'type': doc.get('type', 'unknown')
                                    })
                                    patched = True
                                
                                # Isolate workspace-exclusive documents from global view
                                if not doc.get('parent_workspace_id'):
                                    doc['parent_workspace_id'] = ws_id
                                    patched = True
                                    print(f"🩹 Patched orphan source {doc_id} to workspace {ws_id}")
                    if patched:
                        save_registry()
                except Exception as e:
                    print(f"Warning: Registry patch failed: {str(e)}")

                print(f"Loaded {len(documents_registry)} documents and {len(workspaces)} workspaces.")
        except Exception as e:
            print(f"Error loading registry: {e}")

def save_registry():
    try:
        with open(REGISTRY_FILE, 'w') as f:
            json.dump({
                'documents': documents_registry,
                'workspaces': workspaces
            }, f, indent=4)
    except Exception as e:
        print(f"Error saving registry: {e}")

load_registry()


def extract_video_id(url):
    """Extract YouTube video ID from URL"""
    parsed_url = urlparse(url)
    
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query).get('v', [None])[0]
    elif parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    
    return None


def chunk_transcript(transcript, chunk_size=500, overlap=100):
    """Split transcript into overlapping chunks"""
    chunks = []
    text_parts = []
    
    for entry in transcript:
        text_parts.append({
            'text': entry['text'],
            'start': entry['start']
        })
    
    # Combine into chunks
    current_chunk = []
    current_length = 0
    current_start_time = None
    
    for i, part in enumerate(text_parts):
        # Anchor the start time strictly to the first snippet that enters the chunk
        if current_start_time is None:
            current_start_time = part['start']
            
        words = part['text'].split()
        current_chunk.extend(words)
        current_length += len(words)
        
        if current_length >= chunk_size:
            chunk_text = ' '.join(current_chunk)
            chunks.append({
                'text': chunk_text,
                'start_time': current_start_time
            })
            
            # Keep overlap for next chunk
            current_chunk = current_chunk[-overlap:] if len(current_chunk) > overlap else []
            current_length = len(current_chunk)
            # Reset start time anchor so it grabs the next snippet's timestamp
            current_start_time = None
    
    # Add remaining text
    if current_chunk:
        chunks.append({
            'text': ' '.join(current_chunk),
            'start_time': current_start_time if current_start_time is not None else text_parts[-1]['start']
        })
    
    return chunks


def allowed_file(filename):
    """Check if file extension is allowed (PDF)"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_audio_file(filename):
    """Check if file extension is an allowed audio format"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS


def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    text_parts = []
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                try:
                    text = page.extract_text()
                    if text and text.strip():
                        text_parts.append(text)
                        print(f"   ✅ Page {page_num}/{total_pages}")
                except Exception as e:
                    print(f"   ❌ Page {page_num}/{total_pages}: {str(e)}")
            
            full_text = '\n\n'.join(text_parts)
            print(f"✅ Extracted {len(full_text)} characters from {total_pages} pages")
            return full_text
    except Exception as e:
        raise Exception(f"Error reading PDF: {str(e)}")


def chunk_text(text, chunk_size=1000, overlap=200):
    """Split text into overlapping chunks"""
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        chunk_text = ' '.join(chunk_words)
        chunks.append({
            'text': chunk_text,
            'chunk_index': len(chunks)
        })
    
    return chunks



def extract_transcript_via_supadata(video_url, api_key=None):
    """Primary transcript extraction using Supadata.ai API to bypass cloud datacenter IP blocks."""
    api_key = api_key or os.getenv('SUPADATA_API_KEY') or 'sd_dda5c6feda374288d06015682b01a873'
    if not api_key:
        print("⚠️ [supadata] No SUPADATA_API_KEY configured", flush=True)
        return None

    print(f"🎬 [supadata] Requesting transcript for: {video_url}", flush=True)
    import requests
    import time
    
    url = f"https://api.supadata.ai/v1/transcript?url={video_url}"
    headers = {'x-api-key': api_key}
    
    try:
        r = requests.get(url, headers=headers, timeout=35)
        print(f"🎬 [supadata] Response status: {r.status_code}", flush=True)
        
        if r.status_code == 200:
            data = r.json()
            raw_chunks = data.get('content') or []
            if isinstance(raw_chunks, list) and raw_chunks:
                snippets = [
                    {
                        'text': c['text'].strip(),
                        'start': float(c.get('offset', 0)) / 1000.0
                    }
                    for c in raw_chunks
                    if isinstance(c, dict) and c.get('text', '').strip()
                ]
                if snippets:
                    print(f"✅ [supadata] Successfully extracted {len(snippets)} snippets!", flush=True)
                    return snippets
            elif isinstance(raw_chunks, str) and raw_chunks.strip():
                return [{'text': raw_chunks.strip(), 'start': 0.0}]
                
        elif r.status_code == 202:
            job_id = r.json().get('jobId')
            print(f"⏳ [supadata] Video queued for async processing (jobId: {job_id}). Polling...", flush=True)
            for attempt in range(45):
                time.sleep(2)
                poll_r = requests.get(f"https://api.supadata.ai/v1/transcript/{job_id}", headers=headers, timeout=15)
                if poll_r.status_code == 200:
                    poll_data = poll_r.json()
                    status = poll_data.get('status')
                    if status == 'completed':
                        content = poll_data.get('content') or poll_data.get('result') or []
                        if isinstance(content, list) and content:
                            snippets = [
                                {
                                    'text': c['text'].strip(),
                                    'start': float(c.get('offset', 0)) / 1000.0
                                }
                                for c in content
                                if isinstance(c, dict) and c.get('text', '').strip()
                            ]
                            if snippets:
                                print(f"✅ [supadata] Async transcription completed: {len(snippets)} snippets", flush=True)
                                return snippets
                        elif isinstance(content, str) and content.strip():
                            return [{'text': content.strip(), 'start': 0.0}]
                    elif status == 'failed':
                        print(f"⚠️ [supadata] Async job failed: {poll_data.get('error')}", flush=True)
                        break
        else:
            print(f"⚠️ [supadata] API returned status {r.status_code}: {r.text[:200]}", flush=True)
    except Exception as e:
        print(f"⚠️ [supadata] Request error: {e}", flush=True)
        
    return None


def extract_transcript_via_ytdlp(video_id):
    """Fallback transcript extraction using yt-dlp to bypass datacenter IP restrictions."""
    print(f"📥 [yt-dlp] Starting extraction for video ID: {video_id}", flush=True)
    try:
        import yt_dlp
        import urllib.request
        import json
        import re

        url = f"https://www.youtube.com/watch?v={video_id}"
        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 15,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("📥 [yt-dlp] Fetching video metadata...", flush=True)
            info = ydl.extract_info(url, download=False)
            all_subs = {}
            all_subs.update(info.get('automatic_captions') or {})
            all_subs.update(info.get('subtitles') or {})
            if not all_subs:
                print("⚠️ [yt-dlp] No subtitle tracks found in metadata", flush=True)
                return None

            print(f"📥 [yt-dlp] Found {len(all_subs)} subtitle languages", flush=True)
            track_list = all_subs.get('en') or all_subs.get('hi') or next(iter(all_subs.values()), [])
            
            # 1. Try json3 format
            json3_track = next((t for t in track_list if t.get('ext') == 'json3'), None)
            if json3_track:
                print("📥 [yt-dlp] Downloading json3 caption stream...", flush=True)
                req = urllib.request.Request(json3_track['url'], headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    snippets = []
                    for event in data.get('events', []):
                        if 'segs' in event:
                            text = ''.join(s.get('utf8', '') for s in event['segs']).strip()
                            if text:
                                snippets.append({'text': text, 'start': float(event.get('tStartMs', 0)) / 1000.0})
                    if snippets:
                        print(f"✅ [yt-dlp] Parsed {len(snippets)} snippets from json3", flush=True)
                        return snippets

            # 2. Try vtt format
            vtt_track = next((t for t in track_list if t.get('ext') == 'vtt'), None)
            if vtt_track:
                print("📥 [yt-dlp] Downloading vtt caption stream...", flush=True)
                req = urllib.request.Request(vtt_track['url'], headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    vtt_text = resp.read().decode('utf-8', errors='ignore')
                    snippets = []
                    curr_time = 0.0
                    for line in vtt_text.splitlines():
                        m = re.match(r'(\d{2}):(\d{2}):(\d{2})\.(\d{3}) -->', line) or re.match(r'(\d{2}):(\d{2})\.(\d{3}) -->', line)
                        if m:
                            nums = [float(x) for x in m.groups()]
                            if len(nums) == 4:
                                curr_time = nums[0]*3600 + nums[1]*60 + nums[2] + nums[3]/1000.0
                            else:
                                curr_time = nums[0]*60 + nums[1] + nums[2]/1000.0
                        elif line.strip() and not line.startswith(('WEBVTT', 'Kind:', 'Language:', 'NOTE')) and not line.isdigit():
                            clean = re.sub(r'<[^>]+>', '', line).strip()
                            if clean:
                                snippets.append({'text': clean, 'start': curr_time})
                    if snippets:
                        print(f"✅ [yt-dlp] Parsed {len(snippets)} snippets from vtt", flush=True)
                        return snippets

    except Exception as e:
        print(f"⚠️ [yt-dlp-fallback] Error during yt-dlp subtitle extraction: {e}", flush=True)
    return None


@app.route('/api/process-video', methods=['POST'])
def process_video():
    """Process YouTube video and create embeddings"""
    try:
        data = request.json or {}
        video_url = data.get('url', '').strip()
        workspace_id = data.get('workspace_id')
        
        print(f"\n🎬 [process-video] Incoming request: url='{video_url}', workspace='{workspace_id}'", flush=True)
        
        if workspace_id and workspace_id not in workspaces:
            print(f"⚠️ [process-video] Target workspace not found: {workspace_id}", flush=True)
            return jsonify({'error': 'Target workspace not found'}), 404
            
        if not video_url:
            print("⚠️ [process-video] No URL provided", flush=True)
            return jsonify({'error': 'No URL provided'}), 400
        
        # Extract video ID
        video_id = extract_video_id(video_url)
        if not video_id:
            print(f"⚠️ [process-video] Could not extract video ID from: {video_url}", flush=True)
            return jsonify({'error': 'Invalid YouTube URL'}), 400
            
        print(f"🎬 [process-video] Extracted video ID: {video_id}", flush=True)
        
        # Get transcript
        transcript = None

        # 1. Primary: Try Supadata API (bypasses YouTube datacenter IP blocks)
        print("🎬 [process-video] Step 1: Attempting extraction via Supadata API...", flush=True)
        try:
            transcript = extract_transcript_via_supadata(video_url)
            if transcript:
                print(f"✅ [process-video] Supadata extracted {len(transcript)} transcript snippets!", flush=True)
        except Exception as supadata_err:
            print(f"⚠️ [process-video] Supadata extraction note: {supadata_err}", flush=True)

        # 2. Fallback: Try yt-dlp if Supadata did not return a transcript
        if not transcript:
            print("🔄 [process-video] Step 2: Attempting fallback extraction via yt-dlp...", flush=True)
            try:
                transcript = extract_transcript_via_ytdlp(video_id)
                if transcript:
                    print(f"✅ [process-video] yt-dlp extracted {len(transcript)} transcript snippets!", flush=True)
            except Exception as ytdlp_err:
                print(f"⚠️ [process-video] yt-dlp fallback error: {ytdlp_err}", flush=True)

        # 3. Fallback: Try youtube_transcript_api if both above failed
        if not transcript:
            print("🔄 [process-video] Step 3: Attempting fallback extraction via youtube_transcript_api...", flush=True)
            try:
                from youtube_transcript_api.proxies import GenericProxyConfig
                import requests
                from requests.adapters import HTTPAdapter
                import urllib3
                
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

                class TimeoutHTTPAdapter(HTTPAdapter):
                    def __init__(self, *args, timeout=(15, 35), **kwargs):
                        self.timeout = timeout
                        super().__init__(*args, **kwargs)

                    def send(self, req, **kwargs):
                        if kwargs.get('timeout') is None:
                            kwargs['timeout'] = self.timeout
                        return super().send(req, **kwargs)

                def _clean_proxy_url(raw):
                    if not raw:
                        return None
                    raw = raw.strip().strip("'\"")
                    if not raw:
                        return None
                    if 'scraperapi' in raw.lower() and '@' not in raw:
                        key = raw.replace('http://', '').replace('https://', '').replace('scraperapi:', '').strip('/')
                        return f"http://scraperapi:{key}@proxy-server.scraperapi.com:8001"
                    elif '@' not in raw and len(raw) == 32 and not raw.startswith(('http://', 'https://')):
                        return f"http://scraperapi:{raw}@proxy-server.scraperapi.com:8001"
                    return raw

                proxy_url = _clean_proxy_url(os.getenv('PROXY_URL'))

                def _build_api(use_proxy=False):
                    session = requests.Session()
                    session.verify = False
                    timeout_val = (15, 35) if use_proxy else (10, 15)
                    session.mount("http://", TimeoutHTTPAdapter(timeout=timeout_val))
                    session.mount("https://", TimeoutHTTPAdapter(timeout=timeout_val))
                    p_cfg = GenericProxyConfig(http_url=proxy_url, https_url=proxy_url) if (use_proxy and proxy_url) else None
                    return YouTubeTranscriptApi(proxy_config=p_cfg, http_client=session)

                def _fetch_transcript_data(api_client):
                    try:
                        return api_client.fetch(video_id, languages=['en', 'hi'])
                    except Exception as lang_err:
                        t_list = api_client.list(video_id)
                        avail = list(t_list)
                        if avail:
                            return api_client.fetch(video_id, languages=[avail[0].language_code])
                        raise NoTranscriptFound("No transcripts available")

                if proxy_url:
                    proxy_api = _build_api(use_proxy=True)
                    try:
                        transcript_data = _fetch_transcript_data(proxy_api)
                    except Exception as proxy_err:
                        if not isinstance(proxy_err, (TranscriptsDisabled, NoTranscriptFound)):
                            direct_api = _build_api(use_proxy=False)
                            transcript_data = _fetch_transcript_data(direct_api)
                        else:
                            raise proxy_err
                else:
                    direct_api = _build_api(use_proxy=False)
                    transcript_data = _fetch_transcript_data(direct_api)

                try:
                    if hasattr(transcript_data[0], 'text'):
                        transcript = [{'text': s.text, 'start': float(s.start)} for s in transcript_data]
                    else:
                        transcript = [{'text': s.get('text', ''), 'start': float(s.get('start', 0.0))} for s in transcript_data]
                except Exception as inner_e:
                    if hasattr(transcript_data, 'snippets'):
                        transcript = [{'text': getattr(s, 'text', ''), 'start': float(getattr(s, 'start', 0.0))} for s in transcript_data.snippets]
                    else:
                        raise inner_e

                if transcript:
                    print(f"✅ [process-video] youtube_transcript_api extracted {len(transcript)} transcript snippets!", flush=True)

            except TranscriptsDisabled:
                print(f"❌ [process-video] Transcripts disabled for video {video_id}", flush=True)
                return jsonify({'error': 'Transcripts are disabled for this video on YouTube'}), 400
            except NoTranscriptFound:
                print(f"❌ [process-video] No transcript found for video {video_id}", flush=True)
                return jsonify({'error': 'No transcript found for this video. Please try a video with closed captions/subtitles.'}), 400
            except Exception as yta_err:
                print(f"⚠️ [process-video] youtube_transcript_api error: {yta_err}", flush=True)

        if not transcript:
            print(f"❌ [process-video] All transcript extraction methods failed for video {video_id}", flush=True)
            return jsonify({'error': 'Could not extract transcript for this video. Please ensure closed captions or subtitles are enabled.'}), 400
        
        # Chunk the transcript
        chunks = chunk_transcript(transcript)
        print(f"📊 [process-video] Chunked transcript into {len(chunks)} chunks", flush=True)
        
        # Create or get collection for this video
        collection_name = f"video_{video_id}"
        try:
            chroma_client.delete_collection(collection_name)
        except:
            pass
        
        collection = chroma_client.create_collection(
            name=collection_name,
            metadata={"video_id": video_id}
        )
        
        # Generate embeddings and store in ChromaDB
        texts = [chunk['text'] for chunk in chunks]
        metadatas = [{'start_time': chunk['start_time']} for chunk in chunks]
        ids = [f"chunk_{i}" for i in range(len(chunks))]
        
        print(f"🧠 [process-video] Generating embeddings for {len(texts)} chunks...", flush=True)
        
        # Process in batches to prevent memory spike
        batch_size = 32
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_emb = embedding_model.encode(batch, show_progress_bar=False).tolist()
            embeddings.extend(batch_emb)
            print(f"   Embeddings: processed {min(i + batch_size, len(texts))}/{len(texts)} chunks", flush=True)
            
        print("✅ [process-video] Embeddings generated successfully!", flush=True)
        
        collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        print(f"💾 [process-video] Stored in ChromaDB under collection '{collection_name}'", flush=True)
        
        # Store in unified document registry
        doc_id = f"youtube_{video_id}"
        documents_registry[doc_id] = {
            'id': doc_id,
            'type': 'youtube',
            'name': f"YouTube Video ({video_id[:8]}...)",
            'video_id': video_id,
            'collection_name': collection_name,
            'chunks_count': len(chunks),
            'parent_workspace_id': workspace_id,
            'created_at': datetime.now().isoformat()
        }
        save_registry()
        
        return jsonify({
            'success': True,
            'document_id': doc_id,
            'video_id': video_id,
            'chunks_created': len(chunks),
            'message': 'Video processed successfully'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/process-pdf', methods=['POST'])
def process_pdf():
    """Process PDF file and create embeddings"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        workspace_id = request.form.get('workspace_id')
        if workspace_id and workspace_id not in workspaces:
            return jsonify({'error': 'Target workspace not found'}), 404
            
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only PDF files are allowed.'}), 400
        
        # Save file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        workspace_id = request.form.get('workspace_id')
        
        # Validate workspace_id if provided
        if workspace_id and workspace_id not in workspaces:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': 'Invalid workspace_id: workspace not found'}), 400
        
        try:
            # Extract text from PDF
            print(f"📄 Processing PDF: {filename}")
            text = extract_text_from_pdf(filepath)
            
            if not text or len(text.strip()) < 100:
                return jsonify({'error': 'PDF appears to be empty or contains too little text'}), 400
            
            # Chunk the text
            chunks = chunk_text(text)
            print(f"📊 Created {len(chunks)} chunks")
            
            # Create collection for this PDF
            doc_id = f"pdf_{str(uuid.uuid4())[:8]}"
            collection_name = doc_id
            
            try:
                chroma_client.delete_collection(collection_name)
            except:
                pass
            
            collection = chroma_client.create_collection(
                name=collection_name,
                metadata={"document_id": doc_id, "filename": filename}
            )
            
            # Generate embeddings
            texts = [chunk['text'] for chunk in chunks]
            metadatas = [{'chunk_index': chunk['chunk_index'], 'filename': filename} for chunk in chunks]
            ids = [f"chunk_{i}" for i in range(len(chunks))]
            
            print(f"Generating embeddings for {len(texts)} chunks...")
            embeddings = embedding_model.encode(texts, show_progress_bar=True).tolist()
            print("Embeddings generated successfully!")
            
            collection.add(
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            
            # Store in document registry
            documents_registry[doc_id] = {
                'id': doc_id,
                'type': 'pdf',
                'name': filename,
                'collection_name': collection_name,
                'chunks_count': len(chunks),
                'parent_workspace_id': workspace_id,
                'created_at': datetime.now().isoformat()
            }
            save_registry()
            
            return jsonify({
                'success': True,
                'document_id': doc_id,
                'filename': filename,
                'chunks_created': len(chunks),
                'message': 'PDF processed successfully'
            })
        
        finally:
            # Clean up uploaded file
            if os.path.exists(filepath):
                os.remove(filepath)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/process-image', methods=['POST'])
def process_image():
    """Process Image file using OCR and create embeddings"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        workspace_id = request.form.get('workspace_id')
        if workspace_id and workspace_id not in workspaces:
            return jsonify({'error': 'Target workspace not found'}), 404
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type.'}), 400
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        workspace_id = request.form.get('workspace_id')
        
        # Validate workspace_id if provided
        if workspace_id and workspace_id not in workspaces:
            return jsonify({'error': 'Invalid workspace_id: workspace not found'}), 400
        
        try:
            print(f"🖼️ OCR Processing: {filename}")
            results = ocr_reader.readtext(filepath)
            extracted_text = " ".join([res[1] for res in results])
            
            if not extracted_text or len(extracted_text.strip()) < 10:
                return jsonify({'error': 'No significant text found in image'}), 400
            
            chunks = chunk_text(extracted_text)
            doc_id = f"image_{str(uuid.uuid4())[:8]}"
            collection_name = doc_id
            
            try:
                chroma_client.delete_collection(collection_name)
            except:
                pass
            
            collection = chroma_client.create_collection(
                name=collection_name,
                metadata={"document_id": doc_id, "filename": filename, "source": "ocr"}
            )
            
            texts = [chunk['text'] for chunk in chunks]
            metadatas = [{'chunk_index': chunk['chunk_index'], 'filename': filename} for chunk in chunks]
            ids = [f"chunk_{i}" for i in range(len(chunks))]
            
            embeddings = embedding_model.encode(texts, show_progress_bar=True).tolist()
            collection.add(embeddings=embeddings, documents=texts, metadatas=metadatas, ids=ids)
            
            documents_registry[doc_id] = {
                'id': doc_id,
                'type': 'image',
                'name': f"OCR: {filename}",
                'collection_name': collection_name,
                'chunks_count': len(chunks),
                'parent_workspace_id': workspace_id,
                'created_at': datetime.now().isoformat()
            }
            save_registry()
            
            return jsonify({
                'success': True,
                'document_id': doc_id,
                'filename': filename,
                'chunks_created': len(chunks),
                'message': 'Image text extracted and indexed'
            })
            
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/process-text', methods=['POST'])
def process_text():
    """Process manual text entry (Note)"""
    try:
        data = request.json
        title = data.get('title', 'Untitled Note')
        text = data.get('text', '')
        parent_workspace_id = data.get('workspace_id')
        
        if parent_workspace_id and parent_workspace_id not in workspaces:
            return jsonify({'error': 'Target workspace not found'}), 404
            
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        # Chunk the text
        chunks = chunk_text(text)
        
        # Create collection for this Note
        doc_id = f"note_{str(uuid.uuid4())[:8]}"
        collection_name = doc_id
        
        collection = chroma_client.create_collection(name=collection_name)
        
        # Add chunks to collection
        texts = [c['text'] for c in chunks]
        embeddings = embedding_model.encode(texts, show_progress_bar=False).tolist()
        metadatas = [{'source': title, 'index': i, 'type': 'note'} for i in range(len(chunks))]
        collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=[f"{doc_id}_{i}" for i in range(len(chunks))]
        )
        
        # Add to registry
        doc_info = {
            'id': doc_id,
            'type': 'note',
            'name': title,
            'collection_name': collection_name,
            'chunks_count': len(chunks),
            'parent_workspace_id': parent_workspace_id,
            'created_at': datetime.now().isoformat()
        }
        documents_registry[doc_id] = doc_info
        save_registry()
        
        return jsonify({
            'success': True,
            'document_id': doc_id,
            'title': title,
            'chunks_count': len(chunks)
        })
    except Exception as e:
        import traceback
        print(f"Text processing error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/process-audio', methods=['POST'])
def process_audio():
    """Process audio file using faster-whisper (local, free) and create embeddings"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_audio_file(file.filename):
            return jsonify({'error': f'Invalid file type. Allowed formats: mp3, m4a, wav, ogg, flac, aac, webm'}), 400

        # Save file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        base_name = os.path.splitext(filename)[0]
        
        workspace_id = request.form.get('workspace_id')
        if workspace_id and workspace_id not in workspaces:
            return jsonify({'error': 'Target workspace not found'}), 404

        try:
            print(f"🎙️ Transcribing audio: {filename} using faster-whisper (local)...")

            segments, info = whisper_model.transcribe(filepath, beam_size=5)

            print(f"   Detected language: {info.language} (probability: {info.language_probability:.2f})")

            # Collect all segments into full transcript
            transcript_parts = []
            for segment in segments:
                transcript_parts.append(segment.text.strip())

            transcript_text = "\n".join(transcript_parts)

            if not transcript_text or len(transcript_text.strip()) < 50:
                return jsonify({'error': 'Could not extract any speech from the audio file. Please ensure the file contains clear spoken content.'}), 400

            print(f"✅ Transcription complete: {len(transcript_text)} characters")

            # Chunk the transcript
            chunks = chunk_text(transcript_text)
            print(f"📊 Created {len(chunks)} chunks")

            # Create ChromaDB collection
            doc_id = f"audio_{str(uuid.uuid4())[:8]}"
            collection_name = doc_id

            try:
                chroma_client.delete_collection(collection_name)
            except:
                pass

            collection = chroma_client.create_collection(
                name=collection_name,
                metadata={"document_id": doc_id, "filename": filename}
            )

            # Generate embeddings
            texts = [chunk['text'] for chunk in chunks]
            metadatas = [{'chunk_index': chunk['chunk_index'], 'filename': filename, 'source_type': 'audio'} for chunk in chunks]
            ids = [f"chunk_{i}" for i in range(len(chunks))]

            print(f"Generating embeddings for {len(texts)} audio chunks...")
            embeddings = embedding_model.encode(texts, show_progress_bar=True).tolist()
            print("Embeddings generated!")

            collection.add(
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )

            # Register the document
            documents_registry[doc_id] = {
                'id': doc_id,
                'type': 'audio',
                'name': base_name,
                'collection_name': collection_name,
                'chunks_count': len(chunks),
                'transcript_length': len(transcript_text),
                'language': info.language,
                'parent_workspace_id': workspace_id,
                'created_at': datetime.now().isoformat()
            }
            save_registry()

            return jsonify({
                'success': True,
                'document_id': doc_id,
                'filename': base_name,
                'chunks_created': len(chunks),
                'transcript_length': len(transcript_text),
                'language': info.language,
                'message': 'Audio transcribed and processed successfully!'
            })

        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    except Exception as e:
        import traceback
        print(f"Audio processing error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat queries about the video"""
    try:
        data = request.json
        document_id = data.get('document_id') or data.get('video_id')  # Support both
        question = data.get('question')
        
        if not document_id or not question:
            return jsonify({'error': 'Missing document_id or question'}), 400
        
        if document_id not in documents_registry:
            return jsonify({'error': 'Document not processed yet'}), 400
        
        # Get collection
        doc_info = documents_registry[document_id]
        collection_name = doc_info['collection_name']
        collection = chroma_client.get_collection(collection_name)
        
        # Generate query embedding using local model (instant!)
        query_embedding = embedding_model.encode([question])[0].tolist()
        
        # Retrieve relevant chunks
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=5
        )
        
        if not results['documents'] or not results['documents'][0]:
            return jsonify({'success': True, 'answer': "No relevant content found in this document.", 'sources_used': []})
        
        # Build context from retrieved chunks
        context_parts = []
        for i, doc in enumerate(results['documents'][0]):
            metadata = results['metadatas'][0][i]
            # Handle both YouTube (start_time) and PDF (chunk_index) metadata
            if 'start_time' in metadata:
                timestamp = int(metadata['start_time'])
                context_parts.append(f"[{timestamp}s] {doc}")
            elif 'chunk_index' in metadata:
                chunk_idx = metadata['chunk_index']
                context_parts.append(f"[Chunk {chunk_idx}] {doc}")
            else:
                context_parts.append(doc)
        
        context = "\n\n".join(context_parts)
        
        # Generate response using Gemini
        # Prepare dynamic prompt text based on document type
        doc_type = doc_info.get('type', 'document')
        
        if doc_type == 'youtube':
            doc_noun = "YouTube video"
            content_noun = "transcript"
            ref_noun = "timestamps in seconds"
        elif doc_type == 'audio':
            doc_noun = "audio transcription"
            content_noun = "transcript"
            ref_noun = "chunk numbers"
        else:
            doc_noun = "PDF document"
            content_noun = "text"
            ref_noun = "chunk numbers"
        
        prompt = f"""You are ChatFusion, an intelligent assistant that helps users understand and explore content from their uploaded {doc_noun}.

CONTENT FROM THE {doc_noun.upper()} (with {ref_noun}):
{context}

USER'S QUESTION: {question}

RESPONSE GUIDELINES:
1. **Primary Source**: Always ground your answer in the provided content above. This is the user's uploaded material and should be the foundation of every response.
2. **Supplement When Helpful**: If the content covers a topic but lacks depth, you may enrich your answer with your own knowledge — add clear examples, simple analogies, or deeper explanations to make things click. Always make it clear what comes from the document vs. your own addition (e.g., "Based on the content... To illustrate further...").
3. **Clarity First**: Write in clear, easy-to-understand language. Use short paragraphs, bullet points, bold key terms, and markdown formatting. Avoid walls of text.
4. **Be Thorough**: Don't give one-line answers when the topic deserves more detail. Provide complete, well-structured responses.
5. **Examples**: When explaining concepts, include practical examples — either from the content or your own — to make the answer concrete and useful.
6. **Conversational**: If the user sends a greeting ("hi", "hello"), respond naturally and ask what they'd like to explore.
7. **Honest**: If the content truly doesn't cover the topic at all, say so briefly, then offer what you know about the topic from your own knowledge if relevant.

Provide your response below:"""
        
        if client is None:
            return jsonify({'error': 'GEMINI_API_KEY is not set on the server. Please add it to your Hugging Face Space Secrets.'}), 500
            
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt
        )
        
        # Build sources list (handle both YouTube and PDF metadata)
        sources_used = []
        for meta in results['metadatas'][0]:
            if 'start_time' in meta:
                sources_used.append({'timestamp': meta['start_time']})
            elif 'chunk_index' in meta:
                sources_used.append({'chunk': meta['chunk_index']})
        
        return jsonify({
            'success': True,
            'answer': response.text,
            'sources_used': sources_used
        })
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Chat error: {str(e)}")
        print(f"Full traceback:\n{error_details}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspace/create', methods=['POST'])
def create_workspace():
    """Create a new workspace by merging multiple documents"""
    try:
        data = request.json
        name = data.get('name')
        document_ids = data.get('document_ids')
        
        if not name or not document_ids or len(document_ids) < 2:
            return jsonify({'error': 'Name and at least 2 document IDs are required'}), 400
            
        workspace_id = f"ws_{str(uuid.uuid4())[:8]}"
        merged_collection_name = f"workspace_merged_{workspace_id}"
        
        try:
            chroma_client.delete_collection(merged_collection_name)
        except:
            pass
            
        merged_collection = chroma_client.create_collection(merged_collection_name)
        
        sources = []
        offset = 0
        for doc_id in document_ids:
            if doc_id not in documents_registry:
                continue
                
            doc_info = documents_registry[doc_id]
            
            # Store independent metadata copy for the workspace
            sources.append({
                'id': doc_info['id'],
                'name': doc_info['name'],
                'type': doc_info['type']
            })
            
            source_collection = chroma_client.get_collection(doc_info['collection_name'])
            
            all_chunks = source_collection.get(include=['documents', 'metadatas', 'embeddings'])
            
            if not all_chunks['documents']:
                continue
                
            for i, (text, meta, embedding) in enumerate(zip(
                all_chunks['documents'],
                all_chunks['metadatas'],
                all_chunks['embeddings']
            )):
                meta['source_doc_id'] = doc_id
                meta['source_name'] = doc_info['name']
                meta['source_type'] = doc_info['type']
                
                merged_collection.add(
                    documents=[text],
                    metadatas=[meta],
                    embeddings=[embedding],
                    ids=[f"merged_{doc_id}_{i}"]
                )
            
            offset += len(all_chunks['documents'])
            
        workspaces[workspace_id] = {
            'id': workspace_id,
            'name': name,
            'document_ids': document_ids,
            'sources': sources,
            'merged_collection': merged_collection_name,
            'total_chunks': offset,
            'created_at': datetime.now().isoformat()
        }
        save_registry()
        
        return jsonify({
            'success': True, 
            'workspace_id': workspace_id, 
            'total_chunks': offset,
            'message': 'Workspace created successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspace/chat', methods=['POST'])
def workspace_chat():
    """Handle chat queries across the merged workspace"""
    try:
        data = request.json
        workspace_id = data.get('workspace_id')
        question = data.get('question')
        
        if not workspace_id or not question:
            return jsonify({'error': 'Missing workspace_id or question'}), 400
            
        if workspace_id not in workspaces:
            return jsonify({'error': 'Workspace not found'}), 404
            
        workspace = workspaces[workspace_id]
        merged_collection = chroma_client.get_collection(workspace['merged_collection'])
        
        query_embedding = embedding_model.encode([question])[0].tolist()
        results = merged_collection.query(
            query_embeddings=[query_embedding],
            n_results=8
        )
        
        if not results['documents'] or not results['documents'][0]:
            return jsonify({'success': True, 'answer': "No relevant content found in the workspace.", 'sources_used': []})
            
        sources_used = {}
        for doc_text, meta in zip(results['documents'][0], results['metadatas'][0]):
            src_id = meta.get('source_doc_id', 'unknown')
            src_name = meta.get('source_name', 'Unknown Source')
            src_type = meta.get('source_type', 'unknown')
            
            if src_id not in sources_used:
                sources_used[src_id] = {
                    'name': src_name,
                    'type': src_type,
                    'chunks': []
                }
                
            if src_type == 'youtube' and 'start_time' in meta:
                label = f"[{src_name} @ {int(meta['start_time'])}s]"
            elif src_type == 'pdf' and 'chunk_index' in meta:
                label = f"[{src_name}, Section {meta['chunk_index']}]"
            else:
                label = f"[{src_name}]"
                
            sources_used[src_id]['chunks'].append(f"{label}\n{doc_text}")
            
        context_sections = []
        for src_id, src_data in sources_used.items():
            section_header = f"{'📄' if src_data['type'] == 'pdf' else '🎙️' if src_data['type'] == 'audio' else '🎥'} {src_data['name']}:"
            section_content = "\n\n".join(src_data['chunks'])
            context_sections.append(f"{section_header}\n{section_content}")
            
        full_context = "\n\n---\n\n".join(context_sections)
        
        num_sources = len(sources_used)
        source_list = "\n".join([
            f"- {'📄' if s['type']=='pdf' else '🎙️' if s['type']=='audio' else '🎥'} {s['name']} ({s['type'].upper()})"
            for s in sources_used.values()
        ])
        
        prompt = f"""You are ChatFusion, an intelligent Knowledge Synthesizer. You have access to a unified workspace containing multiple sources that the user has uploaded. Your job is to deeply integrate these sources and provide clear, comprehensive answers.

KNOWLEDGE SOURCES IN THIS WORKSPACE:
{source_list}

RELEVANT KNOWLEDGE RETRIEVED:
{full_context}

USER'S QUESTION: {question}

RESPONSE GUIDELINES:
1. **Merge, Don't Separate**: Seamlessly weave together information from all relevant sources into one cohesive answer. Don't just list what each source says — integrate them into a unified narrative.
2. **Supplement When Helpful**: If the sources cover a topic but lack depth, enrich your answer with your own knowledge — add examples, analogies, or context. Clearly distinguish between what's from the sources and what you're adding (e.g., "The documents explain X... To build on this...").
3. **Clarity First**: Write in clear, easy-to-understand language. Use short paragraphs, bullet points, **bold key terms**, and proper markdown formatting. No walls of text.
4. **Be Thorough**: Provide complete, well-structured responses. Don't skip valuable details or artificially shorten answers.
5. **Practical Examples**: Include concrete examples — from the sources or your own knowledge — to make concepts tangible and useful.
6. **Natural Attribution**: When referencing specific sources, blend it naturally (e.g., "As covered in the lecture recording and expanded upon in the PDF...").
7. **Conversational**: If the user sends a greeting, respond naturally and ask what they'd like to explore. Don't dump a full summary.
8. **No Disclaimers**: Don't say "the document doesn't cover X" — just give the best, richest answer you can with what's available, supplemented by your own knowledge.

Provide your response below:"""
        
        if client is None:
            return jsonify({'error': 'GEMINI_API_KEY is not set on the server. Please add it to your Hugging Face Space Secrets.'}), 500

        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt
        )
        
        return jsonify({
            'success': True,
            'answer': response.text,
            'sources_used': [
                {'id': k, 'name': v['name'], 'type': v['type'], 'chunks_used': len(v['chunks'])}
                for k, v in sources_used.items()
            ],
            'total_chunks_searched': len(results['documents'][0])
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Workspace chat error: {str(e)}")
        print(f"Full traceback:\n{error_details}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspaces', methods=['GET'])
def list_workspaces():
    """List all created workspaces"""
    try:
        ws_list = list(workspaces.values())
        return jsonify({
            'success': True,
            'workspaces': ws_list,
            'count': len(ws_list)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspace/<workspace_id>', methods=['DELETE'])
def delete_workspace(workspace_id):
    """Delete a workspace"""
    try:
        if workspace_id not in workspaces:
            return jsonify({'error': 'Workspace not found'}), 404
            
        workspace = workspaces[workspace_id]
        
        try:
            chroma_client.delete_collection(workspace['merged_collection'])
        except Exception as e:
            print(f"Warning: Could not delete merged collection {workspace['merged_collection']}: {str(e)}")
            
        del workspaces[workspace_id]
        
        # Completely destroy native documents uploaded into this workspace
        docs_to_delete = []
        for doc_id, doc in documents_registry.items():
            if doc.get('parent_workspace_id') == workspace_id:
                docs_to_delete.append(doc_id)
                
        for doc_id in docs_to_delete:
            native_doc = documents_registry[doc_id]
            try:
                chroma_client.delete_collection(native_doc['collection_name'])
            except:
                pass
            del documents_registry[doc_id]
            
        save_registry()
        
        return jsonify({
            'success': True,
            'message': f"Workspace {workspace['name']} deleted successfully"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workspace/<workspace_id>/add-document', methods=['POST'])
def add_document_to_workspace(workspace_id):
    """Append a new document's chunks into an existing workspace's merged collection"""
    try:
        if workspace_id not in workspaces:
            return jsonify({'error': 'Workspace not found'}), 404

        data = request.json
        document_id = data.get('document_id')

        if not document_id:
            return jsonify({'error': 'document_id is required'}), 400

        if document_id not in documents_registry:
            return jsonify({'error': 'Document not found'}), 404

        # Automatically tag notes with the workspace ID for isolation
        doc = documents_registry[document_id]
        if doc.get('type') == 'note' and not doc.get('parent_workspace_id'):
            doc['parent_workspace_id'] = workspace_id
            print(f"📌 Auto-tagging note {document_id} with workspace {workspace_id}")

        workspace = workspaces[workspace_id]

        # Prevent adding a document that's already in the workspace
        if document_id in workspace.get('document_ids', []):
            return jsonify({'error': 'Document already exists in this workspace'}), 409

        doc_info = documents_registry[document_id]
        source_collection = chroma_client.get_collection(doc_info['collection_name'])
        merged_collection = chroma_client.get_collection(workspace['merged_collection'])

        # Pull all chunks from the source document
        all_chunks = source_collection.get(include=['documents', 'metadatas', 'embeddings'])

        if not all_chunks['documents']:
            return jsonify({'error': 'Document has no chunks to merge'}), 400

        # Use a unique prefix based on current merged count to avoid ID collisions
        existing_count = merged_collection.count()

        for i, (text, meta, embedding) in enumerate(zip(
            all_chunks['documents'],
            all_chunks['metadatas'],
            all_chunks['embeddings']
        )):
            meta['source_doc_id'] = document_id
            meta['source_name'] = doc_info['name']
            meta['source_type'] = doc_info['type']

            merged_collection.add(
                documents=[text],
                metadatas=[meta],
                embeddings=[embedding],
                ids=[f"merged_{document_id}_{existing_count + i}"]
            )

        # Ensure workspace has a sources array
        if 'sources' not in workspace:
            workspace['sources'] = []

        # Update workspace metadata
        if document_id not in workspace.get('document_ids', []):
            workspace.setdefault('document_ids', []).append(document_id)
            
        # Avoid duplicate source entries when appending multiple times
        if not any(s['id'] == document_id for s in workspace['sources']):
            workspace['sources'].append({
                'id': doc_info['id'], 
                'name': doc_info['name'], 
                'type': doc_info['type']
            })

        workspace['total_chunks'] = workspace.get('total_chunks', 0) + len(all_chunks['documents'])
        save_registry()

        return jsonify({
            'success': True,
            'workspace_id': workspace_id,
            'workspace_name': workspace['name'],
            'document_added': doc_info['name'],
            'chunks_added': len(all_chunks['documents']),
            'total_chunks': workspace['total_chunks'],
            'message': f"'{doc_info['name']}' merged into '{workspace['name']}' successfully"
        })

    except Exception as e:
        import traceback
        print(f"Add-to-workspace error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/documents', methods=['GET'])
def list_documents():
    """List all processed documents"""
    try:
        documents = list(documents_registry.values())
        return jsonify({
            'success': True,
            'documents': documents,
            'count': len(documents)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/document/<document_id>', methods=['DELETE'])
def delete_document(document_id):
    """Delete a processed document"""
    try:
        if document_id not in documents_registry:
            return jsonify({'error': 'Document not found'}), 404
        
        # Get document info
        doc_info = documents_registry[document_id]
        collection_name = doc_info['collection_name']
        
        # Delete ChromaDB collection
        try:
            chroma_client.delete_collection(collection_name)
        except Exception as e:
            print(f"Warning: Could not delete collection {collection_name}: {str(e)}")
        
        # Remove from registry
        del documents_registry[document_id]
        
        # Clean up stale workspace references
        for ws_id, ws in workspaces.items():
            if document_id in ws.get('document_ids', []):
                try:
                    ws['document_ids'].remove(document_id)
                except ValueError:
                    pass  # Already not in list
            if 'sources' in ws:
                ws['sources'] = [src for src in ws['sources'] if src['id'] != document_id]
                
        save_registry()
        
        return jsonify({
            'success': True,
            'message': f"Document {doc_info['name']} deleted successfully"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/rename', methods=['POST'])
def rename_item():
    """Rename a document or workspace"""
    try:
        data = request.json
        item_type = data.get('type')
        item_id = data.get('id')
        new_name = data.get('name')
        
        if not item_type or not item_id or not new_name:
            return jsonify({'error': 'Missing type, id, or name'}), 400
            
        if item_type == 'document':
            if item_id in documents_registry:
                documents_registry[item_id]['name'] = new_name
                
                # Propagate rename to all internal workspace copies
                for ws in workspaces.values():
                    if 'sources' in ws:
                        for src in ws['sources']:
                            if src['id'] == item_id:
                                src['name'] = new_name
                                
                save_registry()
                return jsonify({'success': True})
            return jsonify({'error': 'Document not found'}), 404
            
        elif item_type == 'workspace':
            if item_id in workspaces:
                workspaces[item_id]['name'] = new_name
                save_registry()
                return jsonify({'success': True})
            return jsonify({'error': 'Workspace not found'}), 404
            
        return jsonify({'error': 'Invalid type'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/script.js')
def serve_script():
    return send_from_directory('.', 'script.js')

@app.route('/style.css')
def serve_style():
    return send_from_directory('.', 'style.css')

@app.route('/favicon.svg')
def serve_favicon():
    return send_from_directory('.', 'favicon.svg')

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)
