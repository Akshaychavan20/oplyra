# Oplyra

**AI-powered Marketing Operating System** for solo performance marketers and freelancers.

Oplyra helps a marketer running Facebook Ads, Google Ads, and SEO for 3–20 clients answer one question every day:

> **"What should I do today?"**

ChatGPT answers questions. Oplyra helps you **finish work**.

---

## Features

- **Today's Work dashboard** — focus card, task queue, deadlines, campaigns, and weekly intelligence
- **Clients → Campaigns** — tasks, assets, notes, and reports nested under campaigns under clients
- **AI content studio** — blogs, emails, social posts, reviews, ads, carousels, video scripts, image prompts via a central AI Gateway
- **SEO analyzer** — readability, structure, keywords, and suggestions
- **Reports & export** — client-ready PDF / DOCX workflows
- **Connected Apps** — Google Search Console & GA4 foundation (OAuth, sync, import; read-only)
- **Platform Admin** — internal staff console with RBAC scaffolding (`/admin`)
- **Light / dark themes** — shared design tokens and Inter typography

---

## Screenshots

> Place product screenshots here once available.

| Dashboard | Campaign Workspace | AI Studio |
|-----------|--------------------|-----------|
| _TODO: `docs/screenshots/dashboard.png`_ | _TODO: `docs/screenshots/workspace.png`_ | _TODO: `docs/screenshots/ai-studio.png`_ |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Flask 3 (app factory + blueprints), SQLAlchemy, Alembic |
| Database | MySQL (prod) / SQLite (tests & local fallback) |
| Auth | Flask-Login, Flask-Bcrypt, CSRF protection |
| AI | Google GenAI (Gemini) + multi-provider gateway |
| Jobs | Celery + Redis (optional; eager mode for tests) |
| Frontend | Jinja2, Bootstrap 5, vanilla JS, Oplyra design system |
| Deploy | Docker / Render (`Dockerfile`, `render.yaml`) |

---

## Installation

### Prerequisites

- Python **3.11+**
- MySQL 8 *(or SQLite for quick local runs)*
- Redis *(optional; required for async mail / Celery in production)*

### Setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate            # Windows
# source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt
copy .env.example .env              # Windows
# cp .env.example .env              # macOS / Linux
```

Edit `.env` with your local secrets (see below). **Never commit `.env`.**

### Database

```powershell
flask db upgrade
```

Dev can self-heal some additive columns on boot. Production should use Alembic only.

### Run locally

```powershell
python run.py
```

Open http://127.0.0.1:5000 and register an account.

Internal admin (when bootstrap env is set): http://127.0.0.1:5000/admin/login

---

## Environment Variables

Copy from `.env.example`. Important keys:

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Flask session signing (≥ 32 random chars in production) |
| `DATABASE_URL` | SQLAlchemy URI (`mysql+pymysql://…` or `sqlite:///…`) |
| `GEMINI_API_KEY` | Google Gemini key (`your_…` prefix enables AI mock mode) |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `DEEPSEEK_API_KEY` | Optional providers |
| `REDIS_URL` | Celery / rate-limit backend |
| `GOOGLE_OAUTH_CLIENT_ID` / `SECRET` | Connected Apps OAuth |
| `MAIL_*` | SMTP for password-reset email |
| `PLATFORM_ADMIN_EMAILS` | Legacy bridge emails for admin access |
| `INTERNAL_ADMIN_BOOTSTRAP_EMAIL` / `PASSWORD` | First staff admin bootstrap |
| `STORAGE_PROVIDER` | `local` \| `s3` \| `gcs` \| `azure` |
| `KNOWLEDGE_VECTOR_PROVIDER` | `local` \| `qdrant` \| `pinecone` \| … |

See `.env.example` for the full list and comments.

---

## Testing

Tests use in-memory SQLite and force AI mock mode (no live Gemini / MySQL required):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "*_test.py" -q
```

---

## Folder Structure

```
app/
├── auth/              # Register, login, password reset
├── main/              # Dashboard + analytics APIs
├── projects/          # Clients (workspaces)
├── content/           # Campaigns, AI generation, SEO, library
├── integrations/      # Connected Apps (OAuth, sync, import)
├── platform_admin/    # Internal admin console + RBAC
├── services/          # AI Gateway, SEO, mail, intelligence, …
├── infra/             # Celery, Redis, storage, metrics
├── static/            # CSS / JS design system
└── templates/         # Jinja2 templates
migrations/            # Alembic revisions
tests/                 # Unit / integration tests
.agents/               # Product bible & architecture notes
config.py              # Dev / Testing / Production configs
run.py                 # Entry point
.env.example           # Documented env template (safe to commit)
```

---

## Future Roadmap

- [ ] Production deployment runbooks and CI
- [ ] Expanded read-only ad-platform connectors
- [ ] Richer campaign workspace automation
- [ ] Screenshot gallery and public docs site
- [ ] Hardened admin audit exports

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
