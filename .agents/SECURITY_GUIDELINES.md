# Oplyra Security Guidelines

This document outlines the security policies, threat mitigation strategies, data encryption practices, and session verification standards for Oplyra.

---

## 1. Authentication & Session Management

- **User Password Hashing**: Passwords must never be stored in plain text. Always use Bcrypt to hash user passwords (`bcrypt.generate_password_hash()`) before writing to the database database layer.
- **Flask-Login Session Controls**: Authenticated sessions are tracked via Flask-Login session cookies. 
  - Ensure the `login_view` redirects securely to `auth.login`.
  - Passwords must be checked using `bcrypt.check_password_hash(self.password_hash, password)`.

---

## 2. Dynamic CSRF Protection (Zero Dependencies)

Oplyra enforces a custom, zero-dependency manual CSRF filter directly inside the app factory [__init__.py](file:///c:/Users/Akshay/genny%20ai/app/__init__.py):

1. **Token Ingestion**: During app bootstrap, a hex token is initialized in the flask session if missing:
   ```python
   session['csrf_token'] = secrets.token_hex(16)
   ```
2. **Context Injector**: The `csrf_token()` function is injected globally into Jinja template engines.
3. **Request Filtering**: Every HTTP `POST` request must submit a matching token payload inside the form data parameter (`csrf_token`) or the request header (`X-CSRF-Token`). Non-matching requests are immediately rejected with an HTTP `400 Bad Request` or custom AJAX error responses.

---

## 3. SQL Injection & XSS Safeguards

### A. SQL Injection Prevention
- Do not build database query strings utilizing manual string concatenation:
  - **Incorrect**: `db.session.execute("SELECT * FROM users WHERE username = '" + name + "'")`
  - **Correct**: Always utilize SQLAlchemy's parameterized execution engine:
    ```python
    User.query.filter_by(username=name).first()
    ```

### B. Cross-Site Scripting (XSS) Protection
- Jinja2 automatically escapes HTML outputs by default.
- Never wrap user-supplied string injections in the `|safe` filter unless they are generated inside sanitized Markdown parser libraries.

---

## 4. API Key Security & Secrets Encryption

- **Environment Separation**: API keys (specifically `GEMINI_API_KEY`, `SECRET_KEY`, and `DATABASE_URL`) must be loaded from system environment variables or a secure `.env` file. They must never be checked into public Git repositories.
- **Custom Key Handlers**: Under settings, if a user provides a custom Gemini API key, we fetch it securely in the request header (`X-Gemini-Key`) or load it from database records. Keep custom keys encrypted if saved locally.

---

## 5. Password Reset Token Management

- **Single-Use Tokens**: Password reset tokens generated via [routes.py](file:///c:/Users/Akshay/genny%20ai/app/auth/routes.py) must utilize secure UUID strings.
- **Expiration Policies**: Token lifespan is limited to a maximum of 1 hour. Tokens must be flagged as `used = True` in the database immediately upon password change validation to prevent replay attacks.
- **Database Model**: Maps to `PasswordResetToken` table, referencing the foreign key `user_id`.
