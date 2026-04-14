import os

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
import os
from dotenv import load_dotenv
import re
from urllib.parse import urlparse, parse_qs
from sentence_transformers import SentenceTransformer
import PyPDF2
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure Gemini API (only for chat, not embeddings)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables. Please create a .env file with your API key.")

client = genai.Client(api_key=GEMINI_API_KEY)

# Initialize Sentence Transformer for local embeddings
print("Loading Sentence Transformer model...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded successfully!")

# Initialize ChromaDB with persistent storage
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Configure file uploads
UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

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
                documents_registry = data.get('documents', {})
                workspaces = data.get('workspaces', {})
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
    
    for i, part in enumerate(text_parts):
        words = part['text'].split()
        current_chunk.extend(words)
        current_length += len(words)
        
        if current_length >= chunk_size:
            chunk_text = ' '.join(current_chunk)
            chunks.append({
                'text': chunk_text,
                'start_time': text_parts[max(0, i - len(current_chunk) + 1)]['start']
            })
            
            # Keep overlap for next chunk
            current_chunk = current_chunk[-overlap:] if len(current_chunk) > overlap else []
            current_length = len(current_chunk)
    
    # Add remaining text
    if current_chunk:
        chunks.append({
            'text': ' '.join(current_chunk),
            'start_time': text_parts[-1]['start']
        })
    
    return chunks


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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



