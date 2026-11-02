# Security

This package has no telemetry, embedded credentials or network clients. It runs
with the permissions of its caller. Treat local files, notebooks and optional
database connections according to the client's data-handling policy.

HMAC tokenization is pseudonymization, not a guarantee that linked records are
anonymous. Keep keys in a secret manager and enforce tenant isolation outside
this package. Do not place client data in GitHub issues, test fixtures or CI logs.

Report vulnerabilities through the repository's private security reporting
feature after the maintainer enables it, or an established private contact with
the maintainer. Do not post exploitable details with client identifiers publicly.

Optional dependencies, cloud access controls, endpoint authentication and
production deployment require environment-specific validation. The framework
does not certify regulatory compliance or make legal determinations.
