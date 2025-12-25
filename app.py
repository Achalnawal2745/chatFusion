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

# Unified document registry (videos + PDFs)
documents_registry = {}


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
            api = YouTubeTranscriptApi()
            
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
        prompt = f"""You are a helpful assistant that answers questions about a YouTube video based on its transcript.

Context from the video (with timestamps in seconds):
{context}

User question: {question}

Please provide a helpful answer based on the context above. If you reference specific information, mention the approximate timestamp. If the context doesn't contain enough information to answer the question, say so politely."""
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
