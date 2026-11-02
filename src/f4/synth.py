"""Seeded, synthetic-only portfolio with delayed outcomes and four injected schemes."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .contracts import (
    ENTITIES,
    AccountEvent,
    BankAccount,
    Carrier,
    ContactPoint,
    Debtor,
    DeviceSession,
    Document,
    Invoice,
    Load,
    Outcome,
    Payment,
    Record,
    from_dict,
    hash_identifier,
    timestamp,
    to_dict,
    validate_portfolio,
)


@dataclass
class Portfolio:
    tables: dict[str, list[Record]]
    truth: dict[str, str]
    seed: int

    def write(self, directory: str | Path) -> None:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        for entity, rows in self.tables.items():
            with (path / f"{entity}.jsonl").open("w", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(to_dict(row), sort_keys=True, allow_nan=False) + "\n")
        # Truth is a separate evaluator-only file, never a field in model input tables.
        (path / "synthetic_truth.json").write_text(
            json.dumps(self.truth, indent=2), encoding="utf-8"
        )
        (path / "manifest.json").write_text(
            json.dumps(
                {
                    "synthetic": True,
                    "seed": self.seed,
                    "schema_version": "1.0",
                    "tables": {k: len(v) for k, v in self.tables.items()},
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    @classmethod
    def read(cls, directory: str | Path) -> Portfolio:
        path = Path(directory)
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        tables = {
            entity: [
                from_dict(entity, json.loads(line))
                for line in (path / f"{entity}.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            for entity in manifest["tables"]
        }
        errors = validate_portfolio(tables)
        if errors:
            raise ValueError("; ".join(errors))
        return cls(
            tables,
            json.loads((path / "synthetic_truth.json").read_text(encoding="utf-8")),
            manifest["seed"],
        )


def generate_portfolio(
    *,
    carriers: int = 24,
    invoices: int = 600,
    seed: int = 42,
    start: datetime | None = None,
    horizon_days: int = 360,
) -> Portfolio:
    if carriers < 12 or invoices < carriers * 4 or horizon_days < 120:
        raise ValueError("at least 12 carriers, 4 invoices per carrier, and 120 days are required")
    start = timestamp(start or datetime(2025, 1, 1, tzinfo=timezone.utc))
    rng = random.Random(seed)
    tables: dict[str, list[Record]] = {name: [] for name in ENTITIES}
    truth: dict[str, str] = {}
    secret = hashlib.sha256(f"SYNTHETIC-ONLY-{seed}".encode()).digest()

    def hashed(value: str, domain: str) -> str:
        return hash_identifier(value, secret=secret, namespace=domain)

    for i in range(8):
        tables["Debtor"].append(
            Debtor(
                id=f"d{i}",
                name=f"Synthetic Shipper {i}",
                observed_at=start - timedelta(days=180),
                days_to_pay=30 + i,
            )
        )
    for i in range(carriers + 1):
        tables["BankAccount"].append(
            BankAccount(
                id=f"b{i}",
                account_hash=hashed(str(i), "bank"),
                routing_hash=hashed("000000000", "routing"),
                first_seen_at=start - timedelta(days=180),
                last_seen_at=start - timedelta(days=180),
                observed_at=start - timedelta(days=180),
                verified=i % 3 != 0,
            )
        )
    for i in range(carriers):
        joined = start - timedelta(days=rng.randint(60, 500))
        contact = hashed("ring-contact" if i < 4 else f"contact-{i}", "contact")
        tables["Carrier"].append(
            Carrier(
                id=f"c{i}",
                legal_name=f"Synthetic Freight {i}",
                usdot=f"SYNTH-{i:06}",
                onboarded_at=joined,
                authority_at=joined,
                contact_hash=contact,
                address_hash=hashed(f"address-{i}", "address"),
                observed_at=joined,
            )
        )
        tables["ContactPoint"].append(
            ContactPoint(
                id=f"cp{i}",
                carrier_id=f"c{i}",
                kind="email",
                value_hash=contact,
                observed_at=joined,
            )
        )
        tables["AccountEvent"].append(
            AccountEvent(
                id=f"ae{i}",
                carrier_id=f"c{i}",
                event="bank_change",
                target_id=f"b{0 if i < 4 else i}",
                occurred_at=joined,
                observed_at=joined,
            )
        )
    takeover_at = start + timedelta(days=60)
    tables["AccountEvent"].append(
        AccountEvent(
            id="takeover-bank",
            carrier_id="c4",
            event="bank_change",
            target_id=f"b{carriers}",
            previous_target_id="b4",
            occurred_at=takeover_at,
            observed_at=takeover_at,
        )
    )
    tables["DeviceSession"].append(
        DeviceSession(
            id="takeover-session",
            carrier_id="c4",
            device_hash=hashed("new-device", "device"),
            ip_hash=hashed("192.0.2.1", "ip"),
            event="bank_change",
            occurred_at=takeover_at,
            observed_at=takeover_at,
        )
    )
    prior_duplicate: str | None = None
    for i in range(invoices):
        ci = i % carriers
        day = horizon_days * i / invoices
        submitted = start + timedelta(days=day)
        debtor = "d0" if ci in (5, 6) else f"d{rng.randrange(8)}"
        scheme = ""
        if ci < 4 and rng.random() < 0.55:
            scheme = "ring"
        elif ci == 4 and 60 <= day <= 90:
            scheme = "takeover"
        elif ci in (5, 6) and rng.random() < 0.6:
            scheme = "collusion"
        load_id = f"l{i}"
        amount = round(rng.uniform(900, 7000) * (2 if scheme == "takeover" else 1), 2)
        if scheme == "takeover":
            amount = round(rng.uniform(12000, 18000), 2)
        if ci == 8 and prior_duplicate is not None:
            load_id = prior_duplicate
            scheme = "double_billing"
        else:
            tables["Load"].append(
                Load(
                    id=load_id,
                    reference=f"SYNTH-LOAD-{i}",
                    origin=f"ZONE-{i % 11}",
                    destination=f"ZONE-{(i + 4) % 11}",
                    pickup_at=submitted - timedelta(days=3),
                    delivery_at=submitted - timedelta(days=1),
                    rate=amount,
                    observed_at=submitted,
                )
            )
        if ci == 7:
            prior_duplicate = load_id
        invoice = Invoice(
            id=f"i{i}",
            carrier_id=f"c{ci}",
            debtor_id=debtor,
            load_id=load_id,
            amount=amount,
            advance=round(amount * 0.9, 2),
            submitted_at=submitted,
            due_at=submitted + timedelta(days=30),
            observed_at=submitted,
        )
        tables["Invoice"].append(invoice)
        tables["Document"].append(
            Document(
                id=f"doc{i}",
                carrier_id=invoice.carrier_id,
                invoice_id=invoice.id,
                kind="invoice",
                file_hash=hashed(f"doc-{i}", "file"),
                extracted_fields={"invoice_id": invoice.id, "amount": amount, "load_id": load_id},
                observed_at=submitted,
            )
        )
        is_fraud = bool(scheme)
        truth[invoice.id] = scheme or "clean"
        confirmed = submitted + timedelta(
            days=rng.randint(35, 75) if is_fraud else rng.randint(25, 50)
        )
        tables["Outcome"].append(
            Outcome(
                id=f"o{i}",
                invoice_id=invoice.id,
                carrier_id=invoice.carrier_id,
                is_fraud=is_fraud,
                confirmed_at=confirmed,
                observed_at=confirmed + timedelta(days=rng.randint(0, 4)),
                loss=invoice.advance if is_fraud else 0,
                recovery=0,
                scheme=scheme,
            )
        )
        if not is_fraud:
            tables["Payment"].append(
                Payment(
                    id=f"p{i}",
                    payer_id=debtor,
                    payee_id=invoice.carrier_id,
                    account_id=f"b{0 if ci < 4 else ci}",
                    invoice_id=invoice.id,
                    amount=amount,
                    paid_at=confirmed,
                    observed_at=confirmed,
                )
            )
    errors = validate_portfolio(tables)
    if errors:
        raise RuntimeError("synthetic generator violated contract: " + "; ".join(errors))
    return Portfolio(tables, truth, seed)
