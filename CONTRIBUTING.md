# Contributing to Hotspot Share

Thank you for your interest in contributing to Hotspot Share! We welcome contributions from developers of all skill levels.

---

## 1. Development Principles

* **Zero External Python Dependencies**: The backend runs purely on Python 3's standard library (`http.server`, `socket`, `threading`, `secrets`, `pathlib`). Do not introduce external PyPI dependencies for core operations.
* **Lightweight Native UI**: The desktop interface is written in pure C using GTK 3 and WebKitGTK with minimal memory footprint.
* **Privacy by Default**: No telemetry, no remote analytics, no third-party calls.
* **Test Coverage**: All new backend features, security checks, and endpoints must have accompanying unit tests in `tests/`.

---

## 2. Setting Up Local Development

```bash
# Clone the repository
git clone https://github.com/penguinatnight/hotspot-share.git
cd hotspot-share

# Run unit tests (58 automated tests)
make test

# Build native WebKitGTK desktop wrapper
make build

# Install for current user (symlinks/copies to ~/.local)
make install-user

# Launch the app
hotspot-share-gui
```

---

## 3. Pull Request Guidelines

1. Fork the repo and create your branch from `main`:
   ```bash
   git checkout -b feature/my-cool-feature
   ```
2. Write clean, documented code and keep comments intact.
3. Ensure all tests pass:
   ```bash
   make test
   ```
4. Follow conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
5. Open a Pull Request against `main`. All PRs run GitHub Actions CI automatically.
