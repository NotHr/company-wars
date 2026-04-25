"""BOARDROOM Environment Client."""

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from .models import BoardroomAction, BoardroomObservation, CompanyStats


class BoardroomEnv(EnvClient[BoardroomAction, BoardroomObservation, State]):
    """
    Client for the BOARDROOM corporate warfare environment.

    Maintains a persistent WebSocket connection. One call to reset() starts
    a game; repeated step() calls advance through up to 12 turns.

    Example:
        with BoardroomEnv(base_url="http://localhost:8000") as env:
            obs = env.reset()
            print(obs.prompt)          # full formatted LLM prompt
            action = BoardroomAction(action_type="EARNINGS_CALL")
            result = env.step(action)
            print(result.reward)
    """

    def _step_payload(self, action: BoardroomAction) -> Dict:
        payload: Dict = {
            "action_type": action.action_type,
            "action_target": action.action_target,
            "private_emails": [e.model_dump() for e in action.private_emails],
        }
        if action.press_release:
            payload["press_release"] = action.press_release.model_dump()
        return payload

    def _parse_result(self, payload: Dict) -> StepResult[BoardroomObservation]:
        obs_data = payload.get("observation", {})

        your_stats = None
        if obs_data.get("your_stats"):
            your_stats = CompanyStats(**obs_data["your_stats"])

        all_companies = [CompanyStats(**c) for c in obs_data.get("all_companies", [])]

        observation = BoardroomObservation(
            you_are=obs_data.get("you_are", ""),
            turn=obs_data.get("turn", 0),
            max_turns=obs_data.get("max_turns", 12),
            your_stats=your_stats,
            all_companies=all_companies,
            emails_received=obs_data.get("emails_received", []),
            press_wire=obs_data.get("press_wire", []),
            active_partnerships=obs_data.get("active_partnerships", []),
            pending_partnership_proposals=obs_data.get("pending_partnership_proposals", []),
            leaderboard=obs_data.get("leaderboard", []),
            game_log=obs_data.get("game_log", []),
            prompt=obs_data.get("prompt", ""),
            done=payload.get("done", False),
            reward=payload.get("reward"),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
