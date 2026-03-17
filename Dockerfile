# Build stage
FROM python:3.11-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt
# Add extra dependencies for production
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels \
    gunicorn \
    psycopg2-binary \
    redis \
    django-redis \
    whitenoise

# Final stage
FROM python:3.11-slim

# Create directory for static files
RUN mkdir -p /app/staticfiles

# Set work directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder stage
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

# Install dependencies from wheels
RUN pip install --no-cache /wheels/*

# Copy project files
COPY . .

# Collect static files (needs to be run if Django handles static)
# Use a dummy secret key and sqlite for the build process to avoid requiring a real DB
RUN SECRET_KEY=build-time-secret-key DATABASE_URL=sqlite:///./build.db python manage.py collectstatic --noinput

# Environment variable for static root (optional but good practice)
ENV STATIC_ROOT=/app/staticfiles

# Expose port
EXPOSE 8000

# Server command
CMD ["gunicorn", "attendance_system.wsgi:application", "--bind", "0.0.0.0:8000"]
