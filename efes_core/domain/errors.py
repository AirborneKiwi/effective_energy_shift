class EfesCoreError(Exception):
    """Base class for all domain-level errors in the EfES core."""

class ImplementationNotKnown(EfesCoreError):
    """Raised when the implementation is not known."""

class ValidationError(EfesCoreError):
    """Raised when an input or model invariant is invalid."""


class InvalidInputError(ValidationError):
    """Raised when the analysis inputs are invalid."""

class NoDeficitError(InvalidInputError):
    """Raised when the time series never contains a deficit phase."""


class NoExcessError(InvalidInputError):
    """Raised when the time series never contains an excess phase."""


class PacketError(EfesCoreError):
    """Base class for packet-related domain errors."""


class PacketValidationError(PacketError, ValidationError):
    """Raised when an EnergyPacket has invalid values."""


class InvalidQueryError(ValidationError):
    """Raised when a dimensioning query is underspecified or overspecified."""
