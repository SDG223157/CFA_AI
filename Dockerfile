FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8501 \
    PYTHONPATH=/app

WORKDIR /app

# System deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY . /app

EXPOSE 8501

# Streamlit must listen on 0.0.0.0 for containers, and use PORT for platforms like Coolify.
CMD ["sh", "-lc", "streamlit run app/main.py --server.address=0.0.0.0 --server.port=${PORT} --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false"]


