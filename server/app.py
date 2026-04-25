"""
FastAPI application for BOARDROOM environment.

Endpoints:
    POST /reset       — reset environment, get initial observation
    POST /step        — submit action, get next observation + reward
    GET  /state       — current episode state
    GET  /schema      — action/observation schemas
    WS   /ws          — WebSocket for persistent sessions (lower latency)

Usage:
    uv run server
    uvicorn server.app:app --reload --port 8000
"""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:
    raise ImportError("openenv is required. Run: uv sync") from e

try:
    from ..models import BoardroomAction, BoardroomObservation
    from .boardroom_environment import BoardroomEnvironment
except ModuleNotFoundError:
    from models import BoardroomAction, BoardroomObservation
    from server.boardroom_environment import BoardroomEnvironment


app = create_app(
    BoardroomEnvironment,
    BoardroomAction,
    BoardroomObservation,
    env_name="boardroom",
    max_concurrent_envs=8,  # multiple parallel rollouts for GRPO
)


def main(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    main(port=args.port)
