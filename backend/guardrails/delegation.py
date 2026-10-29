"""Per-task delegation counter."""
from dataclasses import dataclass

class DelegationLimitExceeded(RuntimeError):
    """Raised before a delegation exceeds the configured maximum."""

@dataclass
class DelegationCounter:
    maximum: int
    count: int = 0

    def consume(self, agent: str) -> None:
        if self.count >= self.maximum:
            raise DelegationLimitExceeded(
                f"Delegation limit reached ({self.maximum}); cannot delegate to {agent}."
            )
        self.count += 1
