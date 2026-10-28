FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml VOICEOPS_PRD.md ./
COPY backend ./backend
COPY frontend ./frontend
COPY .streamlit ./.streamlit
COPY scripts ./scripts
RUN pip install .
EXPOSE 10000
CMD ["python", "scripts/start_render.py"]
