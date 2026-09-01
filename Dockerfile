FROM python:3.10-slim

# Install system dependencies (ffmpeg for faster-whisper, libgl1/libglib for opencv/easyocr)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create a user to run the app to pass Hugging Face's security requirements
RUN useradd -m -u 1000 user

WORKDIR /app

# Set Hugging Face specific Environment Variables
ENV HOME=/app \
    TRANSFORMERS_CACHE=/app/.cache \
    HF_HOME=/app/.cache \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache \
    TORCH_HOME=/app/.cache/torch \
    EASYOCR_MODULE_PATH=/app/.EasyOCR \
    PYTHONUNBUFFERED=1

# Ensure storage directories exist and have proper permissions
RUN mkdir -p /app/chroma_db /app/uploads /app/.cache /app/.EasyOCR \
    && chown -R user:user /app

# Copy and install requirements
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

# Pre-cache Sentence Transformer during Docker build so it doesn't download at runtime
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy the rest of the application files
COPY --chown=user . /app

# Final permission fix
RUN chown -R user:user /app

# Expose the standard port used by Hugging Face Spaces
EXPOSE 7860

# Switch to the non-root user (Required by Hugging Face Spaces)
USER user

# Start the application using Gunicorn on port 7860 with multi-threading and a safe timeout
CMD ["gunicorn", "-b", "0.0.0.0:7860", "--workers", "1", "--threads", "4", "--timeout", "300", "app:app"]
