"""BOARDROOM — Multi-Agent Corporate Warfare Environment."""

try:
    from .client import BoardroomEnv
    from .models import BoardroomAction, BoardroomObservation, CompanyStats, Email, PressRelease

    __all__ = [
        "BoardroomAction",
        "BoardroomObservation",
        "CompanyStats",
        "Email",
        "PressRelease",
        "BoardroomEnv",
    ]
except ImportError:
    # Imported as a standalone module (e.g., pytest test collection) — skip package-level re-exports.
    pass
