# One container: builds the frontend, serves it from the API, includes ffmpeg + Chromium for video export.
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt && playwright install --with-deps chromium
COPY backend/ backend/
COPY --from=web /web/dist frontend/dist
ENV RENDER_BASE_URL=http://127.0.0.1:8000 LESSONFORGE_DATA=/data
VOLUME /data
EXPOSE 8000
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
