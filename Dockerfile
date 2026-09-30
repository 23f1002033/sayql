# --- Stage 1: build the Next.js static export ---
FROM node:20-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: python runtime ---
FROM python:3.11-slim AS runtime
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py tools.py metrics.yaml ./
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY static/ ./static/
COPY docs/ ./docs/
COPY --from=frontend-build /build/frontend/out ./frontend/out

# Deterministic demo data, baked into the image at build time.
RUN python scripts/seed.py

EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
