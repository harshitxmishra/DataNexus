# Contributing to DataNexus

Thank you for your interest in contributing to **DataNexus: Document Intelligence & Data Analytics Platform**. We welcome contributions from data engineers, backend developers, frontend designers, and technical writers.

---

## 1. Code of Conduct

We are committed to providing a friendly, safe, and welcoming environment for all contributors, regardless of experience level, gender identity, sexual orientation, disability, personal appearance, race, ethnicity, or religion.

---

## 2. Development Workflow

### 2.1 Prerequisites
- **Python**: 3.11 or higher (tested on Python 3.13)
- **Node.js**: v18 or higher (LTS recommended)
- **npm**: v9 or higher
- **Git**: 2.30+

### 2.2 Local Repository Setup
1. Fork the repository on GitHub and clone your fork:
   ```bash
   git clone https://github.com/<your-username>/DataNexus.git
   cd DataNexus
   ```
2. Set up the Python virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux / macOS:
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```
3. Set up the frontend application:
   ```bash
   cd frontend
   npm install
   cd ..
   ```
4. Copy the environment configuration template:
   ```bash
   cp .env.example .env
   ```
5. Seed initial demonstration documents and dimensional records:
   ```bash
   python scripts/seed_database.py
   ```

---

## 3. Coding Standards & Conventions

### 3.1 Backend (Python)
- Follow **PEP 8** style guidelines.
- Use explicit type annotations for function signatures and Pydantic schemas.
- Ensure all database queries utilize SQLAlchemy 2.0+ ORM and standard expression constructs (`case(...)`, not `func.case(...)`).
- Do not commit secrets, hardcoded API keys, or raw binary database files.

### 3.2 Frontend (TypeScript & React)
- Use **TypeScript** with strict mode enabled.
- Avoid generic `any` types; define typed domain models in `frontend/src/types/index.ts`.
- Maintain the custom dark-slate design system; avoid introducing generic brightly-colored gradients or unstyled elements.
- Ensure all interactive controls have accessible labels and appropriate loading/empty/error states.

---

## 4. Branching & Commit Guidelines

### 4.1 Branch Naming
- Features: `feat/<feature-name>`
- Bugfixes: `fix/<issue-name>`
- Documentation: `docs/<topic-name>`
- Refactoring: `refactor/<scope-name>`

### 4.2 Conventional Commits
All commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:
- `feat(<scope>): add new capability`
- `fix(<scope>): resolve specific bug`
- `docs(<scope>): update documentation`
- `test(<scope>): add unit or integration tests`
- `chore(<scope>): build system or dependency update`

---

## 5. Testing Requirements

Before submitting a pull request, ensure all tests pass:

1. **Backend Tests**:
   ```bash
   python -m pytest backend/tests -v
   ```
   All tests must pass. Do not suppress or weaken existing test assertions.

2. **Frontend Production Build**:
   ```bash
   cd frontend
   npm run build
   cd ..
   ```
   TypeScript compilation and Vite bundling must succeed with zero errors.

---

## 6. Submitting a Pull Request

1. Push your branch to your GitHub fork:
   ```bash
   git push origin feat/my-new-feature
   ```
2. Open a Pull Request against `main` on `harshitxmishra/DataNexus`.
3. Provide a clear description of:
   - What problem is solved or what capability is added.
   - Any manual or automated testing performed.
   - Screenshots or CLI outputs illustrating verified behavior.
