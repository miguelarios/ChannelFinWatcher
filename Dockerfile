# ChannelFinWatcher Production Dockerfile
# This creates a single container with both backend and frontend services
# using supervisor to manage multiple processes

# =============================================================================
# Stage 1: Build Frontend
# =============================================================================
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# Install frontend dependencies
COPY frontend/package*.json ./
RUN npm ci

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# =============================================================================
# Stage 2: Build Backend Dependencies
# =============================================================================
FROM python:3.11-slim AS backend-builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

# =============================================================================
# Stage 3: Final Production Image
# =============================================================================
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for running frontend (minimal installation)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=backend-builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy backend application
COPY --chown=appuser:appuser backend/ ./backend/

# Copy frontend build from builder stage
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/.next ./frontend/.next
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/node_modules ./frontend/node_modules
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/package*.json ./frontend/
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/next.config.js ./frontend/

# Create data directories with proper permissions
RUN mkdir -p /app/data /app/media /app/temp && \
    chown -R appuser:appuser /app

# Copy supervisor configuration
COPY --chown=appuser:appuser docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create startup script
COPY --chown=appuser:appuser docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose ports
EXPOSE 3000 8000

# Health check - checks both services
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:3000 && curl -f http://localhost:8000/health || exit 1

# Set default environment variables
ENV PYTHONPATH=/app/backend \
    DATABASE_URL=sqlite:///data/app.db \
    MEDIA_DIR=/app/media \
    TEMP_DIR=/app/temp \
    CONFIG_FILE=/app/data/config.yaml \
    COOKIES_FILE=/app/data/cookies.txt \
    NODE_ENV=production \
    NEXT_PUBLIC_API_URL=http://localhost:8000

# Use entrypoint script for initialization
ENTRYPOINT ["/app/entrypoint.sh"]

# Run supervisor to manage both processes
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
