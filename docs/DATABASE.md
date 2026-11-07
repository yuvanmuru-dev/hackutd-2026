# Database

## Storage model
- Database/provider: [Approved choice from ARCHITECTURE.md]
- Ownership model: [Single-user, organization, or tenant]
- Data classification: [Public, internal, personal, sensitive]

## Entities
| Entity | Purpose | Owner | Retention |
| --- | --- | --- | --- |
| [Entity] | [Purpose] | [User/tenant/system] | [Period and deletion rule] |

## Schema
For each table/collection list name, fields, types, nullability, defaults, primary key, foreign keys, and unique constraints.
- [Table]: [Fields and constraints]
- Example proposal: tasks(id, owner_id, title, status, created_at). Approve or replace before implementation.

## Relationships
- [Entity A] has [cardinality] [Entity B].
- Delete/update behavior: [Cascade, restrict, or explicit cleanup]

## Access rules
- Who can read/create/update/delete each entity?
- How is ownership or tenant isolation enforced?
- Which server/database checks prevent unauthorized access?

## Queries and indexes
- Key query: [Filter, sort, pagination]
- Index: [Fields, reason, anticipated workload]

## Migrations and seed data
- Migration tool and review process: [Choice]
- Seed data: [Synthetic examples only]
- Rollback/backups/restore check: [Plan]

## Data validation
[Required fields, allowed values, consistency rules, and failure responses.]
