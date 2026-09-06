# Security and privacy

OfferLens processes resumes, which may contain personal information. The default demo keeps input in process memory and LangGraph state in a local SQLite file under `.offerlens/`; that directory is ignored by Git.

## Before production use

- add authentication and per-user authorization;
- encrypt checkpoint and document storage;
- define automatic retention and deletion policies;
- redact phone numbers, email addresses and IDs from logs and traces;
- use signed object-storage URLs instead of a shared filesystem;
- restrict CORS to the deployed frontend;
- sandbox any future browser or code-execution tools;
- treat web pages and uploaded files as untrusted content;
- disable LangSmith tracing for personal data unless organizational policy permits it.

## Current controls

- accepted resume types are limited to PDF, DOCX, TXT and Markdown;
- uploads have a configurable 5 MB default limit;
- Pydantic validates all public request and Agent output schemas;
- external research failures are marked rather than silently replaced;
- model output cannot overwrite deterministic scores, evidence or sources;
- no secrets are committed; `.env` is ignored.

For a vulnerability, open a private security report rather than including personal resume data in a public issue.
