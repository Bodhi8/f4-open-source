"""F4 public core. No telemetry, services, or network clients are initialized."""

__version__ = "0.1.0"

from .economics import Payoffs, best_action, expected_values, verification_threshold  # noqa: E402
from .synth import Portfolio, generate_portfolio  # noqa: E402

__all__ = [
    "Payoffs",
    "Portfolio",
    "best_action",
    "expected_values",
    "generate_portfolio",
    "verification_threshold",
]
