# Organized Search Engine with Arabic spaCy Model (Educational)

This variant installs both English and Arabic spaCy models inside the backend container to improve
keyword extraction for Arabic content. Note: installing the Arabic model increases build time and image size.

## Quick start (with Docker)
Prerequisites: Docker & Docker Compose installed.

1. From project root run:
   ```bash
   docker-compose up --build
   ```
   This will build the backend image and start Elasticsearch and Redis. The Flask backend listens on port 5000.
   Building may take several minutes because spaCy models (especially Arabic) are downloaded during the build.

2. (Optional) In a new terminal, run the crawler inside the backend container to gather pages:
   ```bash
   # crawl 10 pages based on seeds.txt and save to docs.json
   docker exec -it organized_backend python crawler.py --max-pages 10
   # index the crawled docs into Elasticsearch
   docker exec -it organized_backend python indexer.py docs.json
   ```

3. Open http://localhost:5000 to access the search UI and admin pages.

## Notes
- The Dockerfile attempts to download `en_core_web_sm` and `ar_core_news_sm`. The Arabic model `ar_core_news_sm` may not be available in some spaCy distributions or may require additional dependencies; the Docker build continues even if the Arabic model download fails.
- If you prefer to pre-download models on host and copy into the image, install spaCy models locally and mount them or modify Dockerfile accordingly.
- For production use, secure Elasticsearch and consider hosting models outside the container for faster builds.
