# Security Policy

## Supported Versions

The following versions of the AI Infrastructure Control Plane are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 2.5.x   | :white_check_mark: |
| 2.4.x   | :white_check_mark: |
| 2.3.x   | :white_check_mark: |
| 2.2.x   | :white_check_mark: |
| 2.1.x   | :white_check_mark: |
| 2.0.x   | :white_check_mark: |
| 1.x     | :x:                |
| < 1.0   | :x:                |

The project follows semantic versioning. Security patches are backported to the current major version (v2.x). Version 1.x is no longer supported; users should upgrade to v2.0 or later.

## Security Features

The AI Infrastructure Control Plane implements multiple security layers:

### Supply Chain Security
- **Signed Container Images**: All container images are signed with cosign using keyless signing
- **SBOM**: Software Bill of Materials (SPDX format) generated for every release
- **Build Provenance**: Build attestations attached to images via GitHub Actions
- **Multi-stage Builds**: Minimal attack surface in production images
- **Security Scanning**: Trivy scans for vulnerabilities in containers and dependencies

### Runtime Security
- **RBAC**: Role-based access control for API endpoints
- **JWT Authentication**: JWT-only tenant mode with JWKS validation
- **Fail-Closed Policy**: Governance fails closed when policy bundles are unavailable
- **Tenant Isolation**: Request-level tenant attribution and isolation
- **Network Policies**: Optional NetworkPolicy resources in Helm chart
- **Read-Only Root Filesystem**: Container security contexts enforce read-only root
- **Non-Root User**: Containers run as non-root user (UID 1000)
- **Dropped Capabilities**: All Linux capabilities dropped except required ones

### Policy Security
- **Signed Policy Bundles**: OCI-distributed policy bundles with cosign signatures
- **Versioned Policies**: Immutable policy bundle generations with rollback support
- **Audit Trail**: Durable decision store with foreign key integrity
- **Approval Workflow**: Request-bound approvals with digest verification

### Infrastructure Security
- **OPA Policy Gates**: Kubernetes manifests validated with Open Policy Agent
- **Secret Management**: External secrets integration (see docs/secrets-management.md)
- **TLS**: Optional TLS termination via Ingress
- **PostgreSQL HA**: Encrypted at rest when using managed database services

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability in this project, please report it privately to:

**Email**: 52860508+justrunme@users.noreply.github.com

Please include:

1. **Description**: A clear description of the vulnerability
2. **Impact**: The potential impact and severity of the issue
3. **Reproduction**: Steps to reproduce the vulnerability
4. **Environment**: Affected versions and deployment configurations
5. **Mitigation**: Any known workarounds or mitigations

### What to Expect

- **Acknowledgment**: You will receive an acknowledgment within 48 hours
- **Assessment**: Initial assessment and severity classification within 5 business days
- **Updates**: Regular status updates as the issue is investigated
- **Resolution**: Security patches released as soon as possible
- **Disclosure**: Coordinated disclosure once a fix is available
- **Credit**: Public acknowledgment of your contribution (if desired)

### Security Updates

Security patches are released as:
- **Patch releases** (e.g., v2.4.1) for the current minor version
- **Backports** to supported versions when necessary
- **Security advisories** published via GitHub Security Advisories

Subscribe to release notifications to stay informed about security updates.

## Security Best Practices

When deploying the AI Infrastructure Control Plane:

1. **Use Production Profile**: Deploy with `values-production.yaml` for HA and security hardening
2. **Enable Network Policies**: Set `networkPolicy.enabled=true` in Helm values
3. **External PostgreSQL**: Use managed PostgreSQL with encryption at rest
4. **TLS Termination**: Enable TLS via Ingress or service mesh
5. **RBAC Enforcement**: Configure JWT authentication with `JWT_REQUIRED=true`
6. **Monitor Metrics**: Set up Prometheus alerts for security events
7. **Verify Signatures**: Validate container image and Helm chart signatures with cosign
8. **Update Regularly**: Apply security updates promptly
9. **Audit Logs**: Enable audit logging and retention policies
10. **Least Privilege**: Run with minimal required permissions

See the [threat model](docs/threat-model.md) for detailed security architecture.

## Security Compliance

The project follows security best practices including:

- OWASP Top 10 mitigation strategies
- CIS Kubernetes Benchmark recommendations
- Supply chain security (SLSA framework alignment)
- Container image hardening guidelines
- Secure software development lifecycle (SSDLC)

## Dependencies

Security vulnerabilities in dependencies are tracked via:
- Dependabot alerts
- Trivy vulnerability scanning
- Regular dependency updates

Dependabot is configured to automatically create PRs for security updates.
