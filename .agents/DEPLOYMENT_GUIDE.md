# Oplyra Deployment Guide

This document describes the configurations, environments, environment variables, Docker build parameters, and rollback strategies for deploying Oplyra to production hosting services (such as Render or AWS ECS).

---

## 1. Hosting Environment Configuration

Oplyra is designed for containerized deployment. The default deployment configuration uses a multi-stage Docker build hosted on **Render** (or any container hosting platform) as declared inside [render.yaml](file:///c:/Users/Akshay/genny%20ai/render.yaml).

### Environmental Variables

| Variable Name | Environment | Purpose / Value |
|---|---|---|
| `FLASK_ENV` | Production | Tells the application factory to load production config overrides (`production`). |
| `SECRET_KEY` | Production | Cryptographic salt used for signing user session cookies. Must be a randomly generated 32-character hex key. |
| `DATABASE_URL` | Production | Database connection string. SQLite fallback: `sqlite:///instance/oplyra.db`. Production: `mysql+pymysql://user:pass@host:3306/oplyra`. |
| `GEMINI_API_KEY` | Production | Google Gemini API key used by the `AIGateway` to call LLM models. |
| `REDIS_URL` | Production | Optional. URL for Redis instance (e.g. `redis://default:pass@redis-host:6379`) to activate memory caching. |

---

## 2. Docker Containerization Standards

The [Dockerfile](file:///c:/Users/Akshay/genny%20ai/Dockerfile) implements a two-stage build to keep the runtime image size minimal and secure:

1. **Stage 1 (Builder)**: Installs development headers (`build-essential`, `libffi-dev`) and installs pip requirements plus `gunicorn` into `/root/.local`.
2. **Stage 2 (Runner)**: Uses `python:3.11-slim` runtime base, copies only compile libraries from the builder stage, maps paths, sets environment configurations, and runs under Gunicorn:
   ```bash
   gunicorn --bind 0.0.0.0:5000 run:app --workers 4 --threads 2 --timeout 120
   ```

---

## 3. Database Initializations & Migrations

- **Database Dynamic Creation**: During factory setup (`create_app` in [__init__.py](file:///c:/Users/Akshay/genny%20ai/app/__init__.py)), the system runs `init_database()`.
- If database tables do not exist (especially on a fresh SQLite or blank MySQL database instance), SQLAlchemy dynamically executes `db.create_all()` to generate tables and prevent database errors on the initial request.
- **Production Migrations**: For production schema updates, integrate `Flask-Migrate` (Alembic engine wrapper) in future phases to execute schema migrations step-by-step without losing existing user assets.

---

## 4. Rollback & Monitoring Actions

### A. Logging & Diagnostics
- Production errors are logged to `app_errors.log` utilizing Flask's rotating file logger (`RotatingFileHandler`, max size 10MB, up to 10 backups).
- Always check `app_errors.log` on the running container for exceptions.

### B. Rollback Strategy
If a deployment fails validation or causes server errors (HTTP 500s):
1. **Container Revert**: Revert the active service deploy tag on Render/AWS to the previous successful Docker image hash.
2. **Database Schema Safeties**: Ensure new columns are created as nullable so that reverting container versions does not cause database insertion crashes.
