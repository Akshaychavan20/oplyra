# Oplyra Testing Strategy

This document outlines the testing architecture, validation frameworks, mock service standards, and coverage goals for the Oplyra platform.

---

## 1. Test Architecture

The application defines two testing environments:
1. **Local Test Harness**: Executed using `pytest`. Uses a local in-memory SQLite database configuration (`SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"`).
2. **System Verification**: Automated scripts located under [scratch/](file:///c:/Users/Akshay/genny%20ai/scratch) (e.g. [test_analytics.py](file:///c:/Users/Akshay/genny%20ai/scratch/test_analytics.py) and [test_password_reset.py](file:///c:/Users/Akshay/genny%20ai/scratch/test_password_reset.py)) designed to evaluate route integrations and token resets locally.

---

## 2. Test Classifications

### A. Unit Testing
- **Scope**: Testing individual helper services (e.g., [seo_service.py](file:///c:/Users/Akshay/genny%20ai/app/services/seo_service.py) keyword checks, brand voice processors).
- **Guidelines**: Isolate methods from external databases or networks using mock inputs.

### B. Integration Testing
- **Scope**: Evaluating Flask blueprint route outputs and database operations.
- **Guidelines**: Use the built-in Flask `test_client()` to simulate request payloads (form data and headers) and evaluate response code mappings (200 OK, 302 Redirect).
- **CSRF Token Handling**: Tests must fetch the initial GET page session CSRF token value and pass it inside the post parameters to bypass request verification filters.

### C. AI Gateway Mock Testing
- **Scope**: Validating that model routing, caches, and rate limits function without hitting actual Google Gemini API endpoints.
- **Mock Strategy**: Set `GEMINI_API_KEY = "your_mock_key"` inside testing configurations. Verify that [ai_gateway.py](file:///c:/Users/Akshay/genny%20ai/app/services/ai_gateway.py) successfully catches this prefix and routes the call to local mock responses, tracking token consumption inside `TokenBillingLog` correctly.

---

## 3. Coverage Goals & Automation

- **Target Coverage**: Core business logic modules (Auth, Campaigns, AI Gateway Services) must maintain a minimum threshold of **80% test coverage**.
- **Running Tests**:
  - Run the test suites:
    ```powershell
    pytest -v
    ```
  - Generate a code coverage report:
    ```powershell
    pytest --cov=app tests/
    ```
- **Deployment Gate**: Tests must run successfully locally prior to committing code or pushing builds to production environments (e.g., Render Docker deployments).
