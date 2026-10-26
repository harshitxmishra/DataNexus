# Security Policy

## 1. Supported Versions

We actively maintain and provide security updates for the latest release branch of DataNexus:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

---

## 2. Reporting a Vulnerability

If you discover a security vulnerability within DataNexus, please report it responsibly. **Do not create a public GitHub issue for security vulnerabilities.**

### Contact
Please send your vulnerability details via email to the project maintainers:
- **Email**: `imharshitway@gmail.com`
- **Subject**: `[DataNexus Security Disclosure] - <Brief Title>`

### What to Include
To help us triage and resolve the issue quickly, please provide:
1. Description of the vulnerability and its potential impact.
2. Step-by-step reproduction instructions or a minimal proof of concept.
3. Affected components, endpoints, or dependencies.
4. Any proposed mitigation or patch if available.

### Response Timeline
- **Initial acknowledgment**: Within 48 hours.
- **Triage and assessment**: Within 5 business days.
- **Remediation & Patch release**: Coordinated disclosure within 30 days depending on severity.

---

## 3. Security Best Practices for Deployments

1. **Secrets Management**: Never commit your `.env` file, production database passwords, or LLM API keys to source control.
2. **File Ingestion**: DataNexus restricts uploaded files to validated MIME types (`application/pdf`, `text/csv`) and enforces configurable file size limits (`MAX_UPLOAD_SIZE_MB`). All saved files are hashed (SHA-256) and stored with sanitized paths to prevent path traversal attacks.
3. **Database Security**: All SQL queries utilize parameterized statements via SQLAlchemy ORM to prevent SQL injection vulnerabilities.
4. **Network Exposure**: In production environments, run backend services behind a reverse proxy (e.g., NGINX, Cloudflare) with HTTPS enabled and restricted CORS origins.
