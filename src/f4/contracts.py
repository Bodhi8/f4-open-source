"""Versioned canonical records, strict timestamps, and cross-table checks.

Records are immutable observations. A correction adds a later observed_at
version; it never overwrites the original record. Money is expressed in the
record's ISO currency, and currency conversion is outside this contract.
"""

from __future__ import annotations

import hashlib
import hmac
import math
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from functools import lru_cache
from types import UnionType
from typing import Any, ClassVar, Mapping, get_args, get_origin, get_type_hints

SCHEMA_VERSION = "1.0"


@lru_cache(maxsize=None)
def _hints(cls):
    return get_type_hints(cls)


def _matches(value, hint) -> bool:
    if hint is Any:
        return True
    origin, args = get_origin(hint), get_args(hint)
    if origin is UnionType:
        return any(_matches(value, choice) for choice in args)
    if origin is dict:
        return isinstance(value, dict) and all(
            _matches(k, args[0]) and _matches(v, args[1]) for k, v in value.items()
        )
    if origin is tuple:
        return isinstance(value, tuple) and all(_matches(v, args[0]) for v in value)
    if hint is float:
        return type(value) in (int, float) and math.isfinite(value)
    if hint in (str, bool, int):
        return type(value) is hint
    return isinstance(value, hint)


def timestamp(value: str | datetime) -> datetime:
    result = (
        datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    )
    if not isinstance(result, datetime) or result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return result.astimezone(timezone.utc)


def finite(value: float, name: str, minimum: float | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


def probability(value: float, name: str = "probability") -> None:
    finite(value, name, 0)
    if value > 1:
        raise ValueError(f"{name} must be <= 1")


def hash_identifier(value: str, *, secret: bytes, namespace: str) -> str:
    """Keyed, domain-separated HMAC. Normalize according to field semantics first.

    Keys belong in the client's secret manager. Simple SHA hashes are unsuitable
    for enumerable identifiers. This deliberately preserves account leading zeros.
    """
    if len(secret) < 32 or not namespace or not value.strip():
        raise ValueError("use a >=32-byte secret, namespace and nonempty identifier")
    message = namespace.encode() + b"\x00" + value.strip().encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


@dataclass(frozen=True, kw_only=True)
class Record:
    id: str
    observed_at: datetime
    schema_version: str = SCHEMA_VERSION
    required: ClassVar[tuple[str, ...]] = ()
    nonnegative: ClassVar[tuple[str, ...]] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("id is required")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported schema_version")
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name.endswith("_at") and value is not None:
                object.__setattr__(self, f.name, timestamp(value))
        for f in fields(self):
            if not _matches(getattr(self, f.name), _hints(type(self))[f.name]):
                raise ValueError(f"invalid type for {f.name}")
        for key in self.required:
            if not isinstance(getattr(self, key), str) or not getattr(self, key).strip():
                raise ValueError(f"{key} is required")
        for key in self.nonnegative:
            finite(getattr(self, key), key, 0)
        if hasattr(self, "currency"):
            c = getattr(self, "currency")
            if not isinstance(c, str) or len(c) != 3 or not c.isascii() or not c.isupper():
                raise ValueError("currency must be a three-letter uppercase code")


@dataclass(frozen=True, kw_only=True)
class Carrier(Record):
    legal_name: str
    onboarded_at: datetime
    usdot: str = ""
    mc_number: str = ""
    dba_name: str = ""
    address_hash: str = ""
    contact_hash: str = ""
    authority_at: datetime | None = None
    required = ("legal_name",)


@dataclass(frozen=True, kw_only=True)
class Debtor(Record):
    name: str
    identifier_hash: str = ""
    days_to_pay: float = 0
    required = ("name",)
    nonnegative = ("days_to_pay",)


@dataclass(frozen=True, kw_only=True)
class Invoice(Record):
    carrier_id: str
    debtor_id: str
    load_id: str
    amount: float
    advance: float
    submitted_at: datetime
    due_at: datetime
    currency: str = "USD"
    status: str = "submitted"
    required = ("carrier_id", "debtor_id", "load_id")
    nonnegative = ("amount", "advance")

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.advance > self.amount or self.due_at < self.submitted_at:
            raise ValueError("advance exceeds amount or due_at precedes submission")


@dataclass(frozen=True, kw_only=True)
class Load(Record):
    reference: str
    origin: str
    destination: str
    pickup_at: datetime
    delivery_at: datetime
    rate: float
    currency: str = "USD"
    required = ("reference", "origin", "destination")
    nonnegative = ("rate",)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.delivery_at < self.pickup_at:
            raise ValueError("delivery precedes pickup")


@dataclass(frozen=True, kw_only=True)
class Payment(Record):
    payer_id: str
    payee_id: str
    account_id: str
    amount: float
    paid_at: datetime
    remittance_reference: str = ""
    invoice_id: str = ""
    currency: str = "USD"
    required = ("payer_id", "payee_id", "account_id")
    nonnegative = ("amount",)


@dataclass(frozen=True, kw_only=True)
class BankAccount(Record):
    account_hash: str
    routing_hash: str
    first_seen_at: datetime
    last_seen_at: datetime
    verified: bool = False
    required = ("account_hash", "routing_hash")

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.last_seen_at < self.first_seen_at or not isinstance(self.verified, bool):
            raise ValueError("invalid bank observation")


@dataclass(frozen=True, kw_only=True)
class ContactPoint(Record):
    carrier_id: str
    kind: str
    value_hash: str
    required = ("carrier_id", "kind", "value_hash")


@dataclass(frozen=True, kw_only=True)
class DeviceSession(Record):
    carrier_id: str
    device_hash: str
    ip_hash: str
    event: str
    occurred_at: datetime
    required = ("carrier_id", "device_hash", "ip_hash", "event")


@dataclass(frozen=True, kw_only=True)
class Document(Record):
    carrier_id: str
    kind: str
    file_hash: str
    extracted_fields: dict[str, Any]
    invoice_id: str = ""
    required = ("carrier_id", "kind", "file_hash")

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.extracted_fields, dict):
            raise ValueError("extracted_fields must be an object")


