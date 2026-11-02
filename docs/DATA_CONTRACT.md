# Canonical data contract

Schema version `1.0`. Python records are in `f4.contracts`; the portable JSON
Schema is in `schemas/contract-v1.json`. All records require a nonempty string ID
and a timezone-aware `observed_at`. Python normalizes times to UTC. Ingestion
rejects unknown fields, incorrect types and unsupported schema versions.

| Entity | Purpose | Additional essential fields |
| --- | --- | --- |
| Carrier | Operating identity | legal_name, onboarded_at, optional USDOT/MC and hashed attributes |
| Debtor | Broker or shipper | name, identifier_hash, days_to_pay |
| Invoice | Funding request | carrier_id, debtor_id, load_id, amount, advance, submitted_at, due_at |
| Load | Underlying shipment | reference, origin, destination, pickup_at, delivery_at, rate |
| Payment | Settlement evidence | payer_id, payee_id, account_id, amount, paid_at |
| BankAccount | Tokenized destination | account_hash, routing_hash, first_seen_at, last_seen_at, verified |
| ContactPoint | Tokenized contact | carrier_id, kind, value_hash |
| DeviceSession | Portal event | carrier_id, device_hash, ip_hash, event, occurred_at |
| Document | Evidence metadata | carrier_id, kind, file_hash, extracted_fields |
| AccountEvent | Account change | carrier_id, event, target_id, occurred_at |
| Outcome | Confirmed result | invoice_id, carrier_id, is_fraud, confirmed_at, loss, recovery |
| Decision | Logged policy action | invoice_id, action, fraud_probability, propensity, action_probabilities, expected_values, reason_codes, model_version, policy_version, decided_at |

Use namespaced strings at the source boundary if IDs overlap across systems.
One dataset represents one client/tenant. Combining tenants requires an explicit
partitioning and authorization layer; the reference API does not implement
multi-tenant access control.

## Revisions and knowledge time

`latest_as_of(records, t)` chooses the last observed version of each ID at or
before `t`. Duplicate `(id, observed_at)` pairs are rejected as ambiguous. A
correction learned tomorrow must not replace what was known yesterday.

Outcome `confirmed_at` describes when the result was established; `observed_at`
describes when the framework could know it. Both constrain label availability.
An old unpaid invoice without a confirmed outcome is unresolved, not clean.

The framework checks referential integrity across the full portfolio. It does
not infer that every referenced entity was already visible at every event time;
as-of feature builders must apply their own visibility checks.

## Amounts and identifiers

Amounts are finite, nonnegative, currency-denominated numbers. Advances cannot
exceed invoice amounts. Recoveries cannot exceed recorded losses in this v1
contract; expenses or excess recoveries need a separately modeled adjustment.
No currency conversion is performed. A three-letter uppercase currency code is
syntactically checked, not validated against an external registry.

`hash_identifier` uses HMAC-SHA256 with a client-owned key of at least 32 bytes
and a field namespace. Normalize phone numbers, email addresses and addresses
upstream using explicit client rules. Do not remove bank-account leading zeros.
Key rotation requires controlled re-tokenization or a versioned mapping. Never
log raw identifiers or the HMAC key.

## Adapters

`map_records` accepts an explicit `{canonical_field: source_column}` mapping.
Transform types and timestamps before passing source values. JSONL round trips
preserve canonical records. DuckDB's `write` stores complete JSON bodies and
`read_bodies` restores them; `read` consumes a client-created typed relational
table. All connections and file paths are caller supplied.
