FROM python:3.10-slim

# Create a user to run the app to pass Hugging Face's security requirements
RUN useradd -m -u 1000 user

WORKDIR /app

# Copy and install requirements
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Expose the standard port used by Hugging Face Spaces
EXPOSE 7860

# Copy the rest of the application files
COPY --chown=user . /app

# Ensure storage directories exist and have proper permissions
RUN mkdir -p /app/chroma_db /app/uploads /app/.cache \
    && chown -R user:user /app/chroma_db /app/uploads /app/.cache /app

# Switch to the non-root user (Required by Hugging Face Spaces)
USER user

# Set Hugging Face specific Environment Variables
ENV HOME=/app
ENV TRANSFORMERS_CACHE=/app/.cache
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache

# Start the application using Gunicorn on port 7860
CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app", "--timeout", "120"]
