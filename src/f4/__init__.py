"""F4 public core. No telemetry, services, or network clients are initialized."""

from .economics import Payoffs, expected_values, verification_threshold
from .synth import Portfolio, generate_portfolio

__version__ = "0.1.0"
__all__ = [
    "Payoffs",
    "Portfolio",
    "expected_values",
    "generate_portfolio",
    "verification_threshold",
]
