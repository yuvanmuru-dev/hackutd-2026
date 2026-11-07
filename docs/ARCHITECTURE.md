# Architecture

## System purpose
[Summarize the approved PRD and technical constraints.]

## Stack decisions
| Layer | Selected technology | Reason | Constraints |
| --- | --- | --- | --- |
| Frontend | [Choice] | [Reason] | [Constraint] |
| Backend/API | [Choice] | [Reason] | [Constraint] |
| Database | [Choice] | [Reason] | [Constraint] |
| Authentication | [Choice] | [Reason] | [Constraint] |
| Hosting | [Choice] | [Reason] | [Constraint] |

## System boundaries
- Client owns: [Presentation and allowed client behavior]
- Server owns: [Validation, permissions, business rules]
- External services own: [Capabilities and failure behavior]
- Out of scope: [Excluded systems]

## Request and data flow
1. [User action] enters [client component].
2. [API endpoint] validates input and authenticates the caller.
3. [Service] checks authorization and applies the rule.
4. [Database operation] reads or writes permitted records.
5. [Response] updates the UI; [failure] shows [recovery].

## Interfaces
- API contract: [Method, path, request, response, errors]
- Events/jobs: [Producer, consumer, retry/idempotency rules]

## Project structure
[List real or proposed directories and their responsibilities.]

## Operations
- Environments, configuration, deployment, rollback: [Plan]
- Logs, monitoring, scale limits: [Plan]

## Decisions and unknowns
[Record confirmed choices separately from proposals; assign owners.]
