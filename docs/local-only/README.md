# Local-Only Ops Materials

This directory is reserved for local-only operational materials that must not be published in the public repository.

Examples of suitable local-only content:
- server access notes
- deploy and restart commands
- private runbooks
- environment-specific paths
- ops handoff notes

Rules:
- keep real operational notes in ignored local files
- keep public placeholders short and safe
- do not commit secrets, server credentials, or internal host details

Suggested pattern:
- real local file: local-only and ignored
- public counterpart: `*.example.md` with structure only
