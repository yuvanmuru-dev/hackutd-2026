# Copy-paste document creation prompt

Fill in the brief, then paste the complete prompt into your coding assistant. Attach the templates or provide their accessible local folder.

```text
Help me create eight consistent project documents before coding.

PROJECT BRIEF
App name: [name]
Problem and desired outcome: [description]
Target users: [description]
MVP features: [list]
Main user journeys: [steps]
Features excluded for now: [list]
Platform: [web/mobile/desktop]
Approved stack, if any: [choices or undecided]
Design references: [links/images or undecided]
Data and integrations: [description]
Roles and data ownership: [description]
Budget, deadline, and other constraints: [description]
Repository/template location: [paths, if available]

Use the pack’s headings to create:
1. docs/PRD.md
2. docs/DESIGN_SYSTEM.md
3. docs/ARCHITECTURE.md
4. AGENTS.md at the project root
5. docs/DATABASE.md
6. docs/SECURITY.md
7. docs/CODE_STYLE.md
8. docs/TESTING.md

Inspect the existing repository when available and preserve existing instructions. Start by asking the questions that block accurate documentation. Offer proposed options for undecided choices, clearly labeled for approval. Do not invent decisions, product claims, dependencies, credentials, or test results.

Draft in this dependency order: PRD, Design System, Architecture, Database, Security, Code Style, Testing, then AGENTS.md. Link each feature to observable acceptance criteria. Align schema and permissions with the architecture. Cover loading/error states and unauthorized access. Record actual verified development/test commands where they exist; otherwise write Not configured.

Before finalizing, check all eight docs for inconsistent scope, naming, stack, roles, interfaces, and acceptance criteria. Explain unresolved issues. Save the approved docs only; do not implement the app, install packages, run production migrations, or deploy as part of this documentation task.
```
