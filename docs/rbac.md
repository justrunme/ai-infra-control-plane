# Control plane RBAC

Roles are mapped from IdP `groups` / `roles` / `realm_access.roles` claims when
`OIDC_JWT_VERIFY=true`.

| Role | Default IdP groups | Typical use |
| --- | --- | --- |
| `platform-admin` | `platform-admins`, `ai-platform-admins` | Activate / rollback policy bundles |
| `tenant-admin` | `tenant-admins`, `ai-tenant-admins` | Tenant-scoped admin (reserved) |
| `approver` | `OIDC_APPROVER_GROUPS` (`ai-approvers`, `secops`) | Approve / reject |
| `auditor` | `ai-auditors`, `auditors` | Read audit surfaces (reserved) |
| `viewer` | `ai-viewers`, `viewers` | Read-only (reserved) |
| `runtime-service` | `ai-runtime-services`, `runtime-services` | Service identity (reserved) |

Override groups with env:

- `OIDC_ROLE_PLATFORM_ADMIN_GROUPS`
- `OIDC_ROLE_TENANT_ADMIN_GROUPS`
- `OIDC_ROLE_AUDITOR_GROUPS`
- `OIDC_ROLE_VIEWER_GROUPS`
- `OIDC_ROLE_RUNTIME_SERVICE_GROUPS`
- `OIDC_APPROVER_GROUPS` (approver)

When JWT verify is **off** (demo), role checks are skipped so local flows keep
working.

## JWT-only tenant

`TENANT_JWT_ONLY=true` (requires `OIDC_JWT_VERIFY=true`):

- Evaluate identity: `tenant_id` / `team` only from verified JWT
- Read/list isolation: ignores `x-ai-tenant` / body tenant spoofing

Enabled in `values-production.yaml`.

## Quota unavailable policy

| `QUOTA_ON_UNAVAILABLE` | Evaluate when Redis is configured but unreachable |
| --- | --- |
| `allow` (default) | Fail-open (demo/dev) |
| `block` | Hard block |
| `approval_required` | Fail-closed to human approval (production) |