@app.route('/api/process-video', methods=['POST'])
def process_video():
    """Process YouTube video and create embeddings"""
    try:
        data = request.json
        video_url = data.get('url')
        
        if not video_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        # Extract video ID
        video_id = extract_video_id(video_url)
        if not video_id:
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        # Get transcript
        try:
            from youtube_transcript_api.proxies import GenericProxyConfig
            import requests
            import urllib3
            
            # Proxies like ScraperAPI intercept requests and use custom SSL certificates
            # We disable SSL warnings so the console doesn't get flooded.
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            proxy_url = os.getenv('PROXY_URL')
            
            # Configure custom session to disable SSL verification when using a proxy
            client = requests.Session()
            if proxy_url:
                client.verify = False 
                
            # Pass the proxy to the API initialization if it exists
            proxy_config = GenericProxyConfig(http_url=proxy_url, https_url=proxy_url) if proxy_url else None
            api = YouTubeTranscriptApi(proxy_config=proxy_config, http_client=client)
            
            # Try to get transcript in multiple languages
            # Priority: Hindi, English, then any available
            try:
                # Try Hindi first
                transcript_data = api.fetch(video_id, languages=['hi'])
            except:
                try:
                    # Try English
                    transcript_data = api.fetch(video_id, languages=['en'])
                except:
                    # Try any available language
                    transcript_list = api.list(video_id)
                    # Get the first available transcript
                    available_transcripts = list(transcript_list)
                    if available_transcripts:
                        first_transcript = available_transcripts[0]
                        transcript_data = api.fetch(video_id, languages=[first_transcript.language_code])
                    else:
                        raise NoTranscriptFound("No transcripts available")
            
            # Convert snippets to the expected format
            transcript = [{'text': snippet.text, 'start': snippet.start} for snippet in transcript_data.snippets]
        except TranscriptsDisabled:
            return jsonify({'error': 'Transcripts are disabled for this video'}), 400
        except NoTranscriptFound:
            return jsonify({'error': 'No transcript found for this video. Please try a video with captions/subtitles.'}), 400
        except Exception as e:
            return jsonify({'error': f'Error fetching transcript: {str(e)}'}), 400
        
        # Chunk the transcript
        chunks = chunk_transcript(transcript)
        
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
        
        # Use local Sentence Transformer for embeddings (MUCH faster!)
        print(f"Generating embeddings for {len(texts)} chunks...")
        embeddings = embedding_model.encode(texts, show_progress_bar=True).tolist()
        print("Embeddings generated successfully!")
        
        collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        
        # Store in unified document registry
        doc_id = f"youtube_{video_id}"
        documents_registry[doc_id] = {
            'id': doc_id,
            'type': 'youtube',
            'name': f"YouTube Video ({video_id[:8]}...)",
            'video_id': video_id,
            'collection_name': collection_name,
            'chunks_count': len(chunks),
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
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only PDF files are allowed.'}), 400
        
        # Save file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
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
        is_video = doc_type == 'youtube'
        
        doc_noun = "YouTube video" if is_video else "PDF document"
        content_noun = "transcript" if is_video else "text"
        ref_noun = "timestamps in seconds" if is_video else "chunk numbers"
        
        prompt = f"""You are a helpful assistant that answers questions about a {doc_noun} based on its {content_noun}.

Context from the {doc_noun} (with {ref_noun}):
{context}

User question: {question}

Please provide a helpful answer based on the context above. If you reference specific information, mention the approximate reference (e.g., timestamp or chunk). If the context doesn't contain enough information to answer the question, say so politely."""
        
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt
        )
        
        # Build sources list (handle both YouTube and PDF metadata)
        sources = []
        for meta in results['metadatas'][0]:
            if 'start_time' in meta:
                sources.append({'timestamp': meta['start_time']})
            elif 'chunk_index' in meta:
                sources.append({'chunk': meta['chunk_index']})
        
        return jsonify({
            'success': True,
            'answer': response.text,
            'sources': sources
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
        
        offset = 0
        for doc_id in document_ids:
            if doc_id not in documents_registry:
                continue
                
            doc_info = documents_registry[doc_id]
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
            section_header = f"{'📄' if src_data['type'] == 'pdf' else '🎥'} {src_data['name']}:"
            section_content = "\n\n".join(src_data['chunks'])
            context_sections.append(f"{section_header}\n{section_content}")
            
        full_context = "\n\n---\n\n".join(context_sections)
        
        num_sources = len(sources_used)
        source_list = "\n".join([
            f"- {'📄' if s['type']=='pdf' else '🎥'} {s['name']} ({s['type'].upper()})"
            for s in sources_used.values()
        ])
        
        prompt = f"""You are a highly capable Knowledge Synthesizer. Your primary objective is to deeply integrate and merge insights from a unified workspace containing multiple diverse sources.

KNOWLEDGE SOURCES IN THIS WORKSPACE:
{source_list}

RELEVANT KNOWLEDGE RETRIEVED:
{full_context}

USER'S PROMPT: {question}

SYNTHESIS PROTOCOL:
1. COMPREHENSIVE MERGING: Seamlessly weave together information from all relevant sources. If a concept is explained formally in one source and practically in another, combine both perspectives to assemble a comprehensive and rich response. Do not artificially abbreviate or skip valuable details.
2. ADAPTIVE RESPONSE: Tailor your response dynamically to the user's prompt (whether it is a general inquiry, a technical problem, a summary request, or a creative task). Leverage the totality of the merged knowledge to comprehensively fulfill the prompt.
3. SEAMLESS ATTRIBUTION: When drawing upon specific sources, organically blend the attribution into your narrative (e.g., "Combining the theoretical framework from the document with the practical demonstration in the video..."). Do not just list what each source says separately.
4. PROFESSIONAL CLARITY: Maintain a highly organized structure utilizing appropriate markdown (headers, bullet points, bolding) to ensure the integrated output is easily digestible.
5. NO APOLOGIES: DO NOT output robotic disclaimers if a specific detail is missing from the retrieved context (e.g., "The video does not cover X"). Simply generate the richest, most capable response possible using the available merged knowledge.
6. CONVERSATIONAL AWARENESS: If the user's prompt is a simple greeting (e.g., "hello", "hi", "hey"), DO NOT attempt to summarize the entire workspace. Instead, just reply conversationally with a friendly greeting and ask them what specific topic they want to explore.

Provide your synthesized response below:"""

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
        save_registry()
        
        return jsonify({
            'success': True,
            'message': f"Workspace {workspace['name']} deleted successfully"
        })
    except Exception as e:
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
        save_registry()
        
        return jsonify({
            'success': True,
            'message': f"Document {doc_info['name']} deleted successfully"
        })
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
