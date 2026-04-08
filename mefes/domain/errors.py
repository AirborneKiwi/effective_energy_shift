# errors.py

class MefesError(Exception):
    """Base class for all domain-level errors in the mEfES core."""


class ValidationError(MefesError):
    """Raised when an input or model invariant is invalid."""


class PacketLaneError(MefesError):
    """Base class for packet-lane consistency errors."""


class PacketOverlapError(PacketLaneError):
    """Raised when packets overlap in a lane where canonical ordering forbids it."""


class PacketOrderError(PacketLaneError):
    """Raised when packet ordering in a lane is invalid."""


class PhaseGroupError(MefesError):
    """Base class for phase-group errors."""


class InvalidPhaseGroupOperation(PhaseGroupError):
    """Raised when an operation is not valid for the current phase-group type."""


class MergeError(PhaseGroupError):
    """Raised when phase groups cannot be merged consistently."""


class ShiftError(PhaseGroupError):
    """Raised when a shift operation cannot be executed consistently."""


class InvariantViolation(MefesError):
    """Raised when an internal algorithm invariant is violated."""