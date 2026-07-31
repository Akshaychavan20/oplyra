# Contributing to Oplyra

Thanks for helping improve Oplyra. This guide keeps contributions safe and consistent.

## Ground rules

- Do **not** commit secrets (`.env`, API keys, OAuth secrets, DB passwords, private keys).
- Prefer small, focused pull requests over large mixed changes.
- Do not change production database schemas without an Alembic migration.
- All AI provider calls must go through the central `AIGateway` — never call SDKs ad hoc from routes.

## Development setup

1. Fork / clone the repository.
2. Create a virtualenv and install dependencies:
   ```bash
   python -m venv .venv
   # Windows: .\.venv\Scripts\activate
   # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` → `.env` and fill local values (never commit `.env`).
4. Run migrations: `flask db upgrade`
5. Start the app: `python run.py`

## Testing

```bash
python -m unittest discover -s tests -p "*_test.py" -q
```

Tests use in-memory SQLite and AI mock keys (`your_*` prefixes) so they never hit live providers.

## Pull request checklist

- [ ] No `.env` or secret material in the diff
- [ ] New config documented in `.env.example` and README when needed
- [ ] Migrations included for schema changes
- [ ] Relevant tests pass locally
- [ ] UI changes respect existing design tokens (`style.css` / typography)

## Code style

- Follow existing Flask blueprint / service patterns in `app/`.
- Keep business logic out of templates; prefer services under `app/services/`.
- Prefer design-system CSS variables over one-off colors.

## Reporting security issues

Do not open a public issue for vulnerabilities. Contact the maintainers privately with reproduction steps.
