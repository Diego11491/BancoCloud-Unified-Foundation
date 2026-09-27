import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


class TransferError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TransferCommand:
    source_account: UUID
    destination_account: UUID
    amount: Decimal
    device_ref: str | None = None
    beneficiary_ref: str | None = None

    def validate(self) -> None:
        if self.source_account == self.destination_account:
            raise TransferError("Source and destination must differ")
        if self.amount <= 0:
            raise TransferError("Amount must be greater than zero")

    def request_hash(self) -> str:
        payload = {
            "source_account": str(self.source_account),
            "destination_account": str(self.destination_account),
            "amount": str(self.amount),
            "device_ref": self.device_ref,
            "beneficiary_ref": self.beneficiary_ref,
        }
        # Preserve the legacy Core serialization so retries remain valid across the modular cutover.
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
