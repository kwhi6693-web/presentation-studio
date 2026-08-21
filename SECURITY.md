# Security Policy

## Supported versions

| Version | Security assessment |
|---|---|
| Current `main` | Supported for investigation and fixes |
| Latest stable Release | Supported for investigation and fixes |
| Older Releases | Best-effort assessment; upgrade may be required |

## Privately report a vulnerability

Please privately report suspected vulnerabilities through [GitHub Private Vulnerability Reporting](https://github.com/kwhi6693-web/presentation-studio/security/advisories/new). Do not open a public Issue for an undisclosed vulnerability.

Include, when available:

- The affected Release, commit, product, engine, or workflow.
- The security impact and realistic attack preconditions.
- A minimal reproduction that does not contain credentials or private user data.
- Whether untrusted presentations, HTML, archives, scripts, provider responses, or environment variables are involved.
- Any mitigation or safe workaround you have already tested.

Never submit access tokens, passwords, API keys, private documents, full environment dumps, or unrelated local filesystem paths. Redact secrets from logs and preflight output. If sensitive evidence is required, coordinate through the private advisory instead of attaching it publicly.

## What happens next

Reports are assessed against the current source, packaged Release, trust boundaries, and documented capability-degradation behavior. A valid report may result in a private advisory, a tested fix, updated documentation, and a new Release when user-facing artifacts are affected.

This project does not promise a response or remediation SLA. Please avoid public disclosure until a fix or coordinated disclosure plan is available.

## Scope notes

- Missing optional software or provider credentials are normally capability limits, not vulnerabilities.
- A report is security-relevant when it crosses a trust boundary, exposes protected data, executes untrusted content, bypasses verification, or misrepresents an unsafe artifact as verified.
- Vulnerabilities inherited from vendored upstream engines are assessed with the corresponding upstream source, license, adapter, and release evidence.