@dataclass(frozen=True, kw_only=True)
class AccountEvent(Record):
    carrier_id: str
    event: str
    target_id: str
    occurred_at: datetime
    previous_target_id: str = ""
    required = ("carrier_id", "event", "target_id")


@dataclass(frozen=True, kw_only=True)
class Outcome(Record):
    invoice_id: str
    carrier_id: str
    is_fraud: bool
    confirmed_at: datetime
    loss: float = 0
    recovery: float = 0
    scheme: str = ""
    currency: str = "USD"
    required = ("invoice_id", "carrier_id")
    nonnegative = ("loss", "recovery")

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.is_fraud, bool) or self.recovery > self.loss:
            raise ValueError("invalid outcome or recovery exceeds loss")


@dataclass(frozen=True, kw_only=True)
class Decision(Record):
    invoice_id: str
    action: str
    fraud_probability: float
    propensity: float
    action_probabilities: dict[str, float]
    expected_values: dict[str, float]
    reason_codes: tuple[str, ...]
    model_version: str
    policy_version: str
    decided_at: datetime
    reviewer: str = ""
    required = ("invoice_id", "action", "model_version", "policy_version")

    def __post_init__(self) -> None:
        super().__post_init__()
        probability(self.fraud_probability)
        probability(self.propensity, "propensity")
        if self.propensity == 0 or not self.action_probabilities:
            raise ValueError("chosen action must have positive propensity")
        for p in self.action_probabilities.values():
            probability(p)
        if not math.isclose(sum(self.action_probabilities.values()), 1.0, abs_tol=1e-9):
            raise ValueError("action probabilities must sum to one")
        if not math.isclose(self.action_probabilities.get(self.action, 0), self.propensity):
            raise ValueError("propensity must equal chosen action probability")
        if self.action not in self.expected_values:
            raise ValueError("chosen action requires an expected value")
        for value in self.expected_values.values():
            finite(value, "expected value")


ENTITIES = {
    c.__name__: c
    for c in (
        Carrier,
        Debtor,
        Invoice,
        Load,
        Payment,
        BankAccount,
        ContactPoint,
        DeviceSession,
        Document,
        AccountEvent,
        Outcome,
        Decision,
    )
}


def to_dict(record: Record) -> dict[str, Any]:
    return {k: v.isoformat() if isinstance(v, datetime) else v for k, v in asdict(record).items()}


def from_dict(entity: str, row: Mapping[str, Any]) -> Record:
    if entity not in ENTITIES:
        raise ValueError(f"unknown entity: {entity}")
    values = dict(row)
    if entity == "Decision" and "reason_codes" in values:
        values["reason_codes"] = tuple(values["reason_codes"])
    return ENTITIES[entity](**values)


def latest_as_of(records: list[Record], as_of: datetime) -> list[Record]:
    """Latest observed version per ID, rejecting ambiguous same-time versions."""
    cutoff = timestamp(as_of)
    result: dict[str, Record] = {}
    seen: set[tuple[str, datetime]] = set()
    for row in records:
        key = (row.id, row.observed_at)
        if key in seen:
            raise ValueError(f"duplicate record version: {key}")
        seen.add(key)
        if row.observed_at <= cutoff and (
            row.id not in result or row.observed_at > result[row.id].observed_at
        ):
            result[row.id] = row
    return sorted(result.values(), key=lambda r: r.id)


def validate_portfolio(tables: Mapping[str, list[Record]]) -> list[str]:
    """Return quality failures. Empty optional tables are valid; dangling references are not."""
    errors: list[str] = []
    ids = {name: {r.id for r in rows} for name, rows in tables.items()}
    links = {
        "Invoice": {"carrier_id": "Carrier", "debtor_id": "Debtor", "load_id": "Load"},
        "Outcome": {"invoice_id": "Invoice", "carrier_id": "Carrier"},
        "AccountEvent": {"carrier_id": "Carrier"},
        "ContactPoint": {"carrier_id": "Carrier"},
        "DeviceSession": {"carrier_id": "Carrier"},
        "Document": {"carrier_id": "Carrier", "invoice_id": "Invoice"},
        "Decision": {"invoice_id": "Invoice"},
        "Payment": {
            "payer_id": "Debtor",
            "payee_id": "Carrier",
            "account_id": "BankAccount",
            "invoice_id": "Invoice",
        },
    }
    for name, rows in tables.items():
        if name not in ENTITIES:
            errors.append(f"unknown table {name}")
            continue
        versions: set[tuple[str, datetime]] = set()
        for row in rows:
            if not isinstance(row, ENTITIES[name]):
                errors.append(f"wrong record type in {name}")
                continue
            key = (row.id, row.observed_at)
            if key in versions:
                errors.append(f"duplicate {name} version {row.id}")
            versions.add(key)
            for field, target in links.get(name, {}).items():
                value = getattr(row, field)
                if value and value not in ids.get(target, set()):
                    errors.append(f"{name}/{row.id}: missing {target}/{value}")
            if isinstance(row, AccountEvent) and row.event == "bank_change":
                if row.target_id not in ids.get("BankAccount", set()):
                    errors.append(f"AccountEvent/{row.id}: missing bank target")
                previous = row.previous_target_id
                if previous and previous not in ids.get("BankAccount", set()):
                    errors.append(f"AccountEvent/{row.id}: missing previous bank target")
    return errors
