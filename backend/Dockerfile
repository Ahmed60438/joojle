FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y build-essential gcc curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
# Attempt to download spaCy models for English and Arabic.
# Arabic model may not be present in some spaCy versions; the build continues if download fails.
RUN python -m spacy download en_core_web_sm || true
RUN python -m spacy download ar_core_news_sm || true
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
