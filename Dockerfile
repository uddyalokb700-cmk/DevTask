# Build DevTask Production Container
FROM python:3.12-slim

# Set environment flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PORT=8000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN groupadd -r devtask && useradd -r -g devtask -m -d /home/devtask devtask

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . /app/

# Set file permissions
RUN chown -R devtask:devtask /app

# Switch to non-root user
USER devtask

# Collect static assets
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Start server using ASGI/WSGI
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
