# Security

## Assets and trust boundaries
- Protected data: [What must be protected?]
- Trusted/untrusted inputs: [Users, uploads, APIs, webhooks]
- Threats relevant to this product: [Abuse cases]

## Authentication and authorization
- Identity provider/session policy: [Approved choice]
- Roles and permissions: [Explicit matrix]
- Ownership/tenant checks: [Server/database enforcement]
- Recovery and revocation: [Behavior]

## Secrets and configuration
- Secret names only: [List environment variable names; never values]
- Storage and rotation: [Method and owner]
- Client exposure: [Which config is public; keep private keys server-side]

## Input and output handling
- Validation: [Schemas, allowed values, limits]
- Injection/XSS protections: [Framework-specific controls]
- Upload restrictions: [Types, size limits, storage, scanning if needed]
- Rate limits/abuse handling: [Endpoints, thresholds, response]

## Privacy
- Data collected and purpose: [List]
- Retention, deletion, access: [Rules]
- Logging redaction: [Fields that must not appear in logs]

## Dependencies and deployment
- Dependency review/update policy: [Process]
- Environment separation: [Development/staging/production]
- Security-sensitive change review: [Owner/process]

## Verification
List permission-denial, tenant-isolation, input-validation, and secret-exposure tests in TESTING.md. Record residual risks and owners. This template does not establish regulatory compliance.
