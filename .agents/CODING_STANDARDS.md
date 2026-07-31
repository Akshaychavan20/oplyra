# Oplyra Coding Standards

This document establishes the python programming guidelines, flask blueprints styles, database transaction protocols, and git practices for Oplyra.

---

## 1. Python Programming Standards

- **Formatting**: Adhere to PEP8 rules. Code must be formatted with standard 4-space indentation.
- **Naming Conventions**:
  - Functions / Methods / Variables: lowercase snake-case (e.g. `generate_blog_post`, `user_id`).
  - Classes: PascalCase (e.g. `AIGateway`, `ContentVersion`).
  - Constants: UPPERCASE snake-case (e.g. `GEMINI_API_KEY`, `REDIS_AVAILABLE`).
- **Imports**: Group imports in the following order, separated by a blank line:
  1. Standard library imports (e.g. `os`, `time`, `hashlib`).
  2. Third-party packages (e.g. `flask`, `sqlalchemy`, `google.genai`).
  3. Local application imports (e.g. `from app import db`, `from app.models import User`).

---

## 2. Flask Blueprint & Controller Patterns

- **Application Factory Pattern**: All initialization logic must remain inside `create_app()` in [__init__.py](file:///c:/Users/Akshay/genny%20ai/app/__init__.py). Avoid using global Flask app objects that cause circular dependency loops.
- **Blueprints Routing**: Use blueprints to isolate pages. Keep routing methods thin:
  - **Correct Pattern**:
    ```python
    @content_bp.route('/generate', methods=['POST'])
    @login_required
    def generate_content_route():
        # 1. Parse request parameters
        topic = request.form.get('topic')
        # 2. Call service layer
        result = GeminiService().generate_blog(topic)
        # 3. Return view template or json
        return render_template('content/view.html', result=result)
    ```
- **Error Handling**: Database query operations must run inside a `try/except` block with a rollback call:
  ```python
  try:
      db.session.add(record)
      db.session.commit()
  except Exception as e:
      db.session.rollback()
      current_app.logger.error(f"Database Exception: {e}")
  ```

---

## 3. HTML & Vanilla CSS Standards

- **Semantic HTML**: Use clean section divisions (`<main>`, `<section>`, `<article>`, `<header>`, `<footer>`).
- **CSS Variable Mapping**: Do not write hardcoded color Hex values inside styling definitions. Use the pre-declared CSS HSL variables from `style.css` (e.g. `var(--bg-dark)`, `var(--primary-hsl)`).
- **Responsive Layout**: Build interface elements utilizing Bootstrap 5 grid utilities (`col-md-6`, `d-flex flex-column`, `gap-3`).

---

## 4. Git Commit Guidelines

Commit messages must be short and descriptive, using the following prefixes:
- `feat:` for new features (e.g. `feat: add CSV analytics parsing controller`).
- `fix:` for bug fixes (e.g. `fix: resolve CSRF validation failures in AJAX requests`).
- `docs:` for documentation edits (e.g. `docs: create database rules guide`).
- `refactor:` for code cleanups with zero functionality changes.
