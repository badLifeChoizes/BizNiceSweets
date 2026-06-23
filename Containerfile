# Containerfile (repo root) — Podman's native build-file name.
# Multi-stage build: frontend SPA build → Python runtime serving API + static assets.
#
# Security hardening (T-01-10, T-01-11, T-01-13):
#   - Non-root user (appuser) — T-01-11
#   - No secrets baked into image; POSTGRES_PASSWORD supplied via compose env_file — T-01-10
#   - Pinned base images (node:22-slim, python:3.13-slim, postgres:17-alpine) — T-01-13
#   - postgresql-client installed for pg_isready in entrypoint (Pitfall 6) — T-01-14
#
# Build context: repo root (compose build context: ..)
# Compose usage:
#   build:
#     context: ..
#     dockerfile: Containerfile

# ---------------------------------------------------------------------------
# Stage 1: Build the React/TypeScript SPA
# ---------------------------------------------------------------------------
FROM node:22-slim AS frontend-builder

WORKDIR /frontend

# Copy manifests first for layer caching
COPY frontend/package*.json ./
RUN npm ci --omit=dev

# Copy source and build
COPY frontend/ ./
RUN npm run build
# Output: /frontend/dist/

# ---------------------------------------------------------------------------
# Stage 2: Python runtime — serves API + migrates DB + serves built SPA
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

WORKDIR /app

# Install postgresql-client for pg_isready (Pitfall 6: not in slim image)
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security hardening (T-01-11)
RUN useradd --no-create-home --shell /bin/false appuser

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY backend/ .

# Copy built SPA from frontend-builder stage (D-08: backend serves SPA)
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Copy and make the entrypoint script executable
COPY backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch to non-root user after all setup is done
USER appuser

EXPOSE 8000

# Entrypoint: wait-for-db → alembic upgrade head → exec uvicorn (D-09)
CMD ["/entrypoint.sh"]
