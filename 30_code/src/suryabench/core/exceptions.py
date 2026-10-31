"""Custom exceptions for SuryaBench."""


class SuryaBenchError(Exception):
    """Base exception for all SuryaBench errors."""


class GraphIntegrityError(SuryaBenchError):
    """Raised when supersession graph integrity validation fails."""


class GraphCycleError(GraphIntegrityError):
    """Raised when a cycle is detected in supersession relations."""


class ManifestMismatchError(SuryaBenchError):
    """Raised when file hash does not match corpus manifest hash."""


class TestSplitAccessViolation(SuryaBenchError):
    """Raised when held-out test split cases are accessed without evaluation authorization."""

    __test__ = False


class PredicateEvaluationError(SuryaBenchError):
    """Raised when an applicability predicate encounters an evaluation failure."""


class CaseValidationError(SuryaBenchError):
    """Raised when a synthetic case or fault event fails validation checks."""


class InvalidModelOutput(SuryaBenchError):
    """The model answered, but its reply is unusable (not a JSON object, or cut off at the output cap).

    Runners score this as an invalid output for that case (plan D24), counted and reported per model;
    infrastructure failures (network, quota) stay SuryaBenchError and fail the run."""
