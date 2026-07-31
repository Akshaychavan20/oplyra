# Changelog

All notable changes to Oplyra will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Hardened production deployment guides
- Expanded integration adapters beyond Google (read-only)
- Deeper campaign workspace automation

## [0.1.0] - 2026-07-31

### Added
- Initial public foundation for the Oplyra AI Marketing Operating System
- Flask application factory with auth, clients, campaigns, content, tasks, reports
- Central AI Gateway (Gemini + multi-provider stubs) with mock mode for tests
- Marketing intelligence (“Today’s Focus”) and automation reminders
- Connected Apps foundation (Google Search Console / GA4 OAuth + sync)
- Internal Platform Admin console with RBAC scaffolding
- Knowledge / storage / Celery / Redis infrastructure hooks
- Design system (Inter typography, themed CSS, admin + dashboard shells)
- Test suite under `tests/` using SQLite + AI mocks

[Unreleased]: https://github.com/OWNER/REPO/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OWNER/REPO/releases/tag/v0.1.0
