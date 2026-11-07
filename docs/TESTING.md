# Testing

## Goals and scope
[What must work before release? Link PRD feature IDs and security requirements.]

## Test layers
- Unit: [Business rules and validation]
- Integration: [API/database/service boundaries]
- End-to-end: [Critical user journeys]
- Manual: [UI, accessibility, and unsupported automation cases]

## Acceptance test matrix
| Feature/risk | Scenario | Expected result | Layer | Status |
| --- | --- | --- | --- | --- |
| F-01 | [Happy path] | [Observable result] | [Layer] | Not run |
| F-01 | [Invalid input] | [Safe error/recovery] | [Layer] | Not run |
| Permissions | [Unauthorized caller] | [Access denied; no data leaked] | Integration | Not run |
| Isolation | [Access another tenant’s record] | [Denied] | Integration | Not run |

## Fixtures and environments
- Synthetic test users and data: [Plan]
- External services: [Mocks/sandbox and assumptions]
- Reset/isolation: [Method]

## Verified commands
- Unit/integration: [Actual command or Not configured]
- End-to-end: [Actual command or Not configured]
- Build/type check: [Actual command or Not configured]

## Release criteria
[Required passing scenarios, unresolved failure policy, and owner.]

## Results
For each execution record command, result, failures, and untested limitations. Keep Not run distinct from Passed. Include regression tests for important bug fixes.
