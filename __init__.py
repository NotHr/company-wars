"""BOARDROOM — Multi-Agent Corporate Warfare Environment."""

try:
    from .client import BoardroomEnv
    from .models import BoardroomAction, BoardroomObservation, CompanyStats, Email, PressRelease
except ImportError:
    # Imported as top-level module (e.g., pytest discovery); relative imports unavailable.
    BoardroomEnv = None  # type: ignore
    BoardroomAction = BoardroomObservation = CompanyStats = Email = PressRelease = None  # type: ignore

__all__ = [
    "BoardroomAction",
    "BoardroomObservation",
    "CompanyStats",
    "Email",
    "PressRelease",
    "BoardroomEnv",
]
