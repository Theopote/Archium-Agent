# Security Policy

## Supported versions

Archium is currently in **alpha** (`v0.2-alpha.x`). Security fixes are applied on a best-effort basis to the default branch.

| Version | Supported |
|---------|-----------|
| `main` / latest alpha | ✅ Best effort |
| Older tags | ❌ No dedicated backports yet |

## Reporting a vulnerability

Please **do not** open a public GitHub Issue for security vulnerabilities.

Instead, report privately via one of:

1. GitHub **Security Advisories** for this repository:  
   [https://github.com/Theopote/Archium-Agent/security/advisories/new](https://github.com/Theopote/Archium-Agent/security/advisories/new)
2. Or email the maintainers listed on the GitHub profile / release notes (if advisories are unavailable).

Include:

- Affected version / commit
- Description and impact
- Reproduction steps or proof of concept (non-destructive)
- Whether the issue is already public elsewhere

We aim to acknowledge reports within **7 days** and share a remediation plan when feasible.

## Scope notes

Archium typically runs **locally** and talks to third-party LLM APIs. Common risk areas:

- Accidental logging of API keys or document contents
- Prompt / tool injection when untrusted project files are ingested
- Path traversal or unsafe file handling during import/export
- Dependency vulnerabilities in Python / Node packages

Out of scope (unless maintainers decide otherwise):

- Issues that only exist when users deliberately disable local sandboxing or expose the Streamlit UI to the public internet without authentication
- Vulnerabilities solely in upstream LLM providers

## Handling secrets

- Copy `.env.example` → `.env`; never commit `.env`
- Prefer OS keyring / UI settings for API keys when available
- Rotate keys immediately if they may have leaked
