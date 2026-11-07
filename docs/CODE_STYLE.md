# Code Style

## Languages and conventions
- Language/version: [Match the approved stack]
- Naming: [Files, functions, components, variables, tables]
- Formatting/linting: [Tools and actual configuration]
- Type safety: [Rules appropriate to the project]

## Organization
- Directory responsibilities: [Match ARCHITECTURE.md]
- Shared components/utilities: [Where they live]
- Business logic placement: [Where it belongs]
- Import/dependency boundaries: [Allowed relationships]

## Coding rules
- Keep functions focused; follow established repository patterns.
- Validate external inputs at the trust boundary.
- Handle loading, empty, error, and success states explicitly.
- Avoid silent failures and undocumented magic values.
- Reuse existing components before introducing new abstractions.

## Errors and logging
- Error shape: [Standard contract]
- Logging levels and redaction: [Rules from SECURITY.md]

## Dependencies
- New packages: [Approval policy]
- Versioning/lockfile practice: [Policy]

## Review checklist
- Implementation matches the approved feature acceptance criteria.
- Types, format, and lint checks use confirmed repository commands.
- No credentials or unrelated files in the diff.
- Tests cover meaningful changed behavior.

## Verified commands
- Format: [Command or Not configured]
- Lint: [Command or Not configured]
- Type check: [Command or Not configured]
Never invent commands or claim checks passed without running them.
