# Security Architecture (OWASP ASVS L2/L3)

## Application Security Controls

- Authentication: OAuth2/JWT validation at API Gateway and service layer.
- Authorization: RBAC with role scopes (`viewer`, `operator`, `admin`, `security_auditor`).
- Session security: short JWT TTL, refresh token rotation, revocation list support.
- Input validation: strict Pydantic schema validation and allow-listed enums.
- Output encoding: JSON-only APIs with content type enforcement.
- SQL injection protection: parameterized queries/ORM only.
- XSS protection: frontend escaping + CSP.
- CSRF protection: same-site cookies for browser session flows.
- Command injection prevention: no shell concatenation; structured subprocess invocation.
- Rate limiting: token bucket middleware at API gateway.
- Secure headers: CSP, HSTS, X-Frame-Options, X-Content-Type-Options.

## Encryption and Secrets

- TLS 1.2+ for service-to-service and external ingress.
- AES-256-GCM for sensitive at-rest fields.
- Secrets managed using Kubernetes Secrets + external secret manager integration.
- Automatic key rotation policy with audit evidence.

## Observability and Audit

- Immutable security audit logs for all privileged operations.
- Correlation IDs across request, event, and runbook actions.
- OpenTelemetry traces with security event attributes.

## DevSecOps Controls

CI pipeline includes:

- SAST: `bandit`, `semgrep`
- Dependency scanning: `pip-audit`, `npm audit`
- Secret detection: `gitleaks`
- Container scanning: `trivy`
- DAST (stage env): `owasp/zap-baseline.py`

## Infrastructure Hardening

- Containers run as non-root user with read-only root FS.
- Distroless/slim base images and pinned dependency versions.
- Kubernetes: RBAC, NetworkPolicies, Pod Security standards, seccomp runtime/default.

## AI SRE Agent Governance

- All automated runbook actions are written to `audit_logs` and `automation_actions`.
- Runbook catalog supports admin-controlled enable/disable to prevent unauthorized automation.
- Manual `runbook/execute` and `incident/analyze` APIs require operator role; governance toggles require admin.
- Redis-backed rate limiting protects SRE Agent APIs from abuse.
