"""Data models for BOARDROOM — multi-agent corporate warfare environment."""

from typing import Any, Dict, List, Literal, Optional

from openenv.core.env_server.types import Action, Observation
from pydantic import BaseModel, Field


class Email(BaseModel):
    to: str
    text: str = Field(max_length=500)


class PressRelease(BaseModel):
    claim: str = Field(max_length=500)
    marked_truthful: bool = True


class CompanyStats(BaseModel):
    name: str
    sector: str
    cash: float
    market_share: float
    stock_price: float
    reputation: float
    alive: bool = True


class BoardroomAction(Action):
    """Action output by the LLM each turn."""

    private_emails: List[Email] = Field(default_factory=list)
    press_release: Optional[PressRelease] = None
    action_type: Literal["EARNINGS_CALL", "SABOTAGE", "PARTNERSHIP", "PROPOSE_MERGER", "HOLD"] = "HOLD"
    action_target: Optional[str] = None  # target company name for SABOTAGE/PARTNERSHIP/PROPOSE_MERGER


class BoardroomObservation(Observation):
    """What the LLM sees each turn."""

    you_are: str = ""
    turn: int = 0
    max_turns: int = 12
    your_stats: Optional[CompanyStats] = None
    all_companies: List[CompanyStats] = Field(default_factory=list)
    emails_received: List[Email] = Field(default_factory=list)
    press_wire: List[Dict[str, Any]] = Field(default_factory=list)
    active_partnerships: List[str] = Field(default_factory=list)
    pending_partnership_proposals: List[str] = Field(default_factory=list)
    leaderboard: List[Dict[str, Any]] = Field(default_factory=list)
    game_log: List[str] = Field(default_factory=list)
    prompt: str = ""  # full formatted text prompt for the LLM
