# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt gunicorn

# Stage 2: Final minimal runtime image
FROM python:3.11-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed libraries and executables
COPY --from=builder /root/.local /root/.local
COPY . .

# Set paths and env variables
ENV PATH=/root/.local/bin:$PATH
ENV FLASK_APP=run.py
ENV FLASK_ENV=production
ENV PORT=5000

# Expose container port
EXPOSE 5000

# Run Gunicorn WSGI server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "run:app", "--workers", "4", "--threads", "2", "--timeout", "120"]
